"""Probe and validate on-disk screen files for the dashboard file panel."""

from __future__ import annotations

from pathlib import Path

from modules.config import ShowConfig
from modules.ffprobe_wrapper import codec_tag_to_identifier, probe_file
from modules.filename_parser import FullMatch, parse_filename
from modules.intake import validate_file_specs, validate_filename
from modules.media_formats import (
    group_image_sequence_paths,
    is_recognized_still_extension,
    is_still_media_kind,
    strip_sequence_frame_suffix,
)


def _codec_label(specs, filename: str) -> str | None:
    if is_still_media_kind(specs.media_kind):
        if specs.media_kind == "image_sequence":
            return "sequence"
        return "still"
    if specs.codec_tag:
        return codec_tag_to_identifier(specs.codec_tag) or specs.codec_tag
    if specs.codec_name:
        return specs.codec_name
    if is_recognized_still_extension(Path(filename).suffix):
        return "still"
    return None


def _spec_status(warnings: list[str], failures: list[str]) -> dict[str, str]:
    status = {"resolution": "default", "codec": "default", "fps": "default"}

    def _apply(messages: list[str], level: str) -> None:
        for message in messages:
            lower = message.lower()
            if "resolution" in lower:
                status["resolution"] = level
            if "framerate" in lower or "fps" in lower:
                status["fps"] = level
            if "codec" in lower:
                status["codec"] = level

    _apply(warnings, "warn")
    _apply(failures, "fail")
    return status


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _build_file_row(
    entry: Path,
    *,
    config: ShowConfig,
    screen_id: str,
    location: str,
    sequence: bool = False,
    frame_count: int = 1,
    display_filename: str | None = None,
    size_bytes: int | None = None,
    infos: list[str] | None = None,
) -> dict:
    warnings: list[str] = []
    failures: list[str] = []
    logical_name = display_filename or entry.name
    parsed_result = parse_filename(logical_name, config)
    specs = probe_file(entry, config, sequence=sequence)

    validate_filename(parsed_result, config, warnings, failures)

    parsed_for_validate = (
        parsed_result.parsed if isinstance(parsed_result, FullMatch) else None
    )
    validate_file_specs(
        specs,
        config,
        warnings,
        failures,
        parsed=parsed_for_validate,
        target_screen_id=screen_id,
    )
    if not specs.probe_succeeded and not failures:
        failures.append(f"Could not read file metadata: {specs.probe_error}")

    display_framerate = specs.framerate
    if is_still_media_kind(specs.media_kind):
        display_framerate = None

    row_infos = list(infos or [])
    if sequence and frame_count > 1 and not row_infos:
        row_infos.insert(0, f"Image sequence: {frame_count} frames")

    return {
        "filename": logical_name,
        "file_path": str(entry),
        "size_bytes": size_bytes if size_bytes is not None else _file_size(entry),
        "location": location,
        "specs": {
            "width": specs.width,
            "height": specs.height,
            "framerate": display_framerate,
            "codec": _codec_label(specs, logical_name),
            "media_kind": specs.media_kind,
            "probe_succeeded": specs.probe_succeeded,
            "frame_count": frame_count if sequence else None,
        },
        "spec_status": _spec_status(warnings, failures),
        "warnings": warnings,
        "failures": failures,
        "infos": row_infos,
    }


def list_screen_file_details(
    show_root: Path,
    config: ShowConfig,
    screen_id: str,
) -> list[dict]:
    """Probe logical assets in a screen folder and return dashboard table rows."""
    screen_folder = show_root / "Media" / screen_id
    if not screen_folder.is_dir():
        return []
    if not any(screen.id == screen_id for screen in config.screens):
        return []

    location = f"Media\\{screen_id}\\"
    rows: list[dict] = []
    paths = [entry for entry in screen_folder.iterdir() if entry.is_file()]
    sequences, singletons = group_image_sequence_paths(paths)

    for members in sequences:
        first = members[0]
        logical_name = strip_sequence_frame_suffix(first.name)
        total_size = sum(_file_size(member) for member in members)
        rows.append(
            _build_file_row(
                first,
                config=config,
                screen_id=screen_id,
                location=location,
                sequence=True,
                frame_count=len(members),
                display_filename=logical_name,
                size_bytes=total_size,
            )
        )

    for entry in singletons:
        rows.append(
            _build_file_row(
                entry,
                config=config,
                screen_id=screen_id,
                location=location,
            )
        )

    return sorted(rows, key=lambda row: row["filename"].lower())
