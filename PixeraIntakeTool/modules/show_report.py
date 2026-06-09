"""'What's in my show' reporting mode."""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from colorama import Fore, Style

from modules.config import ShowConfig
from modules.console_ui import print_blank, print_subheader, print_warning
from modules.filename_parser import FullMatch, ParsedFilename, parse_filename
from modules.setup import StaleFolder, detect_stale_folders


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScreenSnapshot:
    """Catalogued content for one configured screen folder."""
    screen_id:      str
    screen_name:    str
    resolution:     str | None
    parsed_files:   list[ParsedFilename] = field(default_factory=list)
    unparsed_files: list[str]            = field(default_factory=list)


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
_SEP_WIDTH = 70


def _is_special_folder(name: str) -> bool:
    return any(name == sp or name.startswith(sp + "-") for sp in _SPECIAL_PREFIXES)


def _walk_filenames(folder: Path) -> list[str]:
    """Return sorted filenames (files only, non-recursive) in folder."""
    if not folder.exists():
        return []
    return sorted(f.name for f in folder.iterdir() if f.is_file())


def _parse_folder(folder: Path) -> tuple[list[ParsedFilename], list[str]]:
    """Parse all files in folder; return (fully-parsed list, unparsed filenames)."""
    parsed:   list[ParsedFilename] = []
    unparsed: list[str]            = []
    for name in _walk_filenames(folder):
        result = parse_filename(name)
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


def _read_last_delivery(show_root: Path) -> str | None:
    """Parse the last line of DeliveryLog.txt into a readable summary, or None."""
    log_path = show_root / "Media" / "_LOGS" / "DeliveryLog.txt"
    if not log_path.exists():
        return None
    try:
        lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if not lines:
            return None
        parts = [p.strip() for p in lines[-1].split("|")]
        # Format: "YYYY-MM-DD HH:MM | source | N copied, N review, N skip | Notes: ..."
        if len(parts) >= 3:
            return f"{parts[0]} ({parts[2]})"
        return parts[0] if parts else None
    except OSError:
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
        parsed, unparsed = _parse_folder(media_dir / screen_cfg.id)
        screens[screen_cfg.id] = ScreenSnapshot(
            screen_id=screen_cfg.id,
            screen_name=screen_cfg.name,
            resolution=screen_cfg.resolution,
            parsed_files=parsed,
            unparsed_files=unparsed,
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


# ---------------------------------------------------------------------------
# Report display
# ---------------------------------------------------------------------------

def display_report(snapshot: ShowSnapshot, config: ShowConfig) -> None:
    """Render the full show content report to the console."""
    sep = "=" * _SEP_WIDTH
    print(f"{Style.BRIGHT}{sep}")
    print(f"  SHOW: {config.show_name}  ({config.show_date})")
    print(f"  Path: {snapshot.show_root}")
    print(f"{sep}{Style.RESET_ALL}")
    print_blank()

    # Screens section
    print(f"Screens configured: {len(config.screens)}")
    for screen_cfg in config.screens:
        snap      = snapshot.screens.get(screen_cfg.id)
        n_files   = (len(snap.parsed_files) + len(snap.unparsed_files)) if snap else 0
        n_slugs   = len({pf.slug for pf in snap.parsed_files}) if snap else 0
        name_col  = f"{screen_cfg.name:<14}  " if screen_cfg.name else ""
        res_col   = f"({screen_cfg.resolution})  " if screen_cfg.resolution else ""
        f_word    = "file"        if n_files  == 1 else "files"
        s_word    = "unique slug" if n_slugs  == 1 else "unique slugs"
        print(f"  {screen_cfg.id}  {name_col}{res_col}— {n_files} {f_word}, {n_slugs} {s_word}")
    print_blank()

    # Special folders section
    if snapshot.special_folders:
        print("Special folders:")
        for folder_name, filenames in sorted(snapshot.special_folders.items()):
            count  = len(filenames)
            f_word = "file" if count == 1 else "files"
            print(f"  {folder_name:<12}— {count} {f_word}")
        print_blank()

    # Totals
    total_screen  = sum(len(s.parsed_files) + len(s.unparsed_files) for s in snapshot.screens.values())
    total_special = sum(len(f) for f in snapshot.special_folders.values())
    total_files   = total_screen + total_special
    all_slugs     = {pf.slug for s in snapshot.screens.values() for pf in s.parsed_files}
    n_slugs       = len(all_slugs)
    f_word = "file"        if total_files == 1 else "files"
    s_word = "unique slug" if n_slugs     == 1 else "unique slugs"
    print(f"Total content: {total_files} {f_word} across {n_slugs} {s_word}")
    print_blank()

    # Multi-version slugs
    if snapshot.multi_version_slugs:
        print(f"{Style.BRIGHT}Slugs with multiple versions present:{Style.RESET_ALL}")
        max_len = max(len(label) for label, _ in snapshot.multi_version_slugs)
        for label, versions in snapshot.multi_version_slugs:
            ver_parts = ", ".join(
                f"v{pf.version:02d} ({pf.date.isoformat()})" for pf in versions
            )
            print(f"  {label:{max_len}}:  {ver_parts}")
        print_blank()

    # _REVIEW files
    review_count = len(snapshot.review_files)
    if review_count > 0:
        print(f"{Fore.YELLOW}Files in _REVIEW: {review_count}{Style.RESET_ALL}")
        for filename in snapshot.review_files:
            print(f"  {filename}")
    else:
        print("Files in _REVIEW: 0")
    print_blank()

    # Last delivery
    last_line = snapshot.last_delivery or "(no deliveries recorded)"
    print(f"Last delivery: {last_line}")

    # Days until show
    if snapshot.days_until_show is not None:
        days = snapshot.days_until_show
        if days < 0:
            print(f"Show date: {config.show_date} ({abs(days)} day{'s' if abs(days) != 1 else ''} ago)")
        elif days == 0:
            print(f"{Fore.YELLOW}{Style.BRIGHT}Days until show: TODAY{Style.RESET_ALL}")
        elif days <= 7:
            print(f"{Fore.YELLOW}{Style.BRIGHT}Days until show: {days}{Style.RESET_ALL}")
        else:
            print(f"Days until show: {days}")
    print_blank()

    # Stale folders (surfaced at the end per DESIGN §10.3)
    if snapshot.stale_folders:
        print_subheader("STALE FOLDERS")
        print_blank()
        for sf in snapshot.stale_folders:
            count  = sf.file_count
            f_word = "file" if count == 1 else "files"
            print_warning(f"Media\\{sf.name}\\ ({count} {f_word}) — not in config")
        print_blank()


def run_report(show_root: Path, config: ShowConfig) -> None:
    """Gather and display the show content report. No interactive prompts."""
    print_blank()
    snapshot = gather_snapshot(show_root, config)
    display_report(snapshot, config)
