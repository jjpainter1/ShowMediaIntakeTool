"""Codec identifier metadata for the config editor."""

from __future__ import annotations

from fastapi import APIRouter

from modules.ffprobe_wrapper import get_known_codecs

router = APIRouter(prefix="/codecs", tags=["codecs"])


@router.get("")
def list_codecs() -> dict:
    return {"identifiers": get_known_codecs()}
