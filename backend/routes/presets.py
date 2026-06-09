"""Preset listing, import, and custom preset save."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from modules.presets import (
    PresetError,
    apply_preset,
    custom_preset_exists,
    load_all_presets,
    load_preset_from_path,
    save_custom_preset,
)

router = APIRouter(prefix="/presets", tags=["presets"])


class PresetOut(BaseModel):
    preset_name: str
    preset_description: str
    expected_specs: dict
    expected_codecs: list[str]
    preferred_codecs: list[str]
    validation_strictness: dict[str, str]
    source: str


class PresetListOut(BaseModel):
    builtin: list[PresetOut]
    custom: list[PresetOut]


class SaveCustomPresetBody(BaseModel):
    preset_name: str = Field(..., min_length=1)
    config: dict


class ImportPresetBody(BaseModel):
    path: str


class ApplyPresetBody(BaseModel):
    preset_name: str = Field(..., min_length=1)
    config: dict


def _preset_to_out(preset, source: str) -> PresetOut:
    return PresetOut(
        preset_name=preset.preset_name,
        preset_description=preset.preset_description,
        expected_specs=dict(preset.expected_specs),
        expected_codecs=list(preset.expected_codecs),
        preferred_codecs=list(preset.preferred_codecs),
        validation_strictness=dict(preset.validation_strictness),
        source=source,
    )


def _preset_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PresetError):
        return HTTPException(status_code=400, detail=str(exc))
    raise exc


@router.get("", response_model=PresetListOut)
def list_presets() -> PresetListOut:
    try:
        builtin, custom = load_all_presets()
    except PresetError as exc:
        raise _preset_http_error(exc) from exc

    return PresetListOut(
        builtin=[_preset_to_out(p, "builtin") for p in builtin],
        custom=[_preset_to_out(p, "custom") for p in custom],
    )


@router.post("/apply")
def apply_preset_endpoint(body: ApplyPresetBody) -> dict:
    try:
        builtin, custom = load_all_presets()
    except PresetError as exc:
        raise _preset_http_error(exc) from exc

    target = body.preset_name.strip().lower()
    match = None
    for preset in [*builtin, *custom]:
        if preset.preset_name.lower() == target:
            match = preset
            break

    if match is None:
        raise HTTPException(status_code=404, detail=f"Preset not found: {body.preset_name!r}")

    merged = apply_preset(body.config, match)
    return {"config": merged}


@router.post("/custom")
def save_custom_preset_endpoint(body: SaveCustomPresetBody) -> dict:
    name = body.preset_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Preset name must not be empty.")
    if custom_preset_exists(name):
        raise HTTPException(
            status_code=409,
            detail=f"A custom preset named '{name}' already exists.",
        )
    try:
        dest = save_custom_preset(name, body.config)
    except PresetError as exc:
        raise _preset_http_error(exc) from exc
    return {"preset_name": name, "path": str(dest)}


@router.post("/import")
def import_preset_endpoint(body: ImportPresetBody) -> PresetOut:
    path = Path(body.path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Preset file not found.")
    try:
        preset = load_preset_from_path(path)
    except PresetError as exc:
        raise _preset_http_error(exc) from exc
    return _preset_to_out(preset, "imported")
