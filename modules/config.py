"""Show config loading, validation, and creation."""

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from modules.filename_parser import ALLOWED_TOKENS, DEFAULT_TOKENS, ROUTING_TOKEN
from modules.media_formats import ExpectedMediaConfig, normalize_extension, parse_expected_media

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
    "filename_convention": "strict",
    "filename_format": "warn",
    "show_token": "strict",
}
_INTAKE_MODES = {"routed", "flat"}
_OUTPUT_SPEC_MODES = {"uniform", "per_screen"}
_PER_SCREEN_OUTPUT_FIELDS = ("framerate", "color_space", "color_range")
_SPEC_OVERRIDE_FIELDS = (
    "framerate", "color_space", "color_range", "audio_sample_rate", "audio_channels",
)


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
class ScreenExpectedSpecs:
    """Optional per-screen overrides; None fields inherit from show expected_specs."""
    framerate: float | None = None
    color_space: str | None = None
    color_range: str | None = None
    audio_sample_rate: int | None = None
    audio_channels: int | None = None


@dataclass
class ScreenConfig:
    """Configuration for a single screen: id, display name, resolution, and optional spec overrides."""
    id: str
    name: str
    resolution: str | None  # None when not specified
    expected_specs: ScreenExpectedSpecs | None = None


@dataclass
class OutputSpecsConfig:
    """Whether video output specs are uniform or defined per screen."""
    mode: str  # "uniform" | "per_screen"


@dataclass
class IntakeConfig:
    """How intake routes and validates incoming delivery files."""
    mode: str  # "routed" | "flat"


@dataclass
class DeliveryConfig:
    """Delivery-wide identifiers and vendor-facing spec notes."""
    show_token: str | None = None
    optional_screen_notes: str | None = None
    vendor_notes: str | None = None


@dataclass
class FilenameConventionConfig:
    """Configurable underscore-delimited filename token order and formats."""
    enabled: bool = False
    tokens: list[str] = field(default_factory=lambda: list(DEFAULT_TOKENS))
    version_prefix: str = "v"
    date_format: str = "YYYYMMDD"
    allow_loop_suffix: bool = True


@dataclass
class OperatorConfig:
    """Operator contact details written into the spec document."""
    name: str
    email: str
    company_name: str


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
    intake: IntakeConfig
    output_specs: OutputSpecsConfig
    delivery: DeliveryConfig
    filename_convention: FilenameConventionConfig
    expected_media: ExpectedMediaConfig = field(default_factory=ExpectedMediaConfig)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _opt_float(v: object) -> float | None:
    return float(v) if v is not None else None  # type: ignore[arg-type]


def _opt_int(v: object) -> int | None:
    return int(v) if v is not None else None  # type: ignore[arg-type]


def _validate_spec_overrides(specs: dict, label: str) -> None:
    """Validate an expected_specs object (show-level or per-screen overrides)."""
    if not isinstance(specs, dict):
        raise ConfigInvalidError(f"Field '{label}' must be an object")
    for field in _SPEC_OVERRIDE_FIELDS:
        if field not in specs:
            raise ConfigInvalidError(f"Missing required field: '{label}.{field}'")
    if specs["framerate"] is not None and not isinstance(specs["framerate"], (int, float)):
        raise ConfigInvalidError(f"Field '{label}.framerate' must be a number or null")
    if specs["audio_sample_rate"] is not None and not isinstance(specs["audio_sample_rate"], int):
        raise ConfigInvalidError(f"Field '{label}.audio_sample_rate' must be an integer or null")
    if specs["audio_channels"] is not None and not isinstance(specs["audio_channels"], int):
        raise ConfigInvalidError(f"Field '{label}.audio_channels' must be an integer or null")


def _parse_screen_expected_specs(data: object) -> ScreenExpectedSpecs | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        return None
    return ScreenExpectedSpecs(
        framerate=_opt_float(data.get("framerate")),
        color_space=data.get("color_space"),
        color_range=data.get("color_range"),
        audio_sample_rate=_opt_int(data.get("audio_sample_rate")),
        audio_channels=_opt_int(data.get("audio_channels")),
    )


def find_screen(config: ShowConfig, screen_id: str) -> ScreenConfig | None:
    """Return the screen with the given id, or None."""
    return next((s for s in config.screens if s.id == screen_id), None)


def effective_specs_for_screen(
    screen: ScreenConfig | None,
    config: ShowConfig,
) -> ExpectedSpecs:
    """Return expected specs for validating a file targeting the given screen."""
    show_specs = config.expected_specs
    if is_per_screen_output(config):
        if screen is None or screen.expected_specs is None:
            return ExpectedSpecs(
                framerate=None,
                color_space=None,
                color_range=None,
                audio_sample_rate=show_specs.audio_sample_rate,
                audio_channels=show_specs.audio_channels,
            )
        override = screen.expected_specs
        return ExpectedSpecs(
            framerate=override.framerate,
            color_space=override.color_space,
            color_range=override.color_range,
            audio_sample_rate=(
                override.audio_sample_rate
                if override.audio_sample_rate is not None
                else show_specs.audio_sample_rate
            ),
            audio_channels=(
                override.audio_channels
                if override.audio_channels is not None
                else show_specs.audio_channels
            ),
        )
    if screen is None or screen.expected_specs is None:
        return show_specs
    override = screen.expected_specs
    return ExpectedSpecs(
        framerate=override.framerate if override.framerate is not None else show_specs.framerate,
        color_space=override.color_space if override.color_space is not None else show_specs.color_space,
        color_range=override.color_range if override.color_range is not None else show_specs.color_range,
        audio_sample_rate=(
            override.audio_sample_rate
            if override.audio_sample_rate is not None
            else show_specs.audio_sample_rate
        ),
        audio_channels=(
            override.audio_channels
            if override.audio_channels is not None
            else show_specs.audio_channels
        ),
    )


def is_per_screen_output(config: ShowConfig) -> bool:
    """Return True when framerate/color specs are defined per screen."""
    return config.output_specs.mode == "per_screen"


def is_flat_intake(config: ShowConfig) -> bool:
    """Return True when intake uses flat mode (union validation, resolution routing)."""
    return config.intake.mode == "flat"


def filename_convention_enabled(config: ShowConfig) -> bool:
    """Return True when a custom filename convention is active."""
    return config.filename_convention.enabled


def strictness_level(config: ShowConfig, field: str) -> str:
    """Return the configured strictness for a field, or its optional default."""
    if field in config.validation_strictness:
        return config.validation_strictness[field]
    return _STRICTNESS_OPTIONAL.get(field, "strict")


def _parse_delivery(data: object) -> DeliveryConfig:
    if not isinstance(data, dict):
        return DeliveryConfig()
    token = data.get("show_token")
    show_token = str(token) if token not in (None, "") else None
    raw_screen_notes = data.get("optional_screen_notes")
    optional_screen_notes = str(raw_screen_notes).strip() if raw_screen_notes else None
    raw_notes = data.get("vendor_notes")
    vendor_notes = str(raw_notes).strip() if raw_notes else None
    return DeliveryConfig(
        show_token=show_token,
        optional_screen_notes=optional_screen_notes or None,
        vendor_notes=vendor_notes or None,
    )


def _parse_filename_convention(data: object) -> FilenameConventionConfig:
    if not isinstance(data, dict):
        return FilenameConventionConfig()
    enabled = bool(data.get("enabled", False))
    raw_tokens = data.get("tokens")
    tokens = list(raw_tokens) if isinstance(raw_tokens, list) and raw_tokens else list(DEFAULT_TOKENS)
    formats = data.get("formats") if isinstance(data.get("formats"), dict) else {}
    version_fmt = formats.get("version") if isinstance(formats.get("version"), dict) else {}
    content_fmt = formats.get("content") if isinstance(formats.get("content"), dict) else {}
    version_prefix = str(version_fmt.get("prefix", "v"))
    date_format = formats.get("date", "YYYYMMDD")
    if not isinstance(date_format, str):
        date_format = "YYYYMMDD"
    allow_loop_suffix = bool(content_fmt.get("allow_loop_suffix", True))
    return FilenameConventionConfig(
        enabled=enabled,
        tokens=tokens,
        version_prefix=version_prefix,
        date_format=date_format,
        allow_loop_suffix=allow_loop_suffix,
    )


def _validate_expected_media(data: dict) -> None:
    if "expected_media" not in data:
        return
    block = data["expected_media"]
    if not isinstance(block, dict):
        raise ConfigInvalidError("Field 'expected_media' must be an object")
    accept_stills = bool(block.get("accept_stills", False))
    raw_images = block.get("image_extensions")
    if raw_images is not None:
        if not isinstance(raw_images, list) or not raw_images:
            raise ConfigInvalidError(
                "Field 'expected_media.image_extensions' must be a non-empty array when set"
            )
        seen: set[str] = set()
        for ext in raw_images:
            normalized = normalize_extension(str(ext))
            if not normalized or len(normalized) < 2:
                raise ConfigInvalidError(
                    f"Invalid image extension: '{ext}' (use format like .png)"
                )
            if normalized in seen:
                raise ConfigInvalidError(
                    f"Duplicate image extension in expected_media.image_extensions: '{ext}'"
                )
            seen.add(normalized)
    if accept_stills and raw_images is None:
        pass  # defaults applied at parse
    raw_videos = block.get("video_extensions")
    if raw_videos is not None:
        if not isinstance(raw_videos, list) or not raw_videos:
            raise ConfigInvalidError(
                "Field 'expected_media.video_extensions' must be a non-empty array when set"
            )
        for ext in raw_videos:
            normalized = normalize_extension(str(ext))
            if not normalized or len(normalized) < 2:
                raise ConfigInvalidError(
                    f"Invalid video extension: '{ext}' (use format like .mov)"
                )


def _validate_filename_convention(data: dict) -> None:
    """Validate filename_convention and delivery.show_token when present."""
    if "delivery" in data:
        delivery = data["delivery"]
        if not isinstance(delivery, dict):
            raise ConfigInvalidError("Field 'delivery' must be an object")
        token = delivery.get("show_token")
        if token is not None and token != "":
            _require_filename_safe(str(token), "delivery.show_token")
        screen_notes = delivery.get("optional_screen_notes")
        if screen_notes is not None and screen_notes != "":
            if not isinstance(screen_notes, str):
                raise ConfigInvalidError("Field 'delivery.optional_screen_notes' must be a string")
            if len(str(screen_notes)) > 2000:
                raise ConfigInvalidError(
                    "Field 'delivery.optional_screen_notes' must be 2000 characters or fewer"
                )
        notes = delivery.get("vendor_notes")
        if notes is not None and notes != "":
            if not isinstance(notes, str):
                raise ConfigInvalidError("Field 'delivery.vendor_notes' must be a string")
            if len(str(notes)) > 4000:
                raise ConfigInvalidError(
                    "Field 'delivery.vendor_notes' must be 4000 characters or fewer"
                )

    if "filename_convention" not in data:
        return

    convention = data["filename_convention"]
    if not isinstance(convention, dict):
        raise ConfigInvalidError("Field 'filename_convention' must be an object")

    if not convention.get("enabled", False):
        return

    raw_tokens = convention.get("tokens")
    if not isinstance(raw_tokens, list) or not raw_tokens:
        raise ConfigInvalidError(
            "Field 'filename_convention.tokens' must be a non-empty array when enabled"
        )

    tokens = [str(t) for t in raw_tokens]
    if len(tokens) != len(set(tokens)):
        raise ConfigInvalidError("Field 'filename_convention.tokens' must not contain duplicates")

    unknown = set(tokens) - ALLOWED_TOKENS
    if unknown:
        raise ConfigInvalidError(
            f"Unknown filename tokens: {sorted(unknown)}. "
            f"Allowed: {', '.join(sorted(ALLOWED_TOKENS))}"
        )

    intake_mode = "routed"
    if "intake" in data and isinstance(data["intake"], dict):
        intake_mode = data["intake"].get("mode", "routed")
    if intake_mode == "routed" and ROUTING_TOKEN not in tokens:
        raise ConfigInvalidError(
            "'screen' token is required in filename_convention.tokens for routed intake"
        )

    if "show_token" in tokens:
        delivery = data.get("delivery") or {}
        show_token = delivery.get("show_token") if isinstance(delivery, dict) else None
        if not show_token:
            raise ConfigInvalidError(
                "delivery.show_token is required when 'show_token' is in filename_convention.tokens"
            )

    formats = convention.get("formats")
    if formats is not None:
        if not isinstance(formats, dict):
            raise ConfigInvalidError("Field 'filename_convention.formats' must be an object")
        version_fmt = formats.get("version")
        if version_fmt is not None:
            if not isinstance(version_fmt, dict):
                raise ConfigInvalidError("Field 'filename_convention.formats.version' must be an object")
            prefix = version_fmt.get("prefix", "v")
            if not isinstance(prefix, str) or not prefix:
                raise ConfigInvalidError(
                    "Field 'filename_convention.formats.version.prefix' must be a non-empty string"
                )
        date_fmt = formats.get("date")
        if date_fmt is not None and date_fmt != "YYYYMMDD":
            raise ConfigInvalidError(
                "Only YYYYMMDD date format is supported in v1 (filename_convention.formats.date)"
            )


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


def validate_config(data: dict, *, for_save: bool = True) -> None:
    """Validate a parsed config dict.

    When *for_save* is False, only checks that would block parsing are skipped —
    use :func:`load_config` for permissive reads. Full validation runs on save.
    """
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
    if for_save:
        company_name = str(operator.get("company_name", "")).strip()
        if not company_name:
            raise ConfigInvalidError("Field 'operator.company_name' is required")

    # Expected specs — null is allowed (means N/A); only validate type when non-null
    specs = _require(data, "expected_specs")
    _validate_spec_overrides(specs, "expected_specs")

    # Intake mode (optional; defaults to routed)
    if "intake" in data:
        intake = data["intake"]
        if not isinstance(intake, dict):
            raise ConfigInvalidError("Field 'intake' must be an object")
        mode = intake.get("mode", "routed")
        if mode not in _INTAKE_MODES:
            raise ConfigInvalidError(
                f"'intake.mode' must be one of: {', '.join(sorted(_INTAKE_MODES))}; got: '{mode}'"
            )

    # Output spec mode (optional; defaults to uniform)
    if "output_specs" in data:
        output_specs = data["output_specs"]
        if not isinstance(output_specs, dict):
            raise ConfigInvalidError("Field 'output_specs' must be an object")
        output_mode = output_specs.get("mode", "uniform")
        if output_mode not in _OUTPUT_SPEC_MODES:
            raise ConfigInvalidError(
                f"'output_specs.mode' must be one of: {', '.join(sorted(_OUTPUT_SPEC_MODES))}; "
                f"got: '{output_mode}'"
            )

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

        if "expected_specs" in screen and screen["expected_specs"] is not None:
            _validate_spec_overrides(screen["expected_specs"], f"screens[{i}].expected_specs")

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

    _validate_expected_media(data)
    _validate_filename_convention(data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(show_root: Path) -> ShowConfig:
    """Load show_config.json from show_root without save-time validation."""
    config_path = show_root / "show_config.json"
    if not config_path.exists():
        raise ConfigNotFoundError(f"No show_config.json found at: {show_root}")

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigInvalidError(f"show_config.json is not valid JSON: {exc}") from exc

    return _build_show_config(data)


def _build_show_config(data: dict) -> ShowConfig:
    """Build a ShowConfig from a parsed dict, filling defaults for missing fields."""
    raw_screens = data.get("screens")
    if not isinstance(raw_screens, list):
        raw_screens = []

    screens: list[ScreenConfig] = []
    for entry in raw_screens:
        if not isinstance(entry, dict):
            continue
        screen_id = str(entry.get("id", "") or "").strip()
        if not screen_id:
            continue
        screens.append(
            ScreenConfig(
                id=screen_id,
                name=str(entry.get("name", "") or ""),
                resolution=entry.get("resolution") or None,
                expected_specs=_parse_screen_expected_specs(entry.get("expected_specs")),
            )
        )

    operator = data.get("operator") if isinstance(data.get("operator"), dict) else {}
    sd = data.get("expected_specs") if isinstance(data.get("expected_specs"), dict) else {}
    intake_data = data.get("intake") or {}
    intake_mode = intake_data.get("mode", "routed") if isinstance(intake_data, dict) else "routed"
    if intake_mode not in _INTAKE_MODES:
        intake_mode = "routed"
    output_data = data.get("output_specs") or {}
    output_mode = (
        output_data.get("mode", "uniform") if isinstance(output_data, dict) else "uniform"
    )
    if output_mode not in _OUTPUT_SPEC_MODES:
        output_mode = "uniform"

    strictness = data.get("validation_strictness")
    if not isinstance(strictness, dict):
        strictness = {}

    expected_codecs = data.get("expected_codecs")
    preferred_codecs = data.get("preferred_codecs")

    return ShowConfig(
        schema_version=int(data.get("schema_version", 1) or 1),
        preset=str(data.get("preset", "pixera") or "pixera"),
        show_name=str(data.get("show_name", "") or ""),
        show_date=str(data.get("show_date", "") or ""),
        operator=OperatorConfig(
            name=str(operator.get("name", "") or ""),
            email=str(operator.get("email", "") or ""),
            company_name=str(operator.get("company_name", "") or "").strip(),
        ),
        expected_specs=ExpectedSpecs(
            framerate=_opt_float(sd.get("framerate")),
            color_space=sd.get("color_space"),
            color_range=sd.get("color_range"),
            audio_sample_rate=_opt_int(sd.get("audio_sample_rate")),
            audio_channels=_opt_int(sd.get("audio_channels")),
        ),
        expected_codecs=list(expected_codecs) if isinstance(expected_codecs, list) else [],
        preferred_codecs=list(preferred_codecs) if isinstance(preferred_codecs, list) else [],
        screens=screens,
        validation_strictness={**_STRICTNESS_OPTIONAL, **strictness},
        intake=IntakeConfig(mode=intake_mode),
        output_specs=OutputSpecsConfig(mode=output_mode),
        delivery=_parse_delivery(data.get("delivery")),
        filename_convention=_parse_filename_convention(data.get("filename_convention")),
        expected_media=parse_expected_media(data.get("expected_media")),
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
    validate_config(data, for_save=True)
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
    operator = migrated.get("operator")
    if isinstance(operator, dict):
        operator.setdefault("company_name", "REPLACE_WITH_COMPANY_NAME")
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
