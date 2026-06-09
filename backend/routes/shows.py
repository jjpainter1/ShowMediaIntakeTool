"""Show discovery, loading, dashboard, and config."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.serializers import delivery_history_entry_to_dict, snapshot_to_dict
from modules.config import (
    ConfigError,
    ConfigInvalidError,
    ConfigNotFoundError,
    is_v1_config,
    load_config,
    migrate_v1_config,
    read_config_dict,
    save_config,
)
from modules.dashboard_files import list_screen_file_details
from modules.recent_shows import add_or_update, load_recent_shows, set_dashboard_view
from modules.setup import create_new_show, ensure_media_structure, open_in_editor
from modules.show_report import (
    gather_snapshot,
    parse_delivery_history,
    read_delivery_log,
    read_intake_log_content,
    resolve_intake_log_path,
)

router = APIRouter(tags=["shows"])


class RecentShowOut(BaseModel):
    path: str
    show_name: str
    last_used: datetime
    dashboard_view: str | None = None


class ShowSummaryOut(BaseModel):
    path: str
    show_name: str
    preset: str | None
    schema_version: int | None


class CreateShowBody(BaseModel):
    parent_path: str
    show_name: str = Field(..., min_length=1)
    show_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")


class ConfigSaveBody(BaseModel):
    path: str
    config: dict


class MigrateOut(BaseModel):
    path: str
    backup_path: str
    message: str


class DashboardViewBody(BaseModel):
    path: str
    view: str = Field(..., pattern="^(cards|compact)$")


class OpenConfigBody(BaseModel):
    path: str


def _resolve_show_root(path: str) -> Path:
    show_root = Path(path)
    if not show_root.is_dir():
        raise HTTPException(status_code=404, detail="Show folder not found.")
    return show_root


def _config_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ConfigNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ConfigInvalidError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ConfigError):
        return HTTPException(status_code=409, detail=str(exc))
    raise exc


@router.get("/recent-shows", response_model=list[RecentShowOut])
def recent_shows() -> list[RecentShowOut]:
    shows = load_recent_shows()
    return [
        RecentShowOut(
            path=str(s.path),
            show_name=s.show_name,
            last_used=s.last_used,
            dashboard_view=s.dashboard_view,
        )
        for s in shows
    ]


@router.get("/shows/load", response_model=ShowSummaryOut)
def load_show(path: str = Query(..., description="Absolute path to show root")) -> ShowSummaryOut:
    show_root = _resolve_show_root(path)
    config_path = show_root / "show_config.json"

    if not config_path.exists():
        raise HTTPException(status_code=404, detail="show_config.json not found in folder.")

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

    if is_v1_config(raw):
        raise HTTPException(
            status_code=409,
            detail="show_config.json is v1 schema — migration required before load.",
        )

    try:
        config = load_config(show_root)
    except (ConfigInvalidError, ConfigNotFoundError) as exc:
        raise _config_http_error(exc) from exc

    ensure_media_structure(show_root, config)
    add_or_update(show_root, config.show_name)

    return ShowSummaryOut(
        path=str(show_root),
        show_name=config.show_name,
        preset=config.preset,
        schema_version=config.schema_version,
    )


@router.get("/shows/screen-files")
def show_screen_files(
    path: str = Query(..., description="Absolute path to show root"),
    screen_id: str = Query(..., min_length=1, description="Configured screen id"),
) -> dict:
    show_root = _resolve_show_root(path)
    try:
        config = load_config(show_root)
    except (ConfigInvalidError, ConfigNotFoundError) as exc:
        raise _config_http_error(exc) from exc

    if not any(screen.id == screen_id for screen in config.screens):
        raise HTTPException(status_code=404, detail=f"Screen not found in config: {screen_id}")

    files = list_screen_file_details(show_root, config, screen_id)
    return {"path": str(show_root), "screen_id": screen_id, "files": files}


@router.get("/shows/dashboard")
def show_dashboard(path: str = Query(..., description="Absolute path to show root")) -> dict:
    show_root = _resolve_show_root(path)
    try:
        config = load_config(show_root)
    except (ConfigInvalidError, ConfigNotFoundError) as exc:
        raise _config_http_error(exc) from exc

    snapshot = gather_snapshot(show_root, config)
    return {
        **snapshot_to_dict(snapshot),
        "show_name": config.show_name,
        "show_date": config.show_date,
    }


@router.patch("/recent-shows/dashboard-view")
def patch_dashboard_view(body: DashboardViewBody) -> dict:
    show_root = _resolve_show_root(body.path)
    set_dashboard_view(show_root, body.view)
    return {"path": str(show_root), "dashboard_view": body.view}


@router.get("/shows/delivery-log")
def show_delivery_log(path: str = Query(..., description="Absolute path to show root")) -> dict:
    show_root = _resolve_show_root(path)
    lines = read_delivery_log(show_root)
    return {"path": str(show_root), "lines": lines}


@router.get("/shows/delivery-history")
def show_delivery_history(path: str = Query(..., description="Absolute path to show root")) -> dict:
    show_root = _resolve_show_root(path)
    entries = parse_delivery_history(show_root)
    return {
        "path": str(show_root),
        "entries": [delivery_history_entry_to_dict(entry) for entry in entries],
    }


@router.get("/shows/intake-log")
def show_intake_log(
    path: str = Query(..., description="Absolute path to show root"),
    log_path: str = Query(..., description="Absolute or basename path to intake log"),
) -> dict:
    show_root = _resolve_show_root(path)
    try:
        resolved = resolve_intake_log_path(show_root, log_path)
        content = read_intake_log_content(show_root, log_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"log_path": str(resolved), "content": content}


@router.get("/shows/config")
def get_show_config(path: str = Query(..., description="Absolute path to show root")) -> dict:
    show_root = _resolve_show_root(path)
    try:
        data = read_config_dict(show_root)
    except (ConfigInvalidError, ConfigNotFoundError) as exc:
        raise _config_http_error(exc) from exc

    if is_v1_config(data):
        raise HTTPException(
            status_code=409,
            detail="show_config.json is v1 schema — migration required before load.",
        )
    return data


@router.put("/shows/config")
def put_show_config(body: ConfigSaveBody) -> dict:
    show_root = _resolve_show_root(body.path)
    try:
        config_path = save_config(show_root, body.config)
    except (ConfigInvalidError, ConfigNotFoundError) as exc:
        raise _config_http_error(exc) from exc

    config = load_config(show_root)
    ensure_media_structure(show_root, config)
    add_or_update(show_root, config.show_name)
    return {"path": str(show_root), "config_path": str(config_path)}


@router.post("/shows/migrate", response_model=MigrateOut)
def migrate_show(path: str = Query(..., description="Absolute path to show root")) -> MigrateOut:
    show_root = _resolve_show_root(path)
    try:
        backup_path = migrate_v1_config(show_root)
    except (ConfigInvalidError, ConfigNotFoundError) as exc:
        raise _config_http_error(exc) from exc
    except ConfigError as exc:
        raise _config_http_error(exc) from exc

    return MigrateOut(
        path=str(show_root),
        backup_path=str(backup_path),
        message="Migration complete. show_config.v1.bak.json written.",
    )


@router.post("/shows/open-config")
def open_show_config(body: OpenConfigBody) -> dict:
    show_root = _resolve_show_root(body.path)
    config_path = show_root / "show_config.json"
    if not config_path.is_file():
        raise HTTPException(status_code=404, detail="show_config.json not found.")
    opened = open_in_editor(config_path)
    return {"opened": opened, "config_path": str(config_path)}


@router.post("/shows/create", response_model=ShowSummaryOut)
def create_show(body: CreateShowBody) -> ShowSummaryOut:
    parent = Path(body.parent_path)
    try:
        show_root = create_new_show(parent, body.show_name, body.show_date)
    except ConfigError as exc:
        raise _config_http_error(exc) from exc

    try:
        config = load_config(show_root)
    except (ConfigInvalidError, ConfigNotFoundError) as exc:
        raise _config_http_error(exc) from exc

    add_or_update(show_root, config.show_name)
    return ShowSummaryOut(
        path=str(show_root),
        show_name=config.show_name,
        preset=config.preset,
        schema_version=config.schema_version,
    )
