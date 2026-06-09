"""Show config loading, validation, and creation."""

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

# Only letters, digits, hyphens, underscores — no spaces or special characters.
FILENAME_SAFE = re.compile(r"^[A-Za-z0-9_-]+$")

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RESOLUTION_RE = re.compile(r"^\d+x\d+$")
_STRICTNESS_VALUES = {"strict", "warn", "info", "ignore"}
_STRICTNESS_FIELDS = (
    "resolution", "framerate", "codec", "codec_flavor",
    "color_space", "color_range", "audio_sample_rate", "audio_channels",
)
# Optional fields introduced after v1; validated if present, defaulted if absent.
_STRICTNESS_OPTIONAL = {
    "screen_id": "strict",
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ConfigError(Exception):
    """Base class for all config errors."""


class ConfigNotFoundError(ConfigError):
    """show_config.json does not exist at the given path."""


class ConfigInvalidError(ConfigError):
    """show_config.json exists but fails validation."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScreenConfig:
    """Configuration for a single screen: id, display name, and expected resolution."""
    id: str
    name: str
    resolution: str | None  # None when not specified


@dataclass
class OperatorConfig:
    """Operator contact details written into the spec document."""
    name: str
    email: str


@dataclass
class ExpectedSpecs:
    """Tech-spec expectations used for intake validation. Any field may be None (N/A)."""
    framerate: float | None
    color_space: str | None
    color_range: str | None
    audio_sample_rate: int | None
    audio_channels: int | None


@dataclass
class ShowConfig:
    """Fully validated show configuration loaded from show_config.json."""
    schema_version: int
    preset: str
    show_name: str
    show_date: str
    operator: OperatorConfig
    expected_specs: ExpectedSpecs
    expected_codecs: list[str]
    preferred_codecs: list[str]
    screens: list[ScreenConfig]
    validation_strictness: dict[str, str]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _require(data: dict, key: str, parent: str = "") -> object:
    """Return data[key], raising ConfigInvalidError if missing or empty."""
    label = f"{parent}.{key}" if parent else key
    if key not in data:
        raise ConfigInvalidError(f"Missing required field: '{label}'")
    value = data[key]
    if value is None or value == "" or value == [] or value == {}:
        raise ConfigInvalidError(f"Field '{label}' must not be empty")
    return value


def _require_filename_safe(value: str, label: str) -> None:
    if not FILENAME_SAFE.match(value):
        raise ConfigInvalidError(
            f"Field '{label}' contains invalid characters: '{value}'. "
            "Only letters, digits, hyphens, and underscores are allowed."
        )


def validate_config(data: dict) -> None:
    """Validate a parsed config dict. Raises ConfigInvalidError on any problem."""
    # Schema version: absent = v1 (migration flow handles it); present = must be 2
    if "schema_version" in data:
        sv = data["schema_version"]
        if sv != 2:
            raise ConfigInvalidError(
                f"Unsupported schema_version: {sv!r} (expected 2)"
            )

    # Preset: informational only; validate type if present
    if "preset" in data and data["preset"] is not None:
        if not isinstance(data["preset"], str) or not data["preset"].strip():
            raise ConfigInvalidError("Field 'preset' must be a non-empty string")

    # Top-level required fields
    show_name = str(_require(data, "show_name"))
    _require_filename_safe(show_name, "show_name")

    show_date = str(_require(data, "show_date"))
    if not _DATE_RE.match(show_date):
        raise ConfigInvalidError(
            f"Field 'show_date' must be YYYY-MM-DD, got: '{show_date}'"
        )

    # Operator
    operator = _require(data, "operator")
    if not isinstance(operator, dict):
        raise ConfigInvalidError("Field 'operator' must be an object")
    _require(operator, "name", "operator")
    _require(operator, "email", "operator")

    # Expected specs — null is allowed (means N/A); only validate type when non-null
    specs = _require(data, "expected_specs")
    if not isinstance(specs, dict):
        raise ConfigInvalidError("Field 'expected_specs' must be an object")
    for field in ("framerate", "color_space", "color_range", "audio_sample_rate", "audio_channels"):
        if field not in specs:
            raise ConfigInvalidError(f"Missing required field: 'expected_specs.{field}'")
    if specs["framerate"] is not None and not isinstance(specs["framerate"], (int, float)):
        raise ConfigInvalidError("Field 'expected_specs.framerate' must be a number or null")
    if specs["audio_sample_rate"] is not None and not isinstance(specs["audio_sample_rate"], int):
        raise ConfigInvalidError("Field 'expected_specs.audio_sample_rate' must be an integer or null")
    if specs["audio_channels"] is not None and not isinstance(specs["audio_channels"], int):
        raise ConfigInvalidError("Field 'expected_specs.audio_channels' must be an integer or null")

    # Codecs
    expected_codecs = _require(data, "expected_codecs")
    if not isinstance(expected_codecs, list) or not expected_codecs:
        raise ConfigInvalidError("Field 'expected_codecs' must be a non-empty array")

    preferred_codecs = _require(data, "preferred_codecs")
    if not isinstance(preferred_codecs, list) or not preferred_codecs:
        raise ConfigInvalidError("Field 'preferred_codecs' must be a non-empty array")

    unexpected = set(preferred_codecs) - set(expected_codecs)
    if unexpected:
        raise ConfigInvalidError(
            f"'preferred_codecs' contains values not in 'expected_codecs': {sorted(unexpected)}"
        )

    # Screens
    if "screens" not in data:
        raise ConfigInvalidError("Missing required field: 'screens'")
    screens = data["screens"]
    if not isinstance(screens, list):
        raise ConfigInvalidError("Field 'screens' must be an array")
    # Empty screens array is valid — screens are defined later via Config Editor

    seen_ids: set[str] = set()
    for i, screen in enumerate(screens):
        if not isinstance(screen, dict):
            raise ConfigInvalidError(f"screens[{i}] must be an object")
        screen_id = str(_require(screen, "id", f"screens[{i}]"))
        _require_filename_safe(screen_id, f"screens[{i}].id")
        if screen_id in seen_ids:
            raise ConfigInvalidError(f"Duplicate screen id: '{screen_id}'")
        seen_ids.add(screen_id)

        if "name" in screen and screen["name"]:
            _require_filename_safe(str(screen["name"]), f"screens[{i}].name")

        if "resolution" in screen and screen["resolution"]:
            res = str(screen["resolution"])
            if not _RESOLUTION_RE.match(res):
                raise ConfigInvalidError(
                    f"screens[{i}].resolution must be ####x#### format, got: '{res}'"
                )

    # Validation strictness
    strictness = _require(data, "validation_strictness")
    if not isinstance(strictness, dict):
        raise ConfigInvalidError("Field 'validation_strictness' must be an object")
    for field in _STRICTNESS_FIELDS:
        if field not in strictness:
            raise ConfigInvalidError(f"Missing 'validation_strictness.{field}'")
        val = strictness[field]
        if val not in _STRICTNESS_VALUES:
            raise ConfigInvalidError(
                f"'validation_strictness.{field}' must be one of: strict, warn, info, ignore; got: '{val}'"
            )
    for field in _STRICTNESS_OPTIONAL:
        if field in strictness and strictness[field] not in _STRICTNESS_VALUES:
            raise ConfigInvalidError(
                f"'validation_strictness.{field}' must be one of: strict, warn, info, ignore; got: '{strictness[field]}'"
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(show_root: Path) -> ShowConfig:
    """Load and validate show_config.json from show_root. Returns a ShowConfig."""
    config_path = show_root / "show_config.json"
    if not config_path.exists():
        raise ConfigNotFoundError(f"No show_config.json found at: {show_root}")

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigInvalidError(f"show_config.json is not valid JSON: {exc}") from exc

    validate_config(data)

    screens = [
        ScreenConfig(
            id=s["id"],
            name=s.get("name", ""),
            resolution=s.get("resolution") or None,
        )
        for s in data["screens"]
    ]

    sd = data["expected_specs"]

    def _opt_float(v: object) -> float | None:
        return float(v) if v is not None else None  # type: ignore[arg-type]

    def _opt_int(v: object) -> int | None:
        return int(v) if v is not None else None  # type: ignore[arg-type]

    return ShowConfig(
        schema_version=data.get("schema_version", 1),
        preset=data.get("preset", "pixera"),
        show_name=data["show_name"],
        show_date=data["show_date"],
        operator=OperatorConfig(
            name=data["operator"]["name"],
            email=data["operator"]["email"],
        ),
        expected_specs=ExpectedSpecs(
            framerate=_opt_float(sd["framerate"]),
            color_space=sd["color_space"],
            color_range=sd["color_range"],
            audio_sample_rate=_opt_int(sd["audio_sample_rate"]),
            audio_channels=_opt_int(sd["audio_channels"]),
        ),
        expected_codecs=list(data["expected_codecs"]),
        preferred_codecs=list(data["preferred_codecs"]),
        screens=screens,
        validation_strictness={**_STRICTNESS_OPTIONAL, **data["validation_strictness"]},
    )


def create_starter_config(show_root: Path) -> Path:
    """Copy the starter config template into show_root/show_config.json. Returns the new path."""
    dest = show_root / "show_config.json"
    if dest.exists():
        raise ConfigError(f"show_config.json already exists at: {dest}")
    source = _TEMPLATES_DIR / "show_config_starter.json"
    shutil.copy2(source, dest)
    return dest


def save_config(show_root: Path, data: dict) -> Path:
    """Validate and write show_config.json. Returns the config path."""
    validate_config(data)
    config_path = show_root / "show_config.json"
    config_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return config_path


def read_config_dict(show_root: Path) -> dict:
    """Load show_config.json as a parsed dict without building ShowConfig."""
    config_path = show_root / "show_config.json"
    if not config_path.exists():
        raise ConfigNotFoundError(f"No show_config.json found at: {show_root}")
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigInvalidError(f"show_config.json is not valid JSON: {exc}") from exc


# ---------------------------------------------------------------------------
# v1 → v2 helpers
# ---------------------------------------------------------------------------

def is_v1_config(data: dict) -> bool:
    """Return True if data lacks a schema_version field (i.e., was written by v1)."""
    return "schema_version" not in data


def migrate_v1_to_v2(data: dict) -> dict:
    """Return a new dict with schema_version=2 and preset='pixera' prepended.

    All existing fields are preserved exactly. The original dict is not mutated.
    """
    migrated: dict = {"schema_version": 2, "preset": "pixera"}
    migrated.update(data)
    return migrated


def migrate_v1_config(show_root: Path) -> Path:
    """Migrate a v1 show_config.json to v2 in place, writing a backup first.

    Steps:
        1. Read and parse show_config.json (raises ConfigInvalidError if not valid JSON).
        2. Verify the config is v1 (raises ConfigError if schema_version already present).
        3. Write backup to show_config.v1.bak.json (raises ConfigError if it already exists).
        4. Write the v2 config back to show_config.json.

    Returns:
        Path to the backup file.

    Raises:
        ConfigNotFoundError: show_config.json does not exist.
        ConfigInvalidError:  show_config.json is not valid JSON.
        ConfigError:         Config is already v2, or backup file already exists.
    """
    config_path = show_root / "show_config.json"
    backup_path = show_root / "show_config.v1.bak.json"

    if not config_path.exists():
        raise ConfigNotFoundError(f"No show_config.json found at: {show_root}")

    # Parse first — no writes until we know the file is valid JSON
    try:
        original_text = config_path.read_text(encoding="utf-8")
        data = json.loads(original_text)
    except json.JSONDecodeError as exc:
        raise ConfigInvalidError(
            f"show_config.json is not valid JSON and cannot be migrated: {exc}"
        ) from exc

    if not is_v1_config(data):
        raise ConfigError(
            "show_config.json already has a schema_version field — migration is not needed."
        )

    if backup_path.exists():
        raise ConfigError(
            f"Backup file already exists: {backup_path.name}\n"
            "Remove or rename it manually, then retry migration."
        )

    # Write backup before touching the original
    backup_path.write_text(original_text, encoding="utf-8")

    # Build v2 dict and overwrite the original
    v2_data = migrate_v1_to_v2(data)
    config_path.write_text(
        json.dumps(v2_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return backup_path
