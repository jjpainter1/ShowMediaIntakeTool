"""Unit tests for routed vs flat intake folder routing."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.config import load_config
from modules.ffprobe_wrapper import MediaSpecs
from modules.filename_parser import FullMatch, NoMatch, ParsedFilename
from modules.intake import (
    FLAT_INTAKE_FOLDER,
    Action,
    plan_file,
    plan_file_flat,
)


def _base_config(mode: str) -> dict:
    return {
        "schema_version": 2,
        "preset": "pixera",
        "show_name": "Routing Test",
        "show_date": "2026-06-18",
        "operator": {"name": "Op", "email": "op@test.com"},
        "expected_specs": {
            "framerate": 30,
            "color_space": "bt709",
            "color_range": "tv",
            "audio_sample_rate": 48000,
            "audio_channels": 2,
        },
        "expected_codecs": ["prores_422_hq"],
        "preferred_codecs": ["prores_422_hq"],
        "screens": [
            {"id": "SCR01", "name": "Main", "resolution": "1920x1080"},
            {"id": "SCR02", "name": "Side", "resolution": "3840x2160"},
        ],
        "validation_strictness": {
            "resolution": "strict",
            "framerate": "strict",
            "codec": "strict",
            "codec_flavor": "warn",
            "color_space": "warn",
            "color_range": "warn",
            "audio_sample_rate": "info",
            "audio_channels": "info",
            "screen_id": "strict",
            "filename_convention": "strict",
            "filename_format": "warn",
            "show_token": "strict",
        },
        "intake": {"mode": mode},
        "output_specs": {"mode": "uniform"},
        "delivery": {},
        "filename_convention": {
            "enabled": True,
            "tokens": ["screen", "slug", "version", "date"],
            "version_prefix": "v",
            "date_format": "YYYYMMDD",
            "loop_suffix": "-LOOP",
        },
    }


def _good_specs(width: int, height: int, framerate: float = 30.0) -> MediaSpecs:
    return MediaSpecs(
        width=width,
        height=height,
        framerate=framerate,
        codec_name="prores",
        codec_tag="apch",
        color_space="bt709",
        color_range="tv",
        audio_sample_rate=48000,
        audio_channels=2,
        duration_seconds=10.0,
        probe_succeeded=True,
        probe_error=None,
    )


def _write_show(tmp: Path, mode: str) -> Path:
    show_root = tmp / "Show_RoutingTest_20260618"
    show_root.mkdir()
    (show_root / "Media").mkdir()
    config_path = show_root / "show_config.json"
    config_path.write_text(json.dumps(_base_config(mode), indent=2), encoding="utf-8")
    return show_root


def test_routed_routes_by_screen_prefix() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        show_root = _write_show(Path(tmpdir), "routed")
        config = load_config(show_root)
        source = show_root / "SCR01_Opening_v01_20260618.mov"
        source.write_bytes(b"fake")

        parsed = FullMatch(
            ParsedFilename(
                screen_prefix="SCR01",
                slug="Opening",
                version=1,
                date=__import__("datetime").date(2026, 6, 18),
                extension=".mov",
                is_loop=False,
                original_name=source.name,
            )
        )
        with patch("modules.intake.parse_filename", return_value=parsed), patch(
            "modules.intake.probe_file", return_value=_good_specs(1920, 1080)
        ):
            plan = plan_file(source, config, show_root)

        assert plan.action in (Action.COPY, Action.COPY_WITH_WARNING), plan.failures
        assert plan.destination_path.parent.name == "SCR01"
        print("PASS  routed intake -> SCR01 folder")


def test_flat_routes_to_incoming() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        show_root = _write_show(Path(tmpdir), "flat")
        config = load_config(show_root)
        source = show_root / "OpeningVideo.mov"
        source.write_bytes(b"fake")

        with patch("modules.intake.parse_filename", return_value=NoMatch("OpeningVideo.mov", [])), patch(
            "modules.intake.probe_file", return_value=_good_specs(3840, 2160)
        ):
            plan = plan_file_flat(source, config, show_root)

        assert plan.action in (Action.COPY, Action.COPY_WITH_WARNING), plan.failures
        assert plan.destination_path.parent.name == FLAT_INTAKE_FOLDER
        print("PASS  flat intake -> _INCOMING folder")


def test_flat_strict_failure_goes_to_review() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        show_root = _write_show(Path(tmpdir), "flat")
        config = load_config(show_root)
        source = show_root / "BadRate.mov"
        source.write_bytes(b"fake")

        with patch("modules.intake.parse_filename", return_value=NoMatch("BadRate.mov", [])), patch(
            "modules.intake.probe_file",
            return_value=_good_specs(1920, 1080, framerate=25.0),
        ):
            plan = plan_file_flat(source, config, show_root)

        assert plan.action == Action.ROUTE_TO_REVIEW
        assert plan.destination_path.parent.name == "_REVIEW"
        assert any("framerate" in f.lower() for f in plan.failures)
        print("PASS  flat strict failure -> _REVIEW")


def test_routed_unknown_screen_goes_to_review() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        show_root = _write_show(Path(tmpdir), "routed")
        config = load_config(show_root)
        source = show_root / "SCR99_Opening_v01_20260618.mov"
        source.write_bytes(b"fake")

        parsed = FullMatch(
            ParsedFilename(
                screen_prefix="SCR99",
                slug="Opening",
                version=1,
                date=__import__("datetime").date(2026, 6, 18),
                extension=".mov",
                is_loop=False,
                original_name=source.name,
            )
        )
        with patch("modules.intake.parse_filename", return_value=parsed), patch(
            "modules.intake.probe_file", return_value=_good_specs(1920, 1080)
        ):
            plan = plan_file(source, config, show_root)

        assert plan.action == Action.ROUTE_TO_REVIEW
        assert plan.destination_path.parent.name == "_REVIEW"
        print("PASS  routed unknown screen -> _REVIEW")


def main() -> int:
    tests = [
        test_routed_routes_by_screen_prefix,
        test_flat_routes_to_incoming,
        test_flat_strict_failure_goes_to_review,
        test_routed_unknown_screen_goes_to_review,
    ]
    failures = 0
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {test.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL  {test.__name__}: {exc}")
    if failures:
        print(f"\n{failures} test(s) failed.")
        return 1
    print("\nAll intake routing tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
