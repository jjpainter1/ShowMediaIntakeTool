"""Native folder picker safe to call from FastAPI worker threads."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def pick_folder_native(title: str = "Select folder") -> Path | None:
    """Open a folder picker in a short-lived subprocess (tkinter needs a main thread)."""
    script = """
import sys
try:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(title=sys.argv[1] if len(sys.argv) > 1 else "Select folder")
    root.destroy()
    print(folder or "")
except Exception:
    print("")
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script, title],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    selected = result.stdout.strip()
    return Path(selected) if selected else None


def pick_file_native(
    title: str = "Select file",
    filetypes: str = "JSON files|*.json|All files|*.*",
) -> Path | None:
    """Open a file picker in a short-lived subprocess."""
    script = """
import sys
try:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    types_arg = sys.argv[2] if len(sys.argv) > 2 else "All files|*.*"
    pairs = []
    for part in types_arg.split("|"):
        part = part.strip()
        if not part:
            continue
        if part.startswith("*."):
            pairs.append(("files", part))
        else:
            pairs.append((part, "*.*"))
    if not pairs:
        pairs = [("All files", "*.*")]
    selected = filedialog.askopenfilename(
        title=sys.argv[1] if len(sys.argv) > 1 else "Select file",
        filetypes=pairs,
    )
    root.destroy()
    print(selected or "")
except Exception:
    print("")
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script, title, filetypes],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    selected = result.stdout.strip()
    return Path(selected) if selected else None


def pick_delivery_source_folder(
    title: str = "Select delivery source folder",
    start_dir: Path | str | None = None,
) -> Path | None:
    """Pick a delivery source folder using the standard Windows folder dialog.

    TODO(v2.1): Revisit a custom browser that lists media files in-folder
    (would need drive switching, e.g. C: vs D:).
  """
    _ = start_dir  # reserved for a future picker that honors initial directory
    return pick_folder_native(title)
