"""'What's in my show' reporting mode."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from modules.config import ShowConfig
from modules.filename_parser import FullMatch, ParsedFilename, parse_filename
from modules.setup import StaleFolder, detect_stale_folders


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MediaFileEntry:
    """A file on disk in a screen folder (filesystem metadata only)."""
    filename:   str
    size_bytes: int


@dataclass
class ScreenSnapshot:
    """Catalogued content for one configured screen folder."""
    screen_id:      str
    screen_name:    str
    resolution:     str | None
    parsed_files:   list[ParsedFilename] = field(default_factory=list)
    unparsed_files: list[str]            = field(default_factory=list)
    files:          list[MediaFileEntry] = field(default_factory=list)


@dataclass
class ShowSnapshot:
    """Full content snapshot of a show's Media folder."""
    show_root:           Path
    screens:             dict[str, ScreenSnapshot]          # screen_id → snapshot
    special_folders:     dict[str, list[str]]               # folder_name → filenames
    review_files:        list[str]
    stale_folders:       list[StaleFolder]
    multi_version_slugs: list[tuple[str, list[ParsedFilename]]]  # label → sorted versions
    last_delivery:       str | None
    days_until_show:     int | None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SPECIAL_PREFIXES = ("SCRwide", "SCRall", "AUD")


def _is_special_folder(name: str) -> bool:
    return any(name == sp or name.startswith(sp + "-") for sp in _SPECIAL_PREFIXES)


def _walk_filenames(folder: Path) -> list[str]:
    """Return sorted filenames (files only, non-recursive) in folder."""
    if not folder.exists():
        return []
    return sorted(f.name for f in folder.iterdir() if f.is_file())


def _list_folder_files(folder: Path) -> list[MediaFileEntry]:
    """Return sorted file entries (name + size) for files in folder."""
    if not folder.exists():
        return []
    entries: list[MediaFileEntry] = []
    for entry in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if entry.is_file():
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            entries.append(MediaFileEntry(filename=entry.name, size_bytes=size))
    return entries


def _parse_folder(folder: Path, config: ShowConfig) -> tuple[list[ParsedFilename], list[str]]:
    """Parse all files in folder; return (fully-parsed list, unparsed filenames)."""
    parsed:   list[ParsedFilename] = []
    unparsed: list[str]            = []
    for name in _walk_filenames(folder):
        result = parse_filename(name, config)
        if isinstance(result, FullMatch):
            parsed.append(result.parsed)
        else:
            unparsed.append(name)
    return parsed, unparsed


def _detect_multi_version_slugs(
    screens: dict[str, ScreenSnapshot],
) -> list[tuple[str, list[ParsedFilename]]]:
    """Find per-screen slugs present in more than one version.

    Returns a sorted list of (label, versions) where label is
    '<screen_prefix>_<slug>' and versions are sorted by version number.
    """
    groups: dict[str, list[ParsedFilename]] = {}
    for snap in screens.values():
        for pf in snap.parsed_files:
            key = f"{pf.screen_prefix}_{pf.slug}"
            groups.setdefault(key, []).append(pf)

    return [
        (label, sorted(versions, key=lambda x: x.version))
        for label, versions in sorted(groups.items())
        if len(versions) > 1
    ]


def read_delivery_log(show_root: Path) -> list[str]:
    """Return non-empty lines from DeliveryLog.txt, oldest first."""
    log_path = show_root / "Media" / "_LOGS" / "DeliveryLog.txt"
    if not log_path.exists():
        return []
    try:
        return [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        return []


@dataclass
class DeliveryHistoryEntry:
    """One parsed row from DeliveryLog.txt."""
    timestamp: str
    source_path: str
    copied: int
    review: int
    skip: int
    notes: str | None
    intake_log_path: str | None


_STATS_RE = re.compile(
    r"(\d+)\s+copied,\s*(\d+)\s+review,\s*(\d+)\s+skip",
    re.IGNORECASE,
)


def _parse_delivery_stats(stats: str) -> tuple[int, int, int]:
    match = _STATS_RE.search(stats)
    if not match:
        return 0, 0, 0
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def _is_intake_log_segment(segment: str) -> bool:
    name = Path(segment.strip()).name
    return name.startswith("intake_") and name.endswith(".txt")


def _delivery_timestamp(segment: str) -> datetime | None:
    try:
        return datetime.strptime(segment.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def _intake_log_timestamp(path: Path) -> datetime | None:
    stem = path.stem
    if not stem.startswith("intake_"):
        return None
    try:
        return datetime.strptime(stem[7:], "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def _list_intake_logs(show_root: Path) -> list[Path]:
    logs_dir = show_root / "Media" / "_LOGS"
    if not logs_dir.exists():
        return []
    return sorted(logs_dir.glob("intake_*.txt"), key=lambda p: p.name.lower())


def _match_intake_log(
    delivery_ts: datetime | None,
    candidates: list[Path],
    used: set[Path],
) -> Path | None:
    if delivery_ts is None:
        return None
    best: Path | None = None
    best_delta: float | None = None
    for candidate in candidates:
        if candidate in used:
            continue
        intake_ts = _intake_log_timestamp(candidate)
        if intake_ts is None:
            continue
        delta = abs((intake_ts - delivery_ts).total_seconds())
        if delta > 180:
            continue
        if best is None or delta < best_delta:
            best = candidate
            best_delta = delta
    return best


def _parse_delivery_line(line: str) -> DeliveryHistoryEntry | None:
    parts = [part.strip() for part in line.split("|")]
    if len(parts) < 3:
        return None

    copied, review, skip = _parse_delivery_stats(parts[2])
    intake_log_path: str | None = None
    notes: str | None = None

    for segment in parts[3:]:
        if segment.startswith("Notes:"):
            note_text = segment[6:].strip()
            if note_text and note_text.lower() != "none":
                notes = note_text
        elif _is_intake_log_segment(segment):
            intake_log_path = segment

    return DeliveryHistoryEntry(
        timestamp=parts[0],
        source_path=parts[1],
        copied=copied,
        review=review,
        skip=skip,
        notes=notes,
        intake_log_path=intake_log_path,
    )


def parse_delivery_history(show_root: Path) -> list[DeliveryHistoryEntry]:
    """Return structured delivery log entries, oldest first."""
    lines = read_delivery_log(show_root)
    if not lines:
        return []

    intake_logs = _list_intake_logs(show_root)
    used_intake_logs: set[Path] = set()
    entries: list[DeliveryHistoryEntry] = []

    for line in lines:
        entry = _parse_delivery_line(line)
        if entry is None:
            continue

        if entry.intake_log_path:
            resolved = Path(entry.intake_log_path)
            if not resolved.is_absolute():
                resolved = show_root / "Media" / "_LOGS" / resolved.name
            if resolved.exists():
                entry.intake_log_path = str(resolved)
                used_intake_logs.add(resolved)
        else:
            matched = _match_intake_log(
                _delivery_timestamp(entry.timestamp),
                intake_logs,
                used_intake_logs,
            )
            if matched is not None:
                entry.intake_log_path = str(matched)
                used_intake_logs.add(matched)

        entries.append(entry)

    return entries


def resolve_intake_log_path(show_root: Path, log_path: str) -> Path:
    """Resolve an intake log path and ensure it stays under Media/_LOGS."""
    logs_dir = (show_root / "Media" / "_LOGS").resolve()
    candidate = Path(log_path)
    if not candidate.is_absolute():
        candidate = logs_dir / candidate.name

    resolved = candidate.resolve()
    if not str(resolved).startswith(str(logs_dir)):
        raise ValueError("Intake log path is outside the show logs folder")
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    if not resolved.name.startswith("intake_") or resolved.suffix.lower() != ".txt":
        raise ValueError("Not an intake log file")
    return resolved


def read_intake_log_content(show_root: Path, log_path: str) -> str:
    """Read a validated intake transcript from Media/_LOGS."""
    resolved = resolve_intake_log_path(show_root, log_path)
    return resolved.read_text(encoding="utf-8")


def _read_last_delivery(show_root: Path) -> str | None:
    """Parse the last line of DeliveryLog.txt into a readable summary, or None."""
    lines = read_delivery_log(show_root)
    if not lines:
        return None
    try:
        parts = [p.strip() for p in lines[-1].split("|")]
        # Format: "YYYY-MM-DD HH:MM | source | N copied, N review, N skip | Notes: ..."
        if len(parts) >= 3:
            return f"{parts[0]} ({parts[2]})"
        return parts[0] if parts else None
    except (IndexError, AttributeError):
        return None


def _days_until_show(show_date_str: str) -> int | None:
    """Return days until show date (negative = past). None on parse error."""
    try:
        return (date.fromisoformat(show_date_str) - date.today()).days
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Snapshot gathering
# ---------------------------------------------------------------------------

def gather_snapshot(show_root: Path, config: ShowConfig) -> ShowSnapshot:
    """Build a complete content snapshot for the show's Media folder."""
    media_dir = show_root / "Media"

    screens: dict[str, ScreenSnapshot] = {}
    for screen_cfg in config.screens:
        screen_folder = media_dir / screen_cfg.id
        parsed, unparsed = _parse_folder(screen_folder, config)
        screens[screen_cfg.id] = ScreenSnapshot(
            screen_id=screen_cfg.id,
            screen_name=screen_cfg.name,
            resolution=screen_cfg.resolution,
            parsed_files=parsed,
            unparsed_files=unparsed,
            files=_list_folder_files(screen_folder),
        )

    special_folders: dict[str, list[str]] = {}
    if media_dir.exists():
        for entry in sorted(media_dir.iterdir()):
            if entry.is_dir() and _is_special_folder(entry.name):
                special_folders[entry.name] = _walk_filenames(entry)

    return ShowSnapshot(
        show_root=show_root,
        screens=screens,
        special_folders=special_folders,
        review_files=_walk_filenames(media_dir / "_REVIEW"),
        stale_folders=detect_stale_folders(show_root, config),
        multi_version_slugs=_detect_multi_version_slugs(screens),
        last_delivery=_read_last_delivery(show_root),
        days_until_show=_days_until_show(config.show_date),
    )
