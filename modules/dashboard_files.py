"""Probe and validate on-disk screen files for the dashboard file panel."""

from __future__ import annotations

from pathlib import Path

from modules.config import ShowConfig
from modules.ffprobe_wrapper import codec_tag_to_identifier, probe_file
from modules.filename_parser import FullMatch, parse_filename
from modules.intake import validate_file_specs, validate_filename


def _codec_label(specs) -> str | None:
    if specs.codec_tag:
        return codec_tag_to_identifier(specs.codec_tag) or specs.codec_tag
    if specs.codec_name:
        return specs.codec_name
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


def list_screen_file_details(
    show_root: Path,
    config: ShowConfig,
    screen_id: str,
) -> list[dict]:
    """Probe each file in a screen folder and return dashboard table rows."""
    screen_folder = show_root / "Media" / screen_id
    if not screen_folder.is_dir():
        return []
    if not any(screen.id == screen_id for screen in config.screens):
        return []

    location = f"Media\\{screen_id}\\"
    rows: list[dict] = []

    for entry in sorted(screen_folder.iterdir(), key=lambda path: path.name.lower()):
        if not entry.is_file():
            continue

        warnings: list[str] = []
        failures: list[str] = []
        parsed_result = parse_filename(entry.name, config)
        specs = probe_file(entry)

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

        try:
            size_bytes = entry.stat().st_size
        except OSError:
            size_bytes = 0

        rows.append(
            {
                "filename": entry.name,
                "file_path": str(entry),
                "size_bytes": size_bytes,
                "location": location,
                "specs": {
                    "width": specs.width,
                    "height": specs.height,
                    "framerate": specs.framerate,
                    "codec": _codec_label(specs),
                    "probe_succeeded": specs.probe_succeeded,
                },
                "spec_status": _spec_status(warnings, failures),
                "warnings": warnings,
                "failures": failures,
            }
        )

    return rows
