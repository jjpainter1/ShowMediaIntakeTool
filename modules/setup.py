"""Show setup, folder reconciliation, and config retry loop."""

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from modules.config import (
    ShowConfig,
    ConfigError,
    ConfigNotFoundError,
    ConfigInvalidError,
    FILENAME_SAFE,
    load_config,
    create_starter_config,
    validate_config,
)
from modules.console_ui import (
    print_header,
    print_success,
    print_warning,
    print_error,
    print_path,
    print_blank,
    prompt_yes_no,
)

# Folders inside Media/ that are always valid and never stale
_MANAGED_FOLDERS  = {"_LOGS", "_REVIEW", "_REFERENCE"}
# Special on-demand content folders that are valid even if not in config
_SPECIAL_PREFIXES = ("SCRwide", "SCRall", "AUD")


# ---------------------------------------------------------------------------
# Editor helpers
# ---------------------------------------------------------------------------

def find_notepad_pp() -> Path | None:
    """Return the Notepad++ executable path if installed, else None."""
    npp = Path("C:/Program Files/Notepad++/notepad++.exe")
    return npp if npp.exists() else None


def open_in_explorer(path: Path) -> bool:
    """Open a folder in File Explorer, or reveal a file with /select."""
    try:
        resolved = path.resolve()
    except OSError:
        return False

    if not resolved.exists():
        return False

    try:
        if resolved.is_dir():
            os.startfile(str(resolved))
            return True
        subprocess.Popen(["explorer", "/select,", str(resolved)])
        return True
    except OSError:
        return False


def open_in_editor(file_path: Path) -> bool:
    """Open file_path in Notepad++ (non-blocking) or fall back to os.startfile.

    Always prints the file path to console. Returns True if the open call
    succeeded (does not mean the file was actually edited).
    """
    print_blank()
    print("  Config file location:")
    print_path(str(file_path))
    print_blank()

    npp = find_notepad_pp()
    if npp:
        try:
            subprocess.Popen([str(npp), str(file_path)])
            return True
        except OSError:
            pass  # fall through to os.startfile

    try:
        os.startfile(str(file_path))
        return True
    except OSError as exc:
        print_warning(f"Could not open editor automatically: {exc}")
        print_warning("Please open the file manually using the path shown above.")
        return False


# ---------------------------------------------------------------------------
# Setup mode
# ---------------------------------------------------------------------------

def show_folder_name(show_name: str, show_date: str) -> str:
    """Build the on-disk folder name: ShowName_YYYYMMDD."""
    name = show_name.strip()
    if not FILENAME_SAFE.match(name):
        raise ConfigError(
            f"Show name '{name}' contains invalid characters. "
            "Only letters, digits, hyphens, and underscores are allowed."
        )
    try:
        parsed = date.fromisoformat(show_date)
    except ValueError as exc:
        raise ConfigError(f"Invalid show date: '{show_date}'") from exc
    return f"{name}_{parsed.strftime('%Y%m%d')}"


def _finalize_starter_config(config_path: Path, show_name: str, show_date: str) -> None:
    """Replace template placeholders so the starter config passes validation."""
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    data["show_name"] = show_name.strip()
    data["show_date"] = show_date

    for screen in data.get("screens", []):
        if isinstance(screen, dict):
            if str(screen.get("name", "")).startswith("REPLACE"):
                screen["name"] = ""
            res = str(screen.get("resolution", "") or "")
            if res.startswith("REPLACE") or (res and not re.fullmatch(r"\d+x\d+", res)):
                screen["resolution"] = ""

    config_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def create_new_show(parent_path: Path, show_name: str, show_date: str) -> Path:
    """Create a new show folder with Media skeleton and starter config."""
    if not parent_path.is_dir():
        raise ConfigError(f"Parent folder not found: {parent_path}")

    folder_name = show_folder_name(show_name, show_date)
    show_root = parent_path / folder_name
    if show_root.exists():
        raise ConfigError(
            f"A show folder with this name already exists at: {show_root}"
        )

    for subdir in ("Media", "Media/_LOGS", "Media/_REVIEW", "Media/_REFERENCE"):
        (show_root / subdir).mkdir(parents=True)

    config_path = create_starter_config(show_root)
    _finalize_starter_config(config_path, show_name, show_date)
    try:
        validate_config(json.loads(config_path.read_text(encoding="utf-8")))
    except ConfigInvalidError as exc:
        raise ConfigError(str(exc)) from exc
    return show_root


def setup_new_show(show_root: Path) -> bool:
    """Run first-time setup for a new show project root.

    Creates the Media folder skeleton and starter config, then opens the
    config in an editor so the operator can fill it in.

    Returns True if the starter config was created (caller should then
    load and validate), False if the operator declined.
    """
    if not show_root.exists() or not show_root.is_dir():
        print_error(f"Show root does not exist or is not a folder: {show_root}")
        return False

    print_blank()
    print_warning("No show_config.json found in this folder.")
    if not prompt_yes_no("Create a starter config here?", default="N"):
        return False

    # Create base Media structure (no screen folders yet — those come from config)
    for subdir in ("Media", "Media/_LOGS", "Media/_REVIEW", "Media/_REFERENCE"):
        (show_root / subdir).mkdir(parents=True, exist_ok=True)

    config_path = create_starter_config(show_root)
    print_success("Starter config created.")

    open_in_editor(config_path)
    input("  Edit and save the config, then press Enter to continue...")
    print_blank()

    return True


# ---------------------------------------------------------------------------
# Folder reconciliation
# ---------------------------------------------------------------------------

def ensure_media_structure(show_root: Path, config: ShowConfig) -> list[str]:
    """Create any missing Media subfolders. Returns a list of created folder names."""
    created: list[str] = []

    base_dirs = [
        show_root / "Media",
        show_root / "Media" / "_LOGS",
        show_root / "Media" / "_REVIEW",
        show_root / "Media" / "_REFERENCE",
    ]
    for d in base_dirs:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(d.name)

    for screen in config.screens:
        screen_dir = show_root / "Media" / screen.id
        if not screen_dir.exists():
            screen_dir.mkdir(parents=True, exist_ok=True)
            created.append(screen.id)

    return created


@dataclass
class StaleFolder:
    """A Media subfolder not accounted for by the current config."""
    name:       str
    path:       Path
    file_count: int


def detect_stale_folders(show_root: Path, config: ShowConfig) -> list[StaleFolder]:
    """Return Media subfolders that are not managed, not in config, and not special prefixes."""
    media_dir = show_root / "Media"
    if not media_dir.exists():
        return []

    config_screen_ids = {s.id for s in config.screens}
    stale: list[StaleFolder] = []

    for entry in sorted(media_dir.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        if name in _MANAGED_FOLDERS:
            continue
        if name in config_screen_ids:
            continue
        if any(name == sp or name.startswith(sp + "-") for sp in _SPECIAL_PREFIXES):
            continue
        file_count = sum(1 for f in entry.rglob("*") if f.is_file())
        stale.append(StaleFolder(name=name, path=entry, file_count=file_count))

    return stale


# ---------------------------------------------------------------------------
# Config load with retry loop
# ---------------------------------------------------------------------------

def load_config_with_retry(show_root: Path) -> ShowConfig | None:
    """Attempt to load and validate the show config, retrying after editor on failure.

    Returns the validated ShowConfig, or None if the user aborts with Ctrl+C.
    Loops until the config is valid.
    """
    config_path = show_root / "show_config.json"

    while True:
        try:
            return load_config(show_root)
        except ConfigNotFoundError:
            print_error("show_config.json not found. Run setup first.")
            return None
        except ConfigInvalidError as exc:
            print_blank()
            print_error(f"Config validation failed: {exc}")
            print_blank()
            try:
                input("  Fix the error, save, then press Enter to retry (Ctrl+C to abort)...")
            except KeyboardInterrupt:
                print_blank()
                return None
            open_in_editor(config_path)
            print_blank()
        except ConfigError as exc:
            print_error(f"Config error: {exc}")
            return None
