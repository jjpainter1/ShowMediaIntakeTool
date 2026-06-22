"""Intake scan and execute endpoints."""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.serializers import (
    execution_result_to_dict,
    file_plan_from_dict,
    intake_scan_result_to_dict,
    stale_folder_from_dict,
)
from modules.config import ConfigInvalidError, ConfigNotFoundError, load_config
from modules.intake import (
    append_to_delivery_log,
    build_intake_plan,
    execute_plan,
    write_intake_log,
)
from modules.setup import open_in_editor

router = APIRouter(prefix="/intake", tags=["intake"])

_executor = ThreadPoolExecutor(max_workers=2)


class IntakeScanBody(BaseModel):
    show_path: str
    source_path: str


class IntakeExecuteBody(BaseModel):
    show_path: str
    source_path: str
    plans: list[dict]
    stale_folders: list[dict] = Field(default_factory=list)


class OpenLogBody(BaseModel):
    log_path: str


def _resolve_show_root(path: str) -> Path:
    show_root = Path(path)
    if not show_root.is_dir():
        raise HTTPException(status_code=404, detail="Show folder not found.")
    return show_root


def _resolve_source(path: str) -> Path:
    source = Path(path)
    if not source.is_dir():
        raise HTTPException(status_code=400, detail="Source folder not found.")
    return source


def _load_show_config(show_root: Path):
    try:
        return load_config(show_root)
    except (ConfigInvalidError, ConfigNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _run_scan(
    show_root: Path,
    source: Path,
    loop: asyncio.AbstractEventLoop | None = None,
    progress_queue: asyncio.Queue | None = None,
):
    config = _load_show_config(show_root)

    def on_progress(current: int, total: int, filename: str) -> None:
        if loop is not None and progress_queue is not None:
            loop.call_soon_threadsafe(
                progress_queue.put_nowait,
                {
                    "type": "progress",
                    "current": current,
                    "total": total,
                    "filename": filename,
                },
            )

    plans, stale = build_intake_plan(
        source, config, show_root, progress=on_progress
    )
    return plans, stale, config


def _run_execute(
    show_root: Path,
    source: Path,
    plan_dicts: list[dict],
    stale_dicts: list[dict],
    loop: asyncio.AbstractEventLoop | None = None,
    progress_queue: asyncio.Queue | None = None,
):
    config = _load_show_config(show_root)
    plans = [file_plan_from_dict(item) for item in plan_dicts]
    stale = [stale_folder_from_dict(item) for item in stale_dicts]
    conflicts_count = sum(1 for p in plans if p.version_conflict)

    def on_progress(current: int, total: int, filename: str, status: str) -> None:
        if loop is not None and progress_queue is not None:
            loop.call_soon_threadsafe(
                progress_queue.put_nowait,
                {
                    "type": "progress",
                    "current": current,
                    "total": total,
                    "filename": filename,
                    "status": status,
                },
            )

    result = execute_plan(plans, show_root, progress=on_progress)
    log_path = write_intake_log(
        show_root, plans, stale, result, source, config, proceeded=True
    )
    append_to_delivery_log(show_root, source, result, conflicts_count, log_path)
    return result, log_path


@router.post("/scan")
def scan_intake(body: IntakeScanBody) -> dict:
    """Build an intake plan without copying files."""
    show_root = _resolve_show_root(body.show_path)
    source = _resolve_source(body.source_path)
    try:
        plans, stale, config = _run_scan(
            show_root, source
        )
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Scan failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return intake_scan_result_to_dict(
        plans,
        stale,
        show_root,
        source,
        intake_mode=config.intake.mode,
    )


@router.post("/execute")
def execute_intake(body: IntakeExecuteBody) -> dict:
    """Execute a previously reviewed intake plan."""
    show_root = _resolve_show_root(body.show_path)
    source = _resolve_source(body.source_path)
    try:
        result, log_path = _run_execute(
            show_root, source, body.plans, body.stale_folders
        )
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Copy failed: {exc}") from exc
    return {
        "show_path": str(show_root),
        "source_path": str(source),
        "result": execution_result_to_dict(result),
        "intake_log_path": str(log_path),
    }


@router.post("/open-log")
def open_intake_log(body: OpenLogBody) -> dict:
    """Open the detailed intake log in the system text editor."""
    log_path = Path(body.log_path)
    if not log_path.is_file():
        raise HTTPException(status_code=404, detail="Intake log not found.")
    opened = open_in_editor(log_path)
    return {"opened": opened, "log_path": str(log_path)}


async def _drain_progress_queue(
    websocket: WebSocket,
    queue: asyncio.Queue,
    done: asyncio.Event,
) -> None:
    while not done.is_set() or not queue.empty():
        try:
            message = queue.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.05)
            continue
        await websocket.send_json(message)


@router.websocket("/scan/ws")
async def scan_progress_ws(websocket: WebSocket) -> None:
    """Scan source folder with live progress events."""
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        payload = json.loads(raw) if raw else {}
        show_path = payload.get("show_path", "")
        source_path = payload.get("source_path", "")
        if not show_path or not source_path:
            await websocket.send_json(
                {"type": "error", "message": "show_path and source_path are required."}
            )
            return

        show_root = _resolve_show_root(show_path)
        source = _resolve_source(source_path)

        await websocket.send_json({"type": "started", "message": "Scan started"})

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        done = asyncio.Event()

        async def run_scan() -> tuple:
            return await loop.run_in_executor(
                _executor,
                lambda: _run_scan(
                    show_root, source, loop, queue
                ),
            )

        drain_task = asyncio.create_task(_drain_progress_queue(websocket, queue, done))
        try:
            plans, stale, config = await run_scan()
        except HTTPException as exc:
            await websocket.send_json({"type": "error", "message": exc.detail})
            return
        except ValueError as exc:
            await websocket.send_json({"type": "error", "message": str(exc)})
            return
        except OSError as exc:
            await websocket.send_json({"type": "error", "message": f"Scan failed: {exc}"})
            return
        finally:
            done.set()
            await drain_task

        result = intake_scan_result_to_dict(
            plans,
            stale,
            show_root,
            source,
            intake_mode=config.intake.mode,
        )
        await websocket.send_json({"type": "complete", **result})
    except WebSocketDisconnect:
        return
    except json.JSONDecodeError:
        await websocket.send_json({"type": "error", "message": "Invalid JSON payload"})
    except Exception as exc:  # noqa: BLE001 — surface unexpected errors to the client
        await websocket.send_json({"type": "error", "message": str(exc)})
    finally:
        await websocket.close()


@router.websocket("/execute/ws")
async def execute_progress_ws(websocket: WebSocket) -> None:
    """Execute an intake plan with live progress events."""
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        payload = json.loads(raw) if raw else {}
        show_path = payload.get("show_path", "")
        source_path = payload.get("source_path", "")
        plan_dicts = payload.get("plans", [])
        stale_dicts = payload.get("stale_folders", [])
        if not show_path or not source_path or not plan_dicts:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "show_path, source_path, and plans are required.",
                }
            )
            return

        show_root = _resolve_show_root(show_path)
        source = _resolve_source(source_path)

        await websocket.send_json({"type": "started", "message": "Copy started"})

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        done = asyncio.Event()

        async def run_execute() -> tuple:
            return await loop.run_in_executor(
                _executor,
                lambda: _run_execute(
                    show_root, source, plan_dicts, stale_dicts, loop, queue
                ),
            )

        drain_task = asyncio.create_task(_drain_progress_queue(websocket, queue, done))
        try:
            result, log_path = await run_execute()
        except HTTPException as exc:
            await websocket.send_json({"type": "error", "message": exc.detail})
            return
        except OSError as exc:
            await websocket.send_json({"type": "error", "message": f"Copy failed: {exc}"})
            return
        finally:
            done.set()
            await drain_task

        await websocket.send_json(
            {
                "type": "complete",
                "show_path": str(show_root),
                "source_path": str(source),
                "result": execution_result_to_dict(result),
                "intake_log_path": str(log_path),
            }
        )
    except WebSocketDisconnect:
        return
    except json.JSONDecodeError:
        await websocket.send_json({"type": "error", "message": "Invalid JSON payload"})
    except Exception as exc:  # noqa: BLE001
        await websocket.send_json({"type": "error", "message": str(exc)})
    finally:
        await websocket.close()
