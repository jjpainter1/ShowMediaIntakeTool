"""Quick smoke tests for Phase 1–2 API endpoints."""

from __future__ import annotations

import json
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_manifest = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
_BACKEND_PORT = int(_manifest.get("backend_port", 18080))
BASE = f"http://127.0.0.1:{_BACKEND_PORT}"


def get(path: str) -> tuple[int, object]:
    try:
        with urllib.request.urlopen(BASE + path) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def post(path: str, body: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body or {}).encode()
    request = urllib.request.Request(
        BASE + path,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def put(path: str, body: dict) -> int:
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return response.status


def main() -> None:
    status, health = get("/api/health")
    assert status == 200 and health["status"] == "ok", health
    assert health.get("phase") == 2, health

    status, recent = get("/api/recent-shows")
    assert status == 200 and isinstance(recent, list)

    parent = Path(tempfile.mkdtemp())
    folder = "TestShow_20260615"
    status, created = post(
        "/api/shows/create",
        {"parent_path": str(parent), "show_name": "TestShow", "show_date": "2026-06-15"},
    )
    assert status == 200, created
    show_path = created["path"]

    status, loaded = get(f"/api/shows/load?path={urllib.parse.quote(show_path)}")
    assert status == 200 and loaded["show_name"] == "TestShow", loaded

    status, dash = get(f"/api/shows/dashboard?path={urllib.parse.quote(show_path)}")
    assert status == 200 and "screens" in dash, dash

    status, log = get(f"/api/shows/delivery-log?path={urllib.parse.quote(show_path)}")
    assert status == 200 and log["lines"] == [], log

    cfg = json.loads(Path(show_path, "show_config.json").read_text(encoding="utf-8"))
    cfg["screens"] = []
    Path(show_path, "show_config.json").write_text(
        json.dumps(cfg, indent=2), encoding="utf-8"
    )
    status, empty_dash = get(f"/api/shows/dashboard?path={urllib.parse.quote(show_path)}")
    assert status == 200 and empty_dash["screens"] == {}, empty_dash

    status, cfg = get(f"/api/shows/config?path={urllib.parse.quote(show_path)}")
    assert status == 200 and cfg["show_name"] == "TestShow"

    cfg["operator"]["name"] = "Test Operator"
    assert put("/api/shows/config", {"path": show_path, "config": cfg}) == 200

    v1_root = Path(tempfile.mkdtemp())
    shutil.copytree(parent / folder, v1_root / "v1show")
    v1_cfg = v1_root / "v1show" / "show_config.json"
    data = json.loads(v1_cfg.read_text(encoding="utf-8"))
    data.pop("schema_version", None)
    data.pop("preset", None)
    v1_cfg.write_text(json.dumps(data, indent=2), encoding="utf-8")

    v1_path = str(v1_root / "v1show")
    status, _ = get(f"/api/shows/load?path={urllib.parse.quote(v1_path)}")
    assert status == 409

    status, mig = post(f"/api/shows/migrate?path={urllib.parse.quote(v1_path)}")
    assert status == 200 and Path(mig["backup_path"]).exists(), mig

    print("ALL API TESTS PASSED")
    shutil.rmtree(parent, ignore_errors=True)
    shutil.rmtree(v1_root, ignore_errors=True)


if __name__ == "__main__":
    main()
