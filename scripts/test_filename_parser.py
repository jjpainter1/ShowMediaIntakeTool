"""Tests for flexible filename token detection (order-independent)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.config import _build_show_config, validate_config
from modules.filename_parser import FullMatch, NoMatch, PartialMatch, parse_filename


def _config_data(tokens: list[str], intake_mode: str = "routed") -> dict:
    return {
        "schema_version": 2,
        "preset": "pixera",
        "show_name": "Maurice",
        "show_date": "2026-04-28",
        "operator": {"company_name": "Test Co", "name": "Op", "email": "op@test.com"},
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
        ],
        "validation_strictness": {
            "resolution": "strict",
            "framerate": "strict",
            "codec": "strict",
            "codec_flavor": "warn",
            "color_space": "ignore",
            "color_range": "ignore",
            "audio_sample_rate": "info",
            "audio_channels": "info",
            "screen_id": "strict",
            "filename_convention": "warn",
            "filename_format": "warn",
            "show_token": "warn",
        },
        "intake": {"mode": intake_mode},
        "output_specs": {"mode": "uniform"},
        "delivery": {"show_token": "Sky"},
        "filename_convention": {
            "enabled": True,
            "tokens": tokens,
            "version_prefix": "v",
            "date_format": "YYYYMMDD",
            "allow_loop_suffix": True,
            "loop_suffix": "-LOOP",
            "formats": {"version": {"prefix": "v", "digits": 2}},
        },
    }


def _config_with_convention() -> object:
    data = _config_data(["show_token", "screen", "content", "version", "date"])
    validate_config(data)
    return _build_show_config(data)


def _config_from_tokens(tokens: list[str], intake_mode: str = "routed") -> object:
    data = _config_data(tokens, intake_mode=intake_mode)
    validate_config(data)
    return _build_show_config(data)


def test_screen_first_without_show_token() -> None:
    config = _config_with_convention()
    result = parse_filename("SCR01_OpeningVideo_v01_20260428.mov", config)
    assert isinstance(result, PartialMatch), type(result)
    assert result.screen_prefix == "SCR01"
    assert any("show token" in p.lower() for p in result.problems)
    print("PASS  SCR01-first filename finds screen (missing show token -> partial)")


def test_canonical_order_full_match() -> None:
    config = _config_with_convention()
    result = parse_filename("Sky_SCR01_OpeningVideo-LOOP_v01_20260425.mov", config)
    assert isinstance(result, FullMatch), (type(result), getattr(result, "problems", None))
    assert result.parsed.screen_prefix == "SCR01"
    assert result.parsed.slug == "OpeningVideo-LOOP"
    assert result.parsed.show_token == "Sky"
    print("PASS  canonical token order -> full match")


def test_reordered_tokens_full_match() -> None:
    config = _config_with_convention()
    result = parse_filename("SCR01_OpeningVideo_v01_20260428_Sky.mov", config)
    assert isinstance(result, FullMatch), (type(result), getattr(result, "problems", None))
    assert result.parsed.screen_prefix == "SCR01"
    assert result.parsed.show_token == "Sky"
    print("PASS  reordered tokens -> full match")


def test_no_screen_is_no_match() -> None:
    config = _config_with_convention()
    result = parse_filename("OpeningVideo_v01_20260428.mov", config)
    assert isinstance(result, NoMatch)
    print("PASS  no screen token -> no match")


def test_config_accepts_partial_token_set() -> None:
    validate_config(_config_data(["screen", "content"], intake_mode="routed"))
    validate_config(_config_data(["content", "version"], intake_mode="flat"))
    print("PASS  config save accepts custom token subsets")


def test_screen_and_content_only_full_match() -> None:
    config = _config_from_tokens(["screen", "content"])
    result = parse_filename("SCR01_OpeningVideo.mov", config)
    assert isinstance(result, FullMatch), (type(result), getattr(result, "problems", None))
    assert result.parsed.screen_prefix == "SCR01"
    assert result.parsed.slug == "OpeningVideo"
    assert result.parsed.version == 0
    print("PASS  screen+content convention -> full match without version/date")


def test_flat_content_version_without_screen() -> None:
    config = _config_from_tokens(["content", "version"], intake_mode="flat")
    result = parse_filename("OpeningVideo_v01.mov", config)
    assert isinstance(result, FullMatch), (type(result), getattr(result, "problems", None))
    assert result.parsed.slug == "OpeningVideo"
    assert result.parsed.version == 1
    assert result.parsed.screen_prefix == ""
    print("PASS  flat content+version without screen -> full match")


def main() -> int:
    tests = [
        test_screen_first_without_show_token,
        test_canonical_order_full_match,
        test_reordered_tokens_full_match,
        test_no_screen_is_no_match,
        test_config_accepts_partial_token_set,
        test_screen_and_content_only_full_match,
        test_flat_content_version_without_screen,
    ]
    failures = 0
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {test.__name__}: {exc}")
    if failures:
        print(f"\n{failures} test(s) failed.")
        return 1
    print("\nAll filename parser tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
