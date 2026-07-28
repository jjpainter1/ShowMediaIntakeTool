"""Tests for still image and image-sequence intake support."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.config import _build_show_config, validate_config
from modules.ffprobe_wrapper import MediaSpecs
from modules.intake import validate_file_specs, validate_file_specs_flat
from modules.media_formats import (
    group_image_sequence_paths,
    image_sequence_key,
    partition_image_sequences,
    strip_sequence_frame_suffix,
)
from modules.show_report import _list_folder_files, _parse_folder


def _base_config_data() -> dict:
    return {
        "schema_version": 2,
        "preset": "pixera",
        "show_name": "TestShow",
        "show_date": "2026-07-27",
        "operator": {"company_name": "Co", "name": "Op", "email": "op@test.com"},
        "expected_specs": {
            "framerate": 30,
            "color_space": "bt709",
            "color_range": "tv",
            "audio_sample_rate": 48000,
            "audio_channels": 2,
        },
        "expected_codecs": ["prores_422_hq"],
        "preferred_codecs": ["prores_422_hq"],
        "screens": [{"id": "SCR01", "name": "Main", "resolution": "1920x1080"}],
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
            "filename_convention": "strict",
            "filename_format": "warn",
            "show_token": "strict",
        },
        "intake": {"mode": "routed"},
        "output_specs": {"mode": "uniform"},
        "expected_media": {
            "accept_stills": True,
            "image_extensions": [".png", ".tga"],
            "allow_image_sequences": True,
        },
    }


def test_config_accepts_expected_media() -> None:
    validate_config(_base_config_data())
    print("PASS  config accepts expected_media block")


def test_still_image_skips_codec_validation() -> None:
    config = _build_show_config(_base_config_data())
    specs = MediaSpecs(
        width=1920,
        height=1080,
        framerate=None,
        codec_name="png",
        codec_tag=None,
        color_space=None,
        color_range=None,
        audio_sample_rate=None,
        audio_channels=None,
        duration_seconds=None,
        media_kind="image",
        probe_succeeded=True,
        probe_error=None,
    )
    warnings: list[str] = []
    failures: list[str] = []
    validate_file_specs(
        specs,
        config,
        warnings,
        failures,
        target_screen_id="SCR01",
    )
    assert not any("codec" in message.lower() for message in failures + warnings)
    print("PASS  still image skips codec/framerate validation")


def test_still_wrong_resolution_fails() -> None:
    config = _build_show_config(_base_config_data())
    specs = MediaSpecs(
        width=1280,
        height=720,
        framerate=None,
        codec_name="png",
        codec_tag=None,
        color_space=None,
        color_range=None,
        audio_sample_rate=None,
        audio_channels=None,
        duration_seconds=None,
        media_kind="image",
        probe_succeeded=True,
        probe_error=None,
    )
    failures: list[str] = []
    validate_file_specs(
        specs,
        config,
        [],
        failures,
        target_screen_id="SCR01",
    )
    assert failures
    assert any("resolution" in message.lower() for message in failures)
    print("PASS  still image resolution mismatch fails")


def test_flat_still_union_resolution() -> None:
    data = _base_config_data()
    data["intake"] = {"mode": "flat"}
    config = _build_show_config(data)
    specs = MediaSpecs(
        width=1920,
        height=1080,
        framerate=None,
        codec_name="png",
        codec_tag=None,
        color_space=None,
        color_range=None,
        audio_sample_rate=None,
        audio_channels=None,
        duration_seconds=None,
        media_kind="image",
        probe_succeeded=True,
        probe_error=None,
    )
    failures: list[str] = []
    validate_file_specs_flat(specs, config, [], failures)
    assert not failures
    print("PASS  flat still image passes union resolution check")


def test_sequence_helpers() -> None:
    assert image_sequence_key(Path("SCR01_Fire_0001.tga")) == ("scr01_fire", ".tga")
    assert strip_sequence_frame_suffix("SCR01_Fire_0001.tga") == "SCR01_Fire.tga"
    assert image_sequence_key(Path("SCR01_Opening_v01_20260428.mov")) is None
    print("PASS  sequence suffix helpers")


def test_partition_image_sequences() -> None:
    config = _build_show_config(_base_config_data())
    files = [
        Path("SCR01_Fire_0001.tga"),
        Path("SCR01_Fire_0002.tga"),
        Path("SCR01_Backdrop.png"),
        Path("SCR01_Opening.mov"),
    ]
    sequences, singletons = partition_image_sequences(files, config)
    assert len(sequences) == 1
    assert len(sequences[0]) == 2
    assert len(singletons) == 2
    print("PASS  partition groups sequence frames")


def test_partition_sequences_when_stills_disabled() -> None:
    data = _base_config_data()
    data["expected_media"] = {
        "accept_stills": False,
        "image_extensions": [".png"],
        "allow_image_sequences": True,
    }
    config = _build_show_config(data)
    files = [
        Path("SCR03_ImageSeq_v01_20260728_00000.png"),
        Path("SCR03_ImageSeq_v01_20260728_00001.png"),
        Path("SCR03_ImageSTILL_v01_20260728.png"),
    ]
    sequences, singletons = partition_image_sequences(files, config)
    assert len(sequences) == 1
    assert len(sequences[0]) == 2
    assert len(singletons) == 1
    print("PASS  partition sequences when stills disabled in config")


def test_partition_sequences_when_extension_unchecked() -> None:
    data = _base_config_data()
    data["expected_media"] = {
        "accept_stills": True,
        "image_extensions": [".tga"],
        "allow_image_sequences": True,
    }
    config = _build_show_config(data)
    files = [
        Path("SCR03_ImageSeq_v01_20260728_00000.png"),
        Path("SCR03_ImageSeq_v01_20260728_00001.png"),
    ]
    sequences, singletons = partition_image_sequences(files, config)
    assert len(sequences) == 1
    assert len(sequences[0]) == 2
    assert not singletons
    print("PASS  partition png sequence when png unchecked in accepted list")


def test_dashboard_groups_sequences_logical_count() -> None:
    import tempfile

    data = _base_config_data()
    data["screens"].append({"id": "SCR03", "name": "720p", "resolution": "1280x720"})
    config = _build_show_config(data)

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for index in range(5):
            (folder / f"SCR03_ImageSeq_v01_20260728_{index:05d}.png").write_bytes(b"x")
        (folder / "SCR03_ImageSTILL_v01_20260728.png").write_bytes(b"y")

        parsed, unparsed = _parse_folder(folder, config)
        logical_count = len(parsed) + len(unparsed)
        assert logical_count == 2

        entries = _list_folder_files(folder)
        assert len(entries) == 2
        assert entries[0].filename.endswith(".png")
        assert sum(entry.size_bytes for entry in entries) == 6

    print("PASS  dashboard snapshot counts one row per image sequence")


def test_file_plan_serializes_sequence_paths() -> None:
    from backend.serializers import file_plan_from_dict, file_plan_to_dict
    from modules.filename_parser import NoMatch
    from modules.intake import FilePlan, Action

    paths = [
        Path("SCR03_ImageSeq_v01_20260728_00000.png"),
        Path("SCR03_ImageSeq_v01_20260728_00001.png"),
    ]
    plan = FilePlan(
        source_path=paths[0],
        parsed=NoMatch(original=paths[0].name, problems=[]),
        specs=None,
        target_screen="SCR03",
        destination_path=Path("Media/SCR03/SCR03_ImageSeq_v01_20260728_00000.png"),
        action=Action.COPY,
        sequence_paths=paths,
        media_kind="image_sequence",
        infos=["Image sequence: 2 frames"],
    )
    data = file_plan_to_dict(plan)
    assert len(data["sequence_paths"]) == 2
    restored = file_plan_from_dict(data)
    assert len(restored.sequence_paths) == 2
    assert restored.infos == ["Image sequence: 2 frames"]
    print("PASS  file plan round-trip preserves sequence_paths")


def test_atomic_copy_reports_byte_progress() -> None:
    import tempfile

    from modules.intake import atomic_copy

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "big.bin"
        source.write_bytes(b"x" * (17 * 1024 * 1024))
        destination = root / "dest.bin"

        updates: list[tuple[int, int]] = []
        ok = atomic_copy(
            source,
            destination,
            progress=lambda copied, total: updates.append((copied, total)),
        )
        assert ok
        assert destination.is_file()
        assert updates
        assert updates[-1] == (source.stat().st_size, source.stat().st_size)
        assert any(copied < source.stat().st_size for copied, _ in updates)
    print("PASS  atomic copy reports byte progress during transfer")


def main() -> int:
    tests = [
        test_config_accepts_expected_media,
        test_still_image_skips_codec_validation,
        test_still_wrong_resolution_fails,
        test_flat_still_union_resolution,
        test_sequence_helpers,
        test_partition_image_sequences,
        test_partition_sequences_when_stills_disabled,
        test_partition_sequences_when_extension_unchecked,
        test_dashboard_groups_sequences_logical_count,
        test_atomic_copy_reports_byte_progress,
        test_file_plan_serializes_sequence_paths,
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
    print("\nAll media intake tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
