"""Startup and health endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from modules.ffprobe_wrapper import check_ffprobe_available
from modules.paths import get_user_data_root

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Return readiness info for the desktop shell."""
    return {
        "status": "ok",
        "phase": 5,
        "api_features": ["pick_delivery_source", "config_editor"],
        "ffprobe_available": check_ffprobe_available(),
        "user_data_root": str(get_user_data_root()),
    }
