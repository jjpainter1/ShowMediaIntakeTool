"""Console output formatting: colors, tables, separators, and input prompts."""

from datetime import datetime
from pathlib import Path

from colorama import Fore, Style, init as _colorama_init

_colorama_init(autoreset=True)

_SEP_WIDTH = 70


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def print_header(text: str) -> None:
    """Bold section header surrounded by = separator lines."""
    sep = "=" * _SEP_WIDTH
    print(f"{Style.BRIGHT}{sep}")
    print(f"  {text}")
    print(f"{sep}{Style.RESET_ALL}")


def print_subheader(text: str) -> None:
    """Bold subsection label followed by a - separator line."""
    sep = "-" * _SEP_WIDTH
    print(f"{Style.BRIGHT}  {text}")
    print(f"{sep}{Style.RESET_ALL}")


def print_success(text: str) -> None:
    """Green line with a checkmark prefix."""
    print(f"{Fore.GREEN}  ✓ {text}{Style.RESET_ALL}")


def print_warning(text: str) -> None:
    """Yellow line with a warning prefix."""
    print(f"{Fore.YELLOW}  ⚠ {text}{Style.RESET_ALL}")


def print_error(text: str) -> None:
    """Red line with a cross prefix."""
    print(f"{Fore.RED}  ✗ {text}{Style.RESET_ALL}")


def print_info(text: str) -> None:
    """Dim cyan line with a bullet prefix."""
    print(f"{Fore.CYAN}{Style.DIM}  • {text}{Style.RESET_ALL}")


def print_path(text: str) -> None:
    """Bright white line — used for file/folder paths."""
    print(f"{Style.BRIGHT}{Fore.WHITE}  {text}{Style.RESET_ALL}")


def print_separator(char: str = "=") -> None:
    """Print a plain separator line."""
    print(char * _SEP_WIDTH)


def print_blank() -> None:
    """Print an empty line."""
    print()


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

def format_filesize(num_bytes: int) -> str:
    """Return a human-friendly file size string (e.g. '1.2 GB', '685 MB')."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024 or unit == "TB":
            if unit == "B":
                return f"{num_bytes} B"
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024  # type: ignore[assignment]
    return f"{num_bytes:.1f} TB"  # unreachable but satisfies type checker


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    """Return a plain-text aligned table string."""
    all_rows = [headers] + rows
    col_widths = [
        max(len(str(row[i])) for row in all_rows if i < len(row))
        for i in range(len(headers))
    ]
    sep = "  ".join("-" * w for w in col_widths)
    lines: list[str] = []
    lines.append("  " + "  ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers)))
    lines.append("  " + sep)
    for row in rows:
        lines.append("  " + "  ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(row)))
    return "\n".join(lines)


def format_relative_time(dt: datetime) -> str:
    """Return a human-friendly relative time string like '2 days ago'."""
    delta = datetime.now() - dt
    seconds = int(delta.total_seconds())

    if seconds < 0:
        return "just now"
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        m = seconds // 60
        return f"{m} minute{'s' if m != 1 else ''} ago"
    if seconds < 86400:
        h = seconds // 3600
        return f"{h} hour{'s' if h != 1 else ''} ago"
    if seconds < 172800:
        return "yesterday"
    if seconds < 604800:
        d = seconds // 86400
        return f"{d} days ago"
    if seconds < 2592000:
        w = seconds // 604800
        return f"{w} week{'s' if w != 1 else ''} ago"
    m = seconds // 2592000
    return f"{m} month{'s' if m != 1 else ''} ago"


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def prompt_yes_no(question: str, default: str = "N") -> bool:
    """Prompt for Y/N. Returns True for yes. Defaults to N on empty Enter."""
    default = default.upper()
    hint = "[Y/n]" if default == "Y" else "[y/N]"
    while True:
        raw = input(f"{Style.BRIGHT}  {question} {hint}: {Style.RESET_ALL}").strip().upper()
        if raw == "":
            return default == "Y"
        if raw in ("Y", "YES"):
            return True
        if raw in ("N", "NO"):
            return False
        print_warning("Please enter Y or N.")


def prompt_menu(
    options: dict[str, str],
    default: str | None = None,
) -> str:
    """Display a numbered/keyed menu and return the selected key.

    options maps key -> description, e.g. {"1": "Load show", "Q": "Quit"}.
    default is the key returned when the user presses Enter alone.
    """
    for key, description in options.items():
        prefix = f"[{key}]" if key == default else f" {key} "
        print(f"  {Style.BRIGHT}{prefix}{Style.RESET_ALL}  {description}")
    print_blank()

    hint = f" [{default}]" if default else ""
    while True:
        raw = input(f"{Style.BRIGHT}  Selection{hint}: {Style.RESET_ALL}").strip().upper()
        if raw == "" and default is not None:
            return default
        if raw in (k.upper() for k in options):
            # Return the original-case key
            for k in options:
                if k.upper() == raw:
                    return k
        print_warning(f"Invalid selection. Choose from: {', '.join(options.keys())}")


def prompt_path_input(question: str) -> Path:
    """Prompt the user to type a folder path. Re-prompts if empty."""
    while True:
        raw = input(f"{Style.BRIGHT}  {question}: {Style.RESET_ALL}").strip()
        if raw:
            return Path(raw)
        print_warning("Path cannot be empty.")


def pick_folder(title: str = "Select show project folder") -> Path | None:
    """Open a native folder picker dialog. Returns None if the user cancels."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", True)  # bring dialog to front on Windows
        folder = filedialog.askdirectory(title=title, parent=root)
        root.destroy()

        return Path(folder) if folder else None
    except Exception:
        # tkinter unavailable or user cancelled via exception
        return None
