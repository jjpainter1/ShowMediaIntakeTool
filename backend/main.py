"""FastAPI sidecar for Show Media Intake Tool v2."""

from __future__ import annotations

import sys
from pathlib import Path

# Project root on path so `modules` imports work when running uvicorn.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes import codecs, health, intake, presets, shows, spec, system

app = FastAPI(
    title="Show Media Intake Tool API",
    version="2.0.0",
    description="Python backend for the Tauri desktop app.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://localhost:5173",
        "http://tauri.localhost",  # Tauri 2 production (Windows default)
        "https://tauri.localhost",
        "tauri://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(shows.router, prefix="/api")
app.include_router(intake.router, prefix="/api")
app.include_router(presets.router, prefix="/api")
app.include_router(codecs.router, prefix="/api")
app.include_router(spec.router, prefix="/api")
app.include_router(system.router, prefix="/api")


@app.on_event("startup")
def _ensure_user_data() -> None:
    from modules.paths import get_user_data_root

    get_user_data_root()
