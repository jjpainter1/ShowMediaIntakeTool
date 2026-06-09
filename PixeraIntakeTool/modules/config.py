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
_STRICTNESS_VALUES = {"strict", "warn", "info"}
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
    """Tech-spec expectations used for intake validation."""
    framerate: float
    color_space: str
    color_range: str
    audio_sample_rate: int
    audio_channels: int


@dataclass
class ShowConfig:
    """Fully validated show configuration loaded from show_config.json."""
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

    # Expected specs
    specs = _require(data, "expected_specs")
    if not isinstance(specs, dict):
        raise ConfigInvalidError("Field 'expected_specs' must be an object")
    for field in ("framerate", "color_space", "color_range", "audio_sample_rate", "audio_channels"):
        _require(specs, field, "expected_specs")
    if not isinstance(specs["framerate"], (int, float)):
        raise ConfigInvalidError("Field 'expected_specs.framerate' must be a number")
    if not isinstance(specs["audio_sample_rate"], int):
        raise ConfigInvalidError("Field 'expected_specs.audio_sample_rate' must be an integer")
    if not isinstance(specs["audio_channels"], int):
        raise ConfigInvalidError("Field 'expected_specs.audio_channels' must be an integer")

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
    screens = _require(data, "screens")
    if not isinstance(screens, list) or not screens:
        raise ConfigInvalidError("Field 'screens' must be a non-empty array")

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
                f"'validation_strictness.{field}' must be 'strict', 'warn', or 'info', got: '{val}'"
            )
    for field in _STRICTNESS_OPTIONAL:
        if field in strictness and strictness[field] not in _STRICTNESS_VALUES:
            raise ConfigInvalidError(
                f"'validation_strictness.{field}' must be 'strict', 'warn', or 'info', got: '{strictness[field]}'"
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

    return ShowConfig(
        show_name=data["show_name"],
        show_date=data["show_date"],
        operator=OperatorConfig(
            name=data["operator"]["name"],
            email=data["operator"]["email"],
        ),
        expected_specs=ExpectedSpecs(
            framerate=float(data["expected_specs"]["framerate"]),
            color_space=data["expected_specs"]["color_space"],
            color_range=data["expected_specs"]["color_range"],
            audio_sample_rate=int(data["expected_specs"]["audio_sample_rate"]),
            audio_channels=int(data["expected_specs"]["audio_channels"]),
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
