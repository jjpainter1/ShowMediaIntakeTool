"""Preset system for Show Media Intake Tool.

Built-in presets live in templates/presets/ alongside the install.
Custom presets live in %LOCALAPPDATA%\\ShowMediaIntakeTool\\custom_presets\\.

The preset_name field inside the JSON is the canonical display name.
Filenames are derived from display names with spaces converted to underscores
and non-alphanumeric characters stripped.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.paths import get_user_data_root

_BUILTIN_DIR = Path(__file__).parent.parent / "templates" / "presets"

# Filenames that are authoritative built-in presets.  Files in _BUILTIN_DIR
# that don't appear here are silently skipped so the install directory can
# contain README or other non-preset files without causing errors.
_BUILTIN_FILENAMES: frozenset[str] = frozenset({"pixera.json", "playbackpro.json", "mitti.json"})

# Lower-cased display names of built-in presets — used to block custom presets
# from overwriting them.
_BUILTIN_DISPLAY_NAMES: frozenset[str] = frozenset({"pixera", "playback pro", "mitti"})

# Required fields in every preset JSON file.
_REQUIRED_FIELDS = (
    "preset_name",
    "expected_specs",
    "expected_codecs",
    "preferred_codecs",
    "validation_strictness",
)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class PresetError(Exception):
    """Raised for invalid preset data or conflicting preset operations."""


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class Preset:
    """A single preset loaded from a JSON file."""
    preset_name: str
    preset_description: str
    expected_specs: dict[str, Any]
    expected_codecs: list[str]
    preferred_codecs: list[str]
    validation_strictness: dict[str, str]
    source_path: Path | None = None  # None when built from config data in memory


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_preset_data(data: dict, source: str) -> None:
    """Raise PresetError if data is missing required fields or has bad types."""
    for field in _REQUIRED_FIELDS:
        if field not in data:
            raise PresetError(f"Preset '{source}' is missing required field: '{field}'")

    if not isinstance(data["preset_name"], str) or not data["preset_name"].strip():
        raise PresetError(f"Preset '{source}': 'preset_name' must be a non-empty string")

    if not isinstance(data["expected_specs"], dict):
        raise PresetError(f"Preset '{source}': 'expected_specs' must be an object")

    if not isinstance(data["expected_codecs"], list):
        raise PresetError(f"Preset '{source}': 'expected_codecs' must be an array")

    if not isinstance(data["preferred_codecs"], list):
        raise PresetError(f"Preset '{source}': 'preferred_codecs' must be an array")

    if not isinstance(data["validation_strictness"], dict):
        raise PresetError(f"Preset '{source}': 'validation_strictness' must be an object")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_preset_file(path: Path) -> Preset:
    """Read, parse, validate, and return a Preset from a JSON file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PresetError(f"Preset file '{path.name}' is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise PresetError(f"Cannot read preset file '{path}': {exc}") from exc

    _validate_preset_data(data, path.name)

    return Preset(
        preset_name=data["preset_name"],
        preset_description=data.get("preset_description", ""),
        expected_specs=dict(data["expected_specs"]),
        expected_codecs=list(data["expected_codecs"]),
        preferred_codecs=list(data["preferred_codecs"]),
        validation_strictness=dict(data["validation_strictness"]),
        source_path=path,
    )


def _get_custom_presets_dir() -> Path:
    """Return the custom presets directory, creating it if needed."""
    custom_dir = get_user_data_root() / "custom_presets"
    custom_dir.mkdir(parents=True, exist_ok=True)
    return custom_dir


def _name_to_filename(name: str) -> str:
    """Convert a display name to a filename stem (no extension).

    Spaces → underscores.  Non-alphanumeric/non-hyphen/non-underscore chars
    are stripped.  Result is stripped of leading/trailing underscores.
    """
    safe = re.sub(r"[^A-Za-z0-9_\- ]", "", name)
    return safe.strip().replace(" ", "_")


# ---------------------------------------------------------------------------
# Public API — loading
# ---------------------------------------------------------------------------

def load_builtin_presets() -> list[Preset]:
    """Load the three built-in presets from templates/presets/.

    Only the filenames in _BUILTIN_FILENAMES are loaded; any other files in
    the directory are silently skipped.  Presets are returned in alphabetical
    order by filename.
    """
    presets: list[Preset] = []
    for filename in sorted(_BUILTIN_FILENAMES):
        path = _BUILTIN_DIR / filename
        if not path.exists():
            raise PresetError(
                f"Built-in preset file missing from install: '{path}'. "
                "Re-install the tool to restore it."
            )
        presets.append(_load_preset_file(path))
    return presets


def load_custom_presets() -> list[Preset]:
    """Load all custom presets from the user's custom_presets directory.

    Invalid files are silently skipped (logged as warnings via Python's
    warnings module in caller code if needed).  Returns presets sorted
    alphabetically by filename.
    """
    custom_dir = _get_custom_presets_dir()
    presets: list[Preset] = []
    for path in sorted(custom_dir.glob("*.json")):
        try:
            presets.append(_load_preset_file(path))
        except PresetError:
            pass  # skip corrupt custom preset files without crashing
    return presets


def load_all_presets() -> tuple[list[Preset], list[Preset]]:
    """Return (built_in_presets, custom_presets) as two sorted lists."""
    return load_builtin_presets(), load_custom_presets()


def load_preset_from_path(path: Path) -> Preset:
    """Load and validate a preset JSON file from an arbitrary path."""
    return _load_preset_file(path)


# ---------------------------------------------------------------------------
# Public API — applying and saving
# ---------------------------------------------------------------------------

def apply_preset(config_data: dict, preset: Preset) -> dict:
    """Return a new config dict with preset fields applied.

    Overwrites expected_specs, expected_codecs, preferred_codecs, and
    validation_strictness from the preset.  Show-specific fields
    (show_name, show_date, screens, operator) are left untouched.
    Sets the informational 'preset' field to the preset's display name.
    The original config_data dict is not mutated.
    """
    result = dict(config_data)
    result["expected_specs"] = dict(preset.expected_specs)
    result["expected_codecs"] = list(preset.expected_codecs)
    result["preferred_codecs"] = list(preset.preferred_codecs)
    result["validation_strictness"] = dict(preset.validation_strictness)
    result["preset"] = preset.preset_name
    return result


def save_custom_preset(preset_name: str, config_data: dict) -> Path:
    """Extract preset-relevant fields from config_data and save as a custom preset.

    Args:
        preset_name: Display name for the preset (e.g. "My Mitti Config").
        config_data: A config dict whose spec/codec/strictness fields are used.

    Returns:
        Path to the written preset file.

    Raises:
        PresetError: If the name conflicts with a built-in preset name, if the
            name produces an empty filename, or if the file cannot be written.
    """
    if preset_name.lower() in _BUILTIN_DISPLAY_NAMES:
        raise PresetError(
            f"'{preset_name}' is a built-in preset name and cannot be used for a custom preset. "
            "Choose a different name."
        )

    safe_stem = _name_to_filename(preset_name)
    if not safe_stem:
        raise PresetError(
            f"Preset name '{preset_name}' produces an empty filename after sanitisation. "
            "Use letters, digits, spaces, hyphens, or underscores."
        )

    preset_data = {
        "preset_name": preset_name,
        "preset_description": f"Custom preset: {preset_name}",
        "expected_specs": config_data.get("expected_specs", {}),
        "expected_codecs": config_data.get("expected_codecs", []),
        "preferred_codecs": config_data.get("preferred_codecs", []),
        "validation_strictness": config_data.get("validation_strictness", {}),
    }

    dest = _get_custom_presets_dir() / f"{safe_stem}.json"
    try:
        dest.write_text(json.dumps(preset_data, indent=2), encoding="utf-8")
    except OSError as exc:
        raise PresetError(f"Could not write custom preset to '{dest}': {exc}") from exc

    return dest


def custom_preset_exists(preset_name: str) -> bool:
    """Return True if a custom preset file already exists for this display name."""
    safe_stem = _name_to_filename(preset_name)
    if not safe_stem:
        return False
    return (_get_custom_presets_dir() / f"{safe_stem}.json").exists()
