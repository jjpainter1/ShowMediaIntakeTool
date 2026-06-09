"""System helpers for local development (native dialogs on the server machine)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from modules.folder_dialog import pick_delivery_source_folder, pick_file_native, pick_folder_native
from modules.setup import open_in_explorer

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/pick-folder")
def pick_folder_endpoint(
    title: str = Query(default="Select folder", max_length=200),
    mode: str = Query(
        default="folder",
        description="'folder' for directory picker; 'delivery_source' shows media files",
    ),
    start_dir: str | None = Query(default=None, max_length=500),
) -> dict:
    """Open a native picker on the machine running the Python backend."""
    if mode == "delivery_source":
        selected = pick_delivery_source_folder(title, start_dir=start_dir)
    else:
        selected = pick_folder_native(title)
    if selected is None:
        return {"cancelled": True, "path": None}
    return {"cancelled": False, "path": str(selected)}


@router.get("/pick-file")
def pick_file_endpoint(
    title: str = Query(default="Select file", max_length=200),
    filetypes: str = Query(
        default="JSON files|*.json|All files|*.*",
        max_length=300,
    ),
) -> dict:
    """Open a native file picker on the machine running the Python backend."""
    selected = pick_file_native(title, filetypes=filetypes)
    if selected is None:
        return {"cancelled": True, "path": None}
    return {"cancelled": False, "path": str(selected)}


class OpenPathBody(BaseModel):
    path: str = Field(..., min_length=1)


@router.post("/open-path")
def open_path_endpoint(body: OpenPathBody) -> dict:
    """Open a folder in Explorer or reveal a file (Windows /select)."""
    target = Path(body.path)
    opened = open_in_explorer(target)
    if not opened:
        raise HTTPException(status_code=404, detail=f"Path not found or could not open: {body.path}")
    return {"opened": True, "path": str(target)}


@router.get("/pick-delivery-source")
def pick_delivery_source_endpoint(
    title: str = Query(
        default="Select any file in the delivery folder",
        max_length=200,
    ),
) -> dict:
    """Alias for pick-folder?mode=delivery_source (kept for compatibility)."""
    return pick_folder_endpoint(title=title, mode="delivery_source")
