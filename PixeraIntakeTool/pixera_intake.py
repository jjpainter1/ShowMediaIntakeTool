"""Pixera Intake Tool — main entry point."""

import sys
import traceback
from pathlib import Path

from colorama import Style

from modules.config import ShowConfig
from modules.console_ui import (
    pick_folder,
    print_blank,
    print_error,
    print_header,
    print_info,
    print_path,
    print_success,
    print_warning,
    prompt_menu,
)
from modules.ffprobe_wrapper import check_ffprobe_available
from modules.intake import run_intake
from modules.recent_shows import add_or_update, display_menu_and_get_selection, load_recent_shows
from modules.setup import ensure_media_structure, load_config_with_retry, setup_new_show
from modules.show_report import run_report
from modules.spec_generator import generate_spec

VERSION    = "1.0"
_SEP_WIDTH = 70


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Top-level entry point with crash guard."""
    try:
        _run()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print_blank()
        print_info("Interrupted.")
        sys.exit(0)
    except Exception:
        print_blank()
        print_error("An unexpected error occurred:")
        traceback.print_exc()
        sys.exit(1)


# ---------------------------------------------------------------------------
# Application loop
# ---------------------------------------------------------------------------

def _run() -> None:
    """Main flow: startup checks → launch menu → show load → main menu (loops)."""
    tool_root = Path(__file__).parent

    if not check_ffprobe_available():
        print_blank()
        print_error(
            "ffprobe not found on PATH. "
            "Install ffmpeg and ensure ffprobe is accessible, then restart."
        )
        sys.exit(1)

    while True:
        show_root = _run_launch_menu(tool_root)
        if show_root is None:
            continue  # folder picker cancelled — loop back to launch menu

        config = _load_show(show_root)
        if config is None:
            continue  # setup declined or config aborted — loop back

        created = ensure_media_structure(show_root, config)
        for name in created:
            print_info(f"Created folder: {name}/")

        add_or_update(tool_root, show_root, config.show_name)
        _run_main_menu(show_root, config)
        # Returns here when the user selects "Switch show" — loop back to launch menu


# ---------------------------------------------------------------------------
# Launch menu
# ---------------------------------------------------------------------------

def _run_launch_menu(tool_root: Path) -> Path | None:
    """Show the recent-shows launch menu. Returns chosen show path, or None if cancelled."""
    recent = load_recent_shows(tool_root)
    print_blank()
    print_header(f"PIXERA INTAKE TOOL  v{VERSION}  By JJ Painter")

    selected = display_menu_and_get_selection(recent)  # raises SystemExit on Q

    if selected is not None:
        return selected  # numbered recent show chosen

    # "N" — open folder picker
    print_blank()
    print("  Select the show project folder.")
    folder = pick_folder("Select show project folder")
    if folder is None:
        print_warning("No folder selected.")
        return None

    if not folder.is_dir():
        print_error(f"Not a valid folder: {folder}")
        return None

    return folder


# ---------------------------------------------------------------------------
# Show loading
# ---------------------------------------------------------------------------

def _load_show(show_root: Path) -> ShowConfig | None:
    """Load (or first-time set up) the show config. Returns None if aborted."""
    config_path = show_root / "show_config.json"

    if not config_path.exists():
        if not setup_new_show(show_root):
            return None  # operator declined setup

    return load_config_with_retry(show_root)  # loops on errors until valid or Ctrl+C


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def _run_main_menu(show_root: Path, config: ShowConfig) -> None:
    """Loop the main menu. Returns when user picks Switch; raises SystemExit on Quit."""
    while True:
        _print_show_header(show_root, config)
        choice = prompt_menu({
            "1": "Intake new content delivery",
            "2": "Generate spec document",
            "3": 'Show "what\'s in my show" report',
            "4": "Switch to a different show",
            "Q": "Quit",
        })

        if choice == "1":
            run_intake(show_root, config)
        elif choice == "2":
            _run_spec(show_root, config)
        elif choice == "3":
            run_report(show_root, config)
        elif choice == "4":
            return  # caller loops back to launch menu
        elif choice == "Q":
            raise SystemExit(0)


def _print_show_header(show_root: Path, config: ShowConfig) -> None:
    """Print the two-line show identity header (DESIGN.md §13)."""
    sep = "=" * _SEP_WIDTH
    print_blank()
    print(f"{Style.BRIGHT}{sep}")
    print(f"  SHOW: {config.show_name}  ({config.show_date})")
    print(f"  Path: {show_root}")
    print(f"{sep}{Style.RESET_ALL}")
    print_blank()


# ---------------------------------------------------------------------------
# Spec generation wrapper
# ---------------------------------------------------------------------------

def _run_spec(show_root: Path, config: ShowConfig) -> None:
    """Generate the spec docx and report the output path to the operator."""
    print_blank()
    try:
        output_path = generate_spec(show_root, config)
        print_success("Spec document generated.")
        print_path(str(output_path))
    except Exception as exc:
        print_error(f"Spec generation failed: {exc}")
    print_blank()


if __name__ == "__main__":
    main()
