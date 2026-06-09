"""Recent shows menu and .recent_shows.json memory."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from colorama import Style

from modules.console_ui import format_relative_time, print_warning, print_blank

_FILENAME    = ".recent_shows.json"
_MAX_ENTRIES = 5


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class RecentShow:
    """A single entry in the recent shows list."""
    path:      Path
    show_name: str
    last_used: datetime


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_recent_shows(tool_root: Path) -> list[RecentShow]:
    """Load recent shows from disk, drop stale entries, return sorted by last_used desc."""
    file = tool_root / _FILENAME
    if not file.exists():
        return []

    try:
        data = json.loads(file.read_text(encoding="utf-8"))
        raw_entries = data.get("shows", [])
    except (json.JSONDecodeError, OSError):
        return []

    shows: list[RecentShow] = []
    for entry in raw_entries:
        try:
            path      = Path(entry["path"])
            show_name = entry["show_name"]
            last_used = datetime.fromisoformat(entry["last_used"])
        except (KeyError, ValueError):
            continue

        # Self-clean: drop entries whose show_config.json no longer exists
        if not (path / "show_config.json").exists():
            continue

        shows.append(RecentShow(path=path, show_name=show_name, last_used=last_used))

    shows.sort(key=lambda s: s.last_used, reverse=True)
    return shows


def save_recent_shows(tool_root: Path, shows: list[RecentShow]) -> None:
    """Write up to 5 most-recent shows to .recent_shows.json."""
    entries = [
        {
            "path":      str(s.path),
            "show_name": s.show_name,
            "last_used": s.last_used.isoformat(timespec="seconds"),
        }
        for s in shows[:_MAX_ENTRIES]
    ]
    file = tool_root / _FILENAME
    file.write_text(
        json.dumps({"shows": entries}, indent=2),
        encoding="utf-8",
    )


def add_or_update(tool_root: Path, show_path: Path, show_name: str) -> None:
    """Add a show to the recent list (or update its last_used if already present)."""
    shows = load_recent_shows(tool_root)

    # Remove existing entry for this path (if any) so we can re-insert at top
    shows = [s for s in shows if s.path != show_path]
    shows.insert(0, RecentShow(path=show_path, show_name=show_name, last_used=datetime.now()))
    shows.sort(key=lambda s: s.last_used, reverse=True)

    save_recent_shows(tool_root, shows)


# ---------------------------------------------------------------------------
# Launch menu
# ---------------------------------------------------------------------------

def display_menu_and_get_selection(shows: list[RecentShow]) -> Path | None:
    """Print the launch menu and return the selected show path.

    Returns:
        Path  — a numbered show was chosen.
        None  — user chose N or pressed Enter (caller opens folder picker).
    Raises:
        SystemExit — user chose Q.
    """
    if shows:
        print(f"{Style.BRIGHT}  Recent shows:{Style.RESET_ALL}")
        for i, show in enumerate(shows, start=1):
            rel = format_relative_time(show.last_used)
            print(f"    {i})  {show.show_name}    (last used {rel})")
        print_blank()

    print(f"  {Style.BRIGHT}[N]{Style.RESET_ALL}  Pick a different show folder")
    print(f"  {Style.BRIGHT} Q {Style.RESET_ALL}  Quit")
    print_blank()

    valid_numbers = {str(i) for i in range(1, len(shows) + 1)}

    while True:
        raw = input(f"{Style.BRIGHT}  Selection [N]: {Style.RESET_ALL}").strip().upper()

        if raw == "" or raw == "N":
            return None

        if raw == "Q":
            raise SystemExit(0)

        if raw in valid_numbers:
            return shows[int(raw) - 1].path

        choices = ", ".join(sorted(valid_numbers) + ["N", "Q"])
        print_warning(f"Invalid selection. Choose from: {choices}")
