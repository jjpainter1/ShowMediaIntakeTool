"""ffprobe integration for video/audio tech spec extraction."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Codec tag mapping  (DESIGN.md §5.5)
# ---------------------------------------------------------------------------

# Maps ffprobe codec_tag_string -> config identifier used in show_config.json
CODEC_TAG_MAP: dict[str, str] = {
    "apco": "prores_422_proxy",
    "apcs": "prores_422_lt",
    "apcn": "prores_422",
    "apch": "prores_422_hq",
    "ap4h": "prores_4444",
    "ap4x": "prores_4444_xq",
    "nclc": "notchlc",
}


def codec_tag_to_identifier(tag: str) -> str | None:
    """Return the config identifier for a codec_tag_string, or None if unknown."""
    return CODEC_TAG_MAP.get(tag.lower())


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class MediaSpecs:
    """Technical spec fields extracted from a single media file via ffprobe."""
    # Video
    width:            int   | None
    height:           int   | None
    framerate:        float | None
    codec_name:       str   | None
    codec_tag:        str   | None   # 4-char tag, e.g. "apch"
    color_space:      str   | None
    color_range:      str   | None
    # Audio
    audio_sample_rate: int  | None
    audio_channels:    int  | None
    # Container
    duration_seconds: float | None
    # Probe status
    probe_succeeded:  bool
    probe_error:      str   | None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_ffprobe_available() -> bool:
    """Return True if ffprobe is on PATH and responds to -version."""
    try:
        result = subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def probe_file(path: Path) -> MediaSpecs:
    """Run ffprobe on path and return a MediaSpecs with all available fields.

    probe_succeeded is True when ffprobe exited cleanly and returned valid JSON,
    regardless of which stream types are present.  Individual fields are None
    when the corresponding stream does not exist (e.g. audio fields on a
    video-only file, or video fields on an audio-only file).
    """
    empty = _empty_specs

    if not path.exists():
        return empty(f"File not found: {path}")

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-print_format", "json",
                "-show_streams",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        return empty("ffprobe not found on PATH")
    except subprocess.TimeoutExpired:
        return empty(f"ffprobe timed out on: {path.name}")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        return empty(f"ffprobe returned error: {stderr[:200]}" if stderr else "ffprobe returned non-zero exit code")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return empty(f"Could not parse ffprobe output: {exc}")

    streams = data.get("streams", [])
    fmt     = data.get("format", {})

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    # --- Video fields ---
    width = height = framerate = None
    codec_name = codec_tag = color_space = color_range = None

    if video_stream:
        width  = _int_or_none(video_stream.get("width"))
        height = _int_or_none(video_stream.get("height"))
        framerate   = _parse_framerate(video_stream.get("r_frame_rate"))
        codec_name  = video_stream.get("codec_name") or None
        raw_tag     = video_stream.get("codec_tag_string", "")
        # ffprobe emits "[0][0][0][0]" when the codec has no registered 4CC
        codec_tag   = raw_tag if (raw_tag and not raw_tag.startswith("[")) else None
        color_space = video_stream.get("color_space") or None
        color_range = video_stream.get("color_range") or None

    # --- Audio fields ---
    audio_sample_rate = audio_channels = None

    if audio_stream:
        audio_sample_rate = _int_or_none(audio_stream.get("sample_rate"))
        audio_channels    = _int_or_none(audio_stream.get("channels"))

    # --- Duration (prefer format-level, fall back to video stream) ---
    duration_seconds = _float_or_none(fmt.get("duration"))
    if duration_seconds is None and video_stream:
        duration_seconds = _float_or_none(video_stream.get("duration"))

    return MediaSpecs(
        width=width,
        height=height,
        framerate=framerate,
        codec_name=codec_name,
        codec_tag=codec_tag,
        color_space=color_space,
        color_range=color_range,
        audio_sample_rate=audio_sample_rate,
        audio_channels=audio_channels,
        duration_seconds=duration_seconds,
        probe_succeeded=True,
        probe_error=None,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _empty_specs(error: str) -> MediaSpecs:
    return MediaSpecs(
        width=None, height=None, framerate=None,
        codec_name=None, codec_tag=None,
        color_space=None, color_range=None,
        audio_sample_rate=None, audio_channels=None,
        duration_seconds=None,
        probe_succeeded=False,
        probe_error=error,
    )


def _parse_framerate(value: str | None) -> float | None:
    """Parse a framerate string such as '30/1' or '30000/1001' into a float."""
    if not value:
        return None
    try:
        if "/" in value:
            num, den = value.split("/", 1)
            den_int = int(den)
            if den_int == 0:
                return None
            return round(int(num) / den_int, 6)
        return float(value)
    except (ValueError, ZeroDivisionError):
        return None


def _int_or_none(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
