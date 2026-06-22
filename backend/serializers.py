"""JSON serializers for API responses."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from modules.ffprobe_wrapper import MediaSpecs, codec_tag_to_identifier
from modules.filename_parser import FullMatch, NoMatch, PartialMatch, ParsedFilename
from modules.intake import Action, ConflictInfo, ExecutionResult, FilePlan
from modules.setup import StaleFolder
from modules.show_report import DeliveryHistoryEntry, ShowSnapshot


def _parsed_filename_dict(parsed: ParsedFilename) -> dict:
    return {
        "screen_prefix": parsed.screen_prefix,
        "slug": parsed.slug,
        "version": parsed.version,
        "date": parsed.date.isoformat(),
        "extension": parsed.extension,
        "is_loop": parsed.is_loop,
        "original_name": parsed.original_name,
        "show_token": parsed.show_token,
        "artist_initials": parsed.artist_initials,
    }


def _parsed_filename_from_dict(data: dict) -> ParsedFilename:
    return ParsedFilename(
        screen_prefix=data["screen_prefix"],
        slug=data["slug"],
        version=int(data["version"]),
        date=date.fromisoformat(data["date"]),
        extension=data["extension"],
        is_loop=bool(data["is_loop"]),
        original_name=data["original_name"],
        show_token=data.get("show_token"),
        artist_initials=data.get("artist_initials"),
    )


def _parse_result_from_dict(data: dict):
    kind = data.get("kind")
    if kind == "full":
        return FullMatch(_parsed_filename_from_dict(data["parsed"]))
    if kind == "partial":
        return PartialMatch(
            screen_prefix=data["screen_prefix"],
            original=data["original"],
            problems=list(data.get("problems", [])),
        )
    return NoMatch(original=data["original"], problems=list(data.get("problems", [])))


def _specs_to_dict(specs: MediaSpecs | None) -> dict | None:
    if specs is None:
        return None
    codec_id = None
    if specs.codec_tag:
        codec_id = codec_tag_to_identifier(specs.codec_tag) or specs.codec_tag
    elif specs.codec_name:
        codec_id = specs.codec_name
    return {
        "width": specs.width,
        "height": specs.height,
        "framerate": specs.framerate,
        "codec": codec_id,
        "probe_succeeded": specs.probe_succeeded,
        "probe_error": specs.probe_error,
    }


def _specs_from_dict(data: dict | None) -> MediaSpecs | None:
    if data is None:
        return None
    return MediaSpecs(
        width=data.get("width"),
        height=data.get("height"),
        framerate=data.get("framerate"),
        codec_name=data.get("codec"),
        codec_tag=None,
        color_space=None,
        color_range=None,
        audio_sample_rate=None,
        audio_channels=None,
        duration_seconds=None,
        probe_succeeded=bool(data.get("probe_succeeded", True)),
        probe_error=data.get("probe_error"),
    )


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


def _destination_label(plan: FilePlan, show_root: Path) -> str:
    try:
        rel = plan.destination_path.relative_to(show_root / "Media")
        folder = rel.parent.name if rel.parent.name else rel.parts[0] if rel.parts else ""
        return f"Media\\{folder}\\" if folder else "Media\\"
    except ValueError:
        return str(plan.destination_path.parent)


def snapshot_to_dict(snapshot: ShowSnapshot) -> dict:
    screens = {}
    for screen_id, screen in snapshot.screens.items():
        screens[screen_id] = {
            "screen_id": screen.screen_id,
            "screen_name": screen.screen_name,
            "resolution": screen.resolution,
            "parsed_files": [_parsed_filename_dict(pf) for pf in screen.parsed_files],
            "unparsed_files": list(screen.unparsed_files),
            "files": [
                {"filename": f.filename, "size_bytes": f.size_bytes}
                for f in screen.files
            ],
            "file_count": len(screen.parsed_files) + len(screen.unparsed_files),
            "slug_count": len({pf.slug for pf in screen.parsed_files}),
        }

    return {
        "show_root": str(snapshot.show_root),
        "screens": screens,
        "special_folders": snapshot.special_folders,
        "review_files": snapshot.review_files,
        "stale_folders": [
            {"name": sf.name, "path": str(sf.path), "file_count": sf.file_count}
            for sf in snapshot.stale_folders
        ],
        "multi_version_slugs": [
            {
                "label": label,
                "versions": [_parsed_filename_dict(pf) for pf in versions],
            }
            for label, versions in snapshot.multi_version_slugs
        ],
        "last_delivery": snapshot.last_delivery,
        "days_until_show": snapshot.days_until_show,
    }


def stale_folder_to_dict(sf: StaleFolder) -> dict:
    return {"name": sf.name, "path": str(sf.path), "file_count": sf.file_count}


def stale_folder_from_dict(data: dict) -> StaleFolder:
    return StaleFolder(
        name=data["name"],
        path=Path(data["path"]),
        file_count=int(data["file_count"]),
    )


def _action_name(action: Action) -> str:
    return action.name


def _action_from_name(name: str) -> Action:
    return Action[name]


def file_plan_to_dict(plan: FilePlan, show_root: Path | None = None) -> dict:
    if isinstance(plan.parsed, FullMatch):
        parsed = {"kind": "full", "parsed": _parsed_filename_dict(plan.parsed.parsed)}
    elif isinstance(plan.parsed, PartialMatch):
        parsed = {
            "kind": "partial",
            "screen_prefix": plan.parsed.screen_prefix,
            "original": plan.parsed.original,
            "problems": plan.parsed.problems,
        }
    else:
        parsed = {
            "kind": "none",
            "original": plan.parsed.original,
            "problems": plan.parsed.problems,
        }

    version_conflict = None
    if plan.version_conflict is not None:
        version_conflict = {
            "existing_versions": [
                _parsed_filename_dict(pf) for pf in plan.version_conflict.existing_versions
            ],
            "incoming_version": plan.version_conflict.incoming_version,
        }

    size_bytes = plan.source_path.stat().st_size if plan.source_path.exists() else 0

    return {
        "filename": plan.source_path.name,
        "source_path": str(plan.source_path),
        "parsed": parsed,
        "specs": _specs_to_dict(plan.specs),
        "spec_status": _spec_status(plan.warnings, plan.failures),
        "size_bytes": size_bytes,
        "target_screen": plan.target_screen,
        "destination_path": str(plan.destination_path),
        "destination_label": _destination_label(plan, show_root) if show_root else "",
        "action": _action_name(plan.action),
        "warnings": plan.warnings,
        "failures": plan.failures,
        "version_conflict": version_conflict,
    }


def file_plan_from_dict(data: dict) -> FilePlan:
    version_conflict = None
    if data.get("version_conflict"):
        vc = data["version_conflict"]
        version_conflict = ConflictInfo(
            existing_versions=[
                _parsed_filename_from_dict(pf) for pf in vc["existing_versions"]
            ],
            incoming_version=int(vc["incoming_version"]),
        )

    return FilePlan(
        source_path=Path(data["source_path"]),
        parsed=_parse_result_from_dict(data["parsed"]),
        specs=_specs_from_dict(data.get("specs")),
        target_screen=data.get("target_screen"),
        destination_path=Path(data["destination_path"]),
        action=_action_from_name(data["action"]),
        warnings=list(data.get("warnings", [])),
        failures=list(data.get("failures", [])),
        version_conflict=version_conflict,
    )


def execution_result_to_dict(result: ExecutionResult) -> dict:
    return {
        "copied": [str(p) for p in result.copied],
        "skipped": [str(p) for p in result.skipped],
        "routed_to_review": [str(p) for p in result.routed_to_review],
        "copy_failures": [
            {"source_path": str(src), "reason": reason}
            for src, reason in result.copy_failures
        ],
    }


def intake_scan_result_to_dict(
    plans: list[FilePlan],
    stale_folders: list[StaleFolder],
    show_root: Path,
    source_path: Path,
    *,
    intake_mode: str = "routed",
) -> dict:
    return {
        "show_path": str(show_root),
        "source_path": str(source_path),
        "intake_mode": intake_mode,
        "plans": [file_plan_to_dict(p, show_root) for p in plans],
        "stale_folders": [stale_folder_to_dict(sf) for sf in stale_folders],
    }


def delivery_history_entry_to_dict(entry: DeliveryHistoryEntry) -> dict:
    return {
        "timestamp": entry.timestamp,
        "source_path": entry.source_path,
        "copied": entry.copied,
        "review": entry.review,
        "skip": entry.skip,
        "notes": entry.notes,
        "intake_log_path": entry.intake_log_path,
    }
