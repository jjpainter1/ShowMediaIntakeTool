"""Delivery format extensions, image sequences, and media kind helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.config import ShowConfig

DEFAULT_IMAGE_EXTENSIONS: tuple[str, ...] = (
    ".jpg",
    ".jpeg",
    ".png",
    ".tga",
    ".tif",
    ".tiff",
    ".exr",
)

DEFAULT_VIDEO_EXTENSIONS: tuple[str, ...] = (
    ".mov",
    ".mp4",
    ".mxf",
    ".avi",
    ".mkv",
    ".wmv",
    ".mpg",
    ".mpeg",
)

IMAGE_PROBE_CODECS: frozenset[str] = frozenset(
    {
        "png",
        "apng",
        "jpeg",
        "mjpeg",
        "bmp",
        "gif",
        "tiff",
        "tga",
        "exr",
        "webp",
    }
)

_SEQUENCE_FRAME_RE = re.compile(r"^(?P<base>.+)_(\d{2,})$")


def normalize_extension(ext: str) -> str:
    """Return a lowercase extension with leading dot."""
    value = ext.strip().lower()
    if not value:
        return ""
    if not value.startswith("."):
        value = f".{value}"
    return value


_RECOGNIZED_STILL_EXTENSIONS: frozenset[str] = frozenset(
    normalize_extension(ext) for ext in DEFAULT_IMAGE_EXTENSIONS
)


def is_recognized_still_extension(ext: str) -> bool:
    """True when the extension is a known still-image format (independent of config acceptance)."""
    return normalize_extension(ext) in _RECOGNIZED_STILL_EXTENSIONS


@dataclass
class ExpectedMediaConfig:
    """Accepted delivery file formats beyond implicit video defaults."""

    accept_stills: bool = False
    image_extensions: list[str] = field(
        default_factory=lambda: list(DEFAULT_IMAGE_EXTENSIONS)
    )
    allow_image_sequences: bool = True
    video_extensions: list[str] | None = None

    def image_ext_set(self) -> set[str]:
        return {normalize_extension(e) for e in self.image_extensions if e}

    def video_ext_set(self) -> set[str]:
        if self.video_extensions:
            return {normalize_extension(e) for e in self.video_extensions if e}
        return set(DEFAULT_VIDEO_EXTENSIONS)

    def is_image_extension(self, ext: str) -> bool:
        return normalize_extension(ext) in self.image_ext_set()

    def is_video_extension(self, ext: str) -> bool:
        return normalize_extension(ext) in self.video_ext_set()

    def classify_extension(self, ext: str) -> str:
        """Return image, video, or unknown for a file extension."""
        normalized = normalize_extension(ext)
        if is_recognized_still_extension(normalized):
            return "image"
        if self.is_video_extension(normalized):
            return "video"
        return "unknown"

    def is_allowed_extension(self, ext: str) -> bool:
        normalized = normalize_extension(ext)
        if is_recognized_still_extension(normalized):
            if not self.accept_stills:
                return False
            return normalized in self.image_ext_set()
        if self.is_video_extension(normalized):
            return True
        return False


def parse_expected_media(data: object) -> ExpectedMediaConfig:
    """Parse expected_media from raw JSON with backward-compatible defaults."""
    if not isinstance(data, dict):
        return ExpectedMediaConfig()
    accept_stills = bool(data.get("accept_stills", False))
    allow_sequences = data.get("allow_image_sequences", True)
    raw_images = data.get("image_extensions")
    image_extensions = (
        [str(e) for e in raw_images]
        if isinstance(raw_images, list) and raw_images
        else list(DEFAULT_IMAGE_EXTENSIONS)
    )
    raw_videos = data.get("video_extensions")
    video_extensions = (
        [str(e) for e in raw_videos]
        if isinstance(raw_videos, list) and raw_videos
        else None
    )
    return ExpectedMediaConfig(
        accept_stills=accept_stills,
        image_extensions=image_extensions,
        allow_image_sequences=bool(allow_sequences) if allow_sequences is not None else True,
        video_extensions=video_extensions,
    )


def image_sequence_key(path: Path) -> tuple[str, str] | None:
    """Return (base_stem_lower, suffix_lower) when filename looks like a sequence frame."""
    if not is_recognized_still_extension(path.suffix):
        return None
    stem = path.stem
    match = _SEQUENCE_FRAME_RE.match(stem)
    if not match:
        return None
    return match.group(1).lower(), path.suffix.lower()


def strip_sequence_frame_suffix(filename: str) -> str:
    """Remove trailing _NNNN frame index for logical filename parsing."""
    path = Path(filename)
    match = _SEQUENCE_FRAME_RE.match(path.stem)
    if not match:
        return filename
    return match.group(1) + path.suffix


def group_image_sequence_paths(
    files: list[Path],
) -> tuple[list[list[Path]], list[Path]]:
    """Group paths into image-sequence batches and singleton stills.

    Uses recognized still extensions and the _NNNN frame suffix pattern only.
    """
    grouped: dict[tuple[str, str], list[Path]] = {}
    singleton_candidates: list[Path] = []

    for path in files:
        if not is_recognized_still_extension(path.suffix):
            singleton_candidates.append(path)
            continue
        key = image_sequence_key(path)
        if key is None:
            singleton_candidates.append(path)
            continue
        grouped.setdefault(key, []).append(path)

    sequences: list[list[Path]] = []
    singletons: list[Path] = list(singleton_candidates)
    for members in grouped.values():
        members.sort(key=lambda p: p.name.lower())
        if len(members) >= 2:
            sequences.append(members)
        else:
            singletons.extend(members)
    return sequences, singletons


def partition_image_sequences(
    files: list[Path],
    config: ShowConfig,
) -> tuple[list[list[Path]], list[Path]]:
    """Split source files into image-sequence groups and remaining singleton paths.

    Grouping uses recognized still extensions and filename pattern only — not whether
    stills are currently accepted in config. That keeps scans fast and shows one row per
    sequence even when formats are disabled or unchecked.
    """
    if not config.expected_media.allow_image_sequences:
        return [], list(files)
    return group_image_sequence_paths(files)


def derive_media_kind(
    path: Path,
    config: ShowConfig,
    *,
    codec_name: str | None,
    sequence: bool = False,
) -> str:
    """Classify probed media as video or image."""
    if sequence:
        return "image_sequence"
    if is_recognized_still_extension(path.suffix):
        return "image"
    if codec_name and codec_name.lower() in IMAGE_PROBE_CODECS:
        return "image"
    return "video"


def is_still_media_kind(media_kind: str) -> bool:
    return media_kind in ("image", "image_sequence")
