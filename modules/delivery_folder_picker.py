"""Folder picker that lists media files so operators can confirm contents.

NOT USED in v2.0 — reverted to standard Windows folder dialog (no in-folder
file preview). Revisit for v2.1: needs drive switching (C: / D:) and a clear
way to confirm the folder without picking a single file.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

_MEDIA_EXTENSIONS = {
    ".mp4", ".mov", ".mxf", ".avi", ".mkv", ".webm", ".mpg", ".mpeg", ".wmv", ".m4v",
    ".prores", ".r3d", ".braw", ".exr", ".tif", ".tiff", ".png", ".jpg", ".jpeg",
    ".wav", ".aiff", ".aif", ".mp3", ".m4a",
}


def _is_media(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in _MEDIA_EXTENSIONS


def _list_entries(folder: Path) -> tuple[list[Path], list[Path]]:
    """Return (subfolders, media_files) sorted by name."""
    if not folder.is_dir():
        return [], []
    subfolders: list[Path] = []
    media_files: list[Path] = []
    try:
        for child in folder.iterdir():
            if child.name.startswith("."):
                continue
            if child.is_dir():
                subfolders.append(child)
            elif _is_media(child):
                media_files.append(child)
    except OSError:
        return [], []
    subfolders.sort(key=lambda p: p.name.lower())
    media_files.sort(key=lambda p: p.name.lower())
    return subfolders, media_files


def pick_delivery_folder(
    title: str = "Select delivery source folder",
    start_dir: Path | None = None,
) -> Path | None:
    """Browse folders, preview media files, confirm with Select This Folder."""
    current = (start_dir or Path.home()).resolve()
    if not current.is_dir():
        current = current.parent if current.parent.is_dir() else Path.home()

    selected: list[Path | None] = [None]

    root = tk.Tk()
    root.title(title)
    root.geometry("760x520")
    root.minsize(560, 400)
    root.attributes("-topmost", True)

    header = ttk.Label(
        root,
        text="Browse to the delivery folder, review the media files listed below, "
        "then click Select This Folder.",
        wraplength=720,
        justify="left",
    )
    header.pack(fill="x", padx=12, pady=(12, 8))

    path_frame = ttk.Frame(root)
    path_frame.pack(fill="x", padx=12, pady=(0, 8))

    path_var = tk.StringVar(value=str(current))
    path_entry = ttk.Entry(path_frame, textvariable=path_var, state="readonly")
    path_entry.pack(side="left", fill="x", expand=True)

    list_frame = ttk.Frame(root)
    list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    scrollbar = ttk.Scrollbar(list_frame)
    scrollbar.pack(side="right", fill="y")

    listbox = tk.Listbox(
        list_frame,
        yscrollcommand=scrollbar.set,
        font=("Consolas", 10),
        selectmode=tk.SINGLE,
    )
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=listbox.yview)

    status_var = tk.StringVar()
    status_label = ttk.Label(root, textvariable=status_var, anchor="w")
    status_label.pack(fill="x", padx=12, pady=(0, 8))

    button_frame = ttk.Frame(root)
    button_frame.pack(fill="x", padx=12, pady=(0, 12))

    def refresh_list() -> None:
        nonlocal current
        current = Path(path_var.get())
        listbox.delete(0, tk.END)
        subfolders, media_files = _list_entries(current)

        if current.parent != current:
            listbox.insert(tk.END, f"📁  ..  (parent folder)")
            listbox.itemconfig(0, foreground="#6b7280")

        for folder in subfolders:
            listbox.insert(tk.END, f"📁  {folder.name}")
        folder_count = len(subfolders)

        for media in media_files:
            listbox.insert(tk.END, f"    {media.name}")
            listbox.itemconfig(listbox.size() - 1, foreground="#2563eb")

        other_count = 0
        if current.is_dir():
            try:
                other_count = sum(
                    1
                    for child in current.iterdir()
                    if child.is_file()
                    and not _is_media(child)
                    and not child.name.startswith(".")
                )
            except OSError:
                other_count = 0

        parts = [f"{len(media_files)} media file{'s' if len(media_files) != 1 else ''}"]
        if folder_count:
            parts.append(f"{folder_count} subfolder{'s' if folder_count != 1 else ''}")
        if other_count:
            parts.append(f"{other_count} other file{'s' if other_count != 1 else ''}")
        status_var.set(" · ".join(parts) if parts else "Folder is empty")

    def go_to(path: Path) -> None:
        if path.is_dir():
            path_var.set(str(path))
            refresh_list()

    def on_activate(_event: object = None) -> None:
        selection = listbox.curselection()
        if not selection:
            return
        text = listbox.get(selection[0])
        if text.startswith("📁  .."):
            go_to(current.parent)
            return
        if text.startswith("📁  "):
            go_to(current / text.replace("📁  ", "", 1).strip())

    def on_select_folder() -> None:
        selected[0] = current
        root.destroy()

    def on_cancel() -> None:
        selected[0] = None
        root.destroy()

    listbox.bind("<Double-Button-1>", on_activate)

    up_btn = ttk.Button(
        button_frame,
        text="↑ Up",
        command=lambda: go_to(current.parent),
    )
    up_btn.pack(side="left")

    select_btn = ttk.Button(
        button_frame,
        text="Select This Folder",
        command=on_select_folder,
    )
    select_btn.pack(side="right", padx=(8, 0))

    cancel_btn = ttk.Button(button_frame, text="Cancel", command=on_cancel)
    cancel_btn.pack(side="right")

    refresh_list()
    root.mainloop()
    return selected[0]


def main() -> None:
    title = sys.argv[1] if len(sys.argv) > 1 else "Select delivery source folder"
    start = Path(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else None
    picked = pick_delivery_folder(title, start)
    print(picked if picked else "")


if __name__ == "__main__":
    main()
