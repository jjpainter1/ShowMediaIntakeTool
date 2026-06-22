"""Delivery specification document generation."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from modules.config import ConfigInvalidError, ConfigNotFoundError, load_config
from modules.setup import open_with_default_app
from modules.spec_generator import generate_spec

router = APIRouter(prefix="/spec", tags=["spec"])


class GenerateSpecBody(BaseModel):
    path: str = Field(..., min_length=1)


class OpenSpecBody(BaseModel):
    path: str = Field(..., min_length=1)


def _resolve_show_root(path: str) -> Path:
    show_root = Path(path)
    if not show_root.is_dir():
        raise HTTPException(status_code=404, detail="Show folder not found.")
    return show_root


@router.post("/generate")
def generate_spec_endpoint(body: GenerateSpecBody) -> dict:
    """Generate the delivery spec .docx from the show's saved configuration."""
    show_root = _resolve_show_root(body.path)
    try:
        config = load_config(show_root)
    except ConfigNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConfigInvalidError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        output_path = generate_spec(show_root, config)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not write spec document: {exc}") from exc

    return {
        "path": str(show_root),
        "output_path": str(output_path),
        "show_name": config.show_name,
    }


@router.post("/open")
def open_spec_endpoint(body: OpenSpecBody) -> dict:
    """Open a generated spec document in the default application."""
    doc_path = Path(body.path)
    if not doc_path.is_file():
        raise HTTPException(status_code=404, detail="Spec document not found.")
    opened = open_with_default_app(doc_path)
    if not opened:
        raise HTTPException(
            status_code=500,
            detail=f"Could not open file: {body.path}",
        )
    return {"opened": opened, "path": str(doc_path)}
