"""Filename convention parsing and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules.config import ShowConfig

# ---------------------------------------------------------------------------
# Regex building blocks (Pixera defaults + shared patterns)
# ---------------------------------------------------------------------------

_SCR_NUM = r"SCR\d{2}"
_SCR_WIDE = r"SCRwide(?:-\d{2})+"
_SCR_ALL = r"SCRall"
_AUD = r"AUD"

_PREFIX_STRICT_PAT = rf"(?:{_SCR_NUM}|{_SCR_WIDE}|{_SCR_ALL}|{_AUD})"
_SLUG_PAT = r"[A-Za-z0-9][A-Za-z0-9-]*"
_VERSION_PAT = r"v\d+"
_DATE_PAT = r"\d{8}"
_INITIALS_PAT = r"[A-Za-z]{2,3}"

_FULL_RE = re.compile(
    rf"^({_PREFIX_STRICT_PAT})_({_SLUG_PAT})_({_VERSION_PAT})_({_DATE_PAT})$"
)
_PREFIX_STRICT_RE = re.compile(rf"^({_PREFIX_STRICT_PAT})$")
_PREFIX_LOOSE_RE = re.compile(r"^(?:SCR[A-Za-z0-9-]*|AUD)$", re.IGNORECASE)

ALLOWED_TOKENS = frozenset({"screen", "content", "version", "date", "show_token", "initials"})
DEFAULT_TOKENS = ["screen", "content", "version", "date"]
ROUTING_TOKEN = "screen"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ParsedFilename:
    """Structured fields extracted from a fully valid delivery filename."""
    screen_prefix: str
    slug: str
    version: int
    date: date
    extension: str
    is_loop: bool
    original_name: str
    show_token: str | None = None
    artist_initials: str | None = None


@dataclass
class FullMatch:
    """Filename matched the full convention; all fields valid."""
    parsed: ParsedFilename


@dataclass
class PartialMatch:
    """Filename has a recognizable screen token but other fields are malformed."""
    screen_prefix: str
    original: str
    problems: list[str]


@dataclass
class NoMatch:
    """Filename has no recognizable screen token."""
    original: str
    problems: list[str]


ParseResult = FullMatch | PartialMatch | NoMatch


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_valid_prefix(token: str) -> bool:
    """Return True if token is a recognised strict Pixera screen prefix."""
    return bool(_PREFIX_STRICT_RE.match(token))


def is_valid_screen_prefix(token: str, config: ShowConfig | None = None) -> bool:
    """Return True if token is a valid routing screen id for this show."""
    if _PREFIX_STRICT_RE.match(token):
        return True
    if config is not None:
        if any(screen.id == token for screen in config.screens):
            return True
    return False


def extract_screen_prefix(filename: str, config: ShowConfig | None = None) -> str | None:
    """Return the screen routing token from filename, or None if not recognised."""
    stem = Path(filename).stem
    parts = stem.split("_")
    for part in parts:
        if is_valid_screen_prefix(part, config):
            return part
    if config is None or not config.filename_convention.enabled:
        token = parts[0] if parts else ""
        return token if _PREFIX_STRICT_RE.match(token) else None
    return None


def parse_filename(filename: str, config: ShowConfig | None = None) -> ParseResult:
    """Parse a media filename against the show's delivery convention."""
    if config is not None and config.filename_convention.enabled:
        return _parse_configurable(filename, config)
    return _parse_legacy(filename)


def build_filename_pattern(config: ShowConfig) -> str:
    """Return a human-readable token pattern for spec documents (brace-delimited tokens)."""
    convention = config.filename_convention
    tokens = convention.tokens if convention.enabled else list(DEFAULT_TOKENS)
    return "_".join(f"{{{token}}}" for token in tokens) + ".ext"


def example_value_for_token(token: str, config: ShowConfig) -> str:
    """Return the example column value for one filename convention token."""
    convention = config.filename_convention
    if token == "show_token":
        return config.delivery.show_token or "ShowToken"
    if token == "initials":
        return "ABC"
    if token == "screen":
        return config.screens[0].id if config.screens else "SCR01"
    if token == "content":
        return "OpeningVideo-LOOP" if convention.allow_loop_suffix else "OpeningVideo"
    if token == "version":
        return f"{convention.version_prefix or 'v'}01"
    if token == "date":
        return "20260425"
    return token


def build_example_filename(config: ShowConfig) -> str:
    """Return a human-readable example filename for the configured convention."""
    convention = config.filename_convention
    if not convention.enabled:
        screen_id = config.screens[0].id if config.screens else "SCR01"
        slug = "OpeningVideo-LOOP" if convention.allow_loop_suffix else "OpeningVideo"
        return f"{screen_id}_{slug}_v01_20260425.mov"
    parts: list[str] = []
    for token in convention.tokens:
        if token == "show_token":
            parts.append(config.delivery.show_token or "ShowToken")
        elif token == "initials":
            parts.append("ABC")
        elif token == "screen":
            parts.append(config.screens[0].id if config.screens else "SCR01")
        elif token == "content":
            parts.append("OpeningVideo-LOOP" if convention.allow_loop_suffix else "OpeningVideo")
        elif token == "version":
            parts.append(f"{convention.version_prefix}01")
        elif token == "date":
            parts.append("20260425")
    return "_".join(parts) + ".mov"


# ---------------------------------------------------------------------------
# Configurable convention
# ---------------------------------------------------------------------------

def _screen_pattern(screen_ids: list[str]) -> str:
    patterns = [_SCR_NUM, _SCR_WIDE, _SCR_ALL, _AUD]
    patterns.extend(re.escape(sid) for sid in screen_ids if sid)
    return "(?:" + "|".join(patterns) + ")"


def _build_convention_regex(config: ShowConfig) -> re.Pattern[str] | None:
    convention = config.filename_convention
    screen_ids = [s.id for s in config.screens]
    group_parts: list[str] = []
    for token in convention.tokens:
        if token == "screen":
            group_parts.append(f"(?P<screen>{_screen_pattern(screen_ids)})")
        elif token == "content":
            group_parts.append(f"(?P<content>{_SLUG_PAT})")
        elif token == "version":
            prefix = re.escape(convention.version_prefix)
            group_parts.append(f"(?P<version>{prefix}\\d+)")
        elif token == "date":
            group_parts.append(r"(?P<date>\d{8})")
        elif token == "show_token":
            if not config.delivery.show_token:
                return None
            group_parts.append(f"(?P<show_token>{re.escape(config.delivery.show_token)})")
        elif token == "initials":
            group_parts.append(f"(?P<initials>{_INITIALS_PAT})")
        else:
            return None
    if not group_parts:
        return None
    return re.compile("^" + "_".join(group_parts) + "$")


def _parse_configurable(filename: str, config: ShowConfig) -> ParseResult:
    p = Path(filename)
    stem = p.stem
    ext = p.suffix
    convention = config.filename_convention

    compiled = _build_convention_regex(config)
    if compiled is not None:
        match = compiled.match(stem)
        if match:
            return _full_match_from_groups(match.groupdict(), ext, filename, convention)

    parts = stem.split("_")
    found, used_indices = _collect_flexible_tokens(parts, config)
    screen_val = found.get("screen")
    requires_screen = ROUTING_TOKEN in convention.tokens

    if requires_screen and not screen_val:
        for part in parts:
            if _PREFIX_LOOSE_RE.match(part):
                loose_problems = [f"'{part}' is not a valid screen token — "] + _diagnose_prefix(part)
                loose_problems += _problems_for_token_values(found, parts, used_indices, config)
                return PartialMatch(screen_prefix=part, original=filename, problems=loose_problems)
        return NoMatch(original=filename, problems=["No recognisable screen token in filename"])

    problems = _problems_for_token_values(found, parts, used_indices, config)
    if requires_screen and screen_val and not is_valid_screen_prefix(screen_val, config):
        problems = (
            [f"'{screen_val}' is not a valid screen token for this show"]
            + _diagnose_prefix(screen_val)
            + problems
        )
        return PartialMatch(screen_prefix=screen_val, original=filename, problems=problems)

    if not problems:
        return _full_match_from_flexible(found, ext, filename, convention)

    prefix = screen_val or ""
    return PartialMatch(screen_prefix=prefix, original=filename, problems=problems)


def _collect_flexible_tokens(
    parts: list[str],
    config: ShowConfig,
) -> tuple[dict[str, str], set[int]]:
    """Identify convention token values anywhere in underscore-separated stem parts."""
    convention = config.filename_convention
    used: set[int] = set()
    found: dict[str, str] = {}

    if ROUTING_TOKEN in convention.tokens:
        for index, part in enumerate(parts):
            if is_valid_screen_prefix(part, config):
                found["screen"] = part
                used.add(index)
                break

    for index, part in enumerate(parts):
        if index in used:
            continue
        date_token = part.split(".")[0]
        if re.match(r"^\d{8}$", date_token) and _parse_date(date_token):
            found["date"] = date_token
            used.add(index)
            break

    prefix = convention.version_prefix
    for index, part in enumerate(parts):
        if index in used:
            continue
        if re.match(rf"^{re.escape(prefix)}\d+$", part):
            found["version"] = part
            used.add(index)
            break

    if config.delivery.show_token:
        for index, part in enumerate(parts):
            if index in used:
                continue
            if part == config.delivery.show_token:
                found["show_token"] = part
                used.add(index)
                break

    if "initials" in convention.tokens:
        for index, part in enumerate(parts):
            if index in used:
                continue
            if re.match(rf"^{_INITIALS_PAT}$", part):
                found["initials"] = part
                used.add(index)
                break

    if "content" in convention.tokens:
        remaining = [index for index in range(len(parts)) if index not in used]
        if remaining:
            content_index = remaining[0]
            found["content"] = parts[content_index]
            used.add(content_index)

    return found, used


def _problems_for_token_values(
    found: dict[str, str],
    parts: list[str],
    used: set[int],
    config: ShowConfig,
) -> list[str]:
    """Validate flexibly located token values against the configured convention."""
    problems: list[str] = []
    for token in config.filename_convention.tokens:
        value = found.get(token)
        if not value:
            problems.append(_missing_token_message(token, config))
        else:
            problems.extend(_validate_token_field(token, value, config))

    for index in range(len(parts)):
        if index not in used:
            problems.append(
                f"Unexpected extra field '{parts[index]}' "
                f"(not assigned to any configured token)"
            )
    return problems


def _full_match_from_flexible(
    found: dict[str, str],
    ext: str,
    filename: str,
    convention,
) -> ParseResult:
    return _full_match_from_groups(found, ext, filename, convention)


def _full_match_from_groups(
    groups: dict[str, str],
    ext: str,
    filename: str,
    convention,
) -> ParseResult | FullMatch:
    tokens = convention.tokens
    screen = groups.get("screen", "")
    show_token = groups.get("show_token") if "show_token" in tokens else None
    initials = groups.get("initials") if "initials" in tokens else None

    if "content" in tokens:
        slug = groups.get("content", "")
        if not re.match(rf"^{_SLUG_PAT}$", slug):
            return PartialMatch(
                screen_prefix=screen,
                original=filename,
                problems=[f"Content '{slug}' contains invalid characters"],
            )
        is_loop = slug.endswith("-LOOP")
    else:
        slug = ""
        is_loop = False

    if "version" in tokens:
        version_str = groups.get("version", "")
        prefix = convention.version_prefix
        if not version_str.startswith(prefix):
            return PartialMatch(
                screen_prefix=screen,
                original=filename,
                problems=[f"Version '{version_str}' must start with '{prefix}'"],
            )
        version_num = int(version_str[len(prefix):])
    else:
        version_num = 0

    if "date" in tokens:
        date_str = groups.get("date", "")
        parsed_date = _parse_date(date_str)
        if parsed_date is None:
            return PartialMatch(
                screen_prefix=screen,
                original=filename,
                problems=[f"Date '{date_str}' is not a valid calendar date"],
            )
    else:
        parsed_date = date(2000, 1, 1)

    if initials and not re.match(rf"^{_INITIALS_PAT}$", initials):
        return PartialMatch(
            screen_prefix=screen,
            original=filename,
            problems=[f"Artist initials '{initials}' must be 2–3 letters"],
        )

    return FullMatch(
        parsed=ParsedFilename(
            screen_prefix=screen,
            slug=slug,
            version=version_num,
            date=parsed_date,
            extension=ext,
            is_loop=is_loop,
            original_name=filename,
            show_token=show_token,
            artist_initials=initials,
        )
    )


def _token_field_label(token: str) -> str:
    labels = {
        "show_token": "show token",
        "initials": "artist initials",
        "screen": "screen",
        "content": "content",
        "version": "version",
        "date": "date",
    }
    return labels.get(token, token)


def _missing_token_message(token: str, config: ShowConfig) -> str:
    convention = config.filename_convention
    hints = {
        "show_token": f"show token (e.g. {config.delivery.show_token or 'ShowToken'})",
        "initials": "artist initials (2–3 letters, e.g. ABC)",
        "screen": "screen ID (e.g. SCR01)",
        "content": "content slug (e.g. OpeningVideo)",
        "version": f"version (e.g. {convention.version_prefix}01)",
        "date": "date (YYYYMMDD, e.g. 20260425)",
    }
    return f"Missing {_token_field_label(token)} field - expected {hints.get(token, token)}"


def _validate_token_field(token: str, value: str, config: ShowConfig) -> list[str]:
    """Return problems for a single token value at its expected position."""
    problems: list[str] = []
    convention = config.filename_convention

    if token == "show_token":
        if not value:
            problems.append(_missing_token_message(token, config))
        elif config.delivery.show_token and value != config.delivery.show_token:
            problems.append(
                f"Show token '{value}' does not match config ('{config.delivery.show_token}')"
            )
    elif token == "initials":
        if not value:
            problems.append(_missing_token_message(token, config))
        elif not re.match(rf"^{_INITIALS_PAT}$", value):
            problems.append(
                f"Artist initials '{value}' must be 2-3 letters (A-Z) - "
                f"got '{value}' in the {_token_field_label(token)} position"
            )
    elif token == "screen":
        if not value:
            problems.append(_missing_token_message(token, config))
        elif not is_valid_screen_prefix(value, config):
            problems.append(f"'{value}' is not a valid screen token for this show")
    elif token == "content":
        if not value:
            problems.append(_missing_token_message(token, config))
        elif not re.match(rf"^{_SLUG_PAT}$", value):
            problems.append(
                f"Content '{value}' - only letters, digits, and dashes allowed"
            )
    elif token == "version":
        prefix = convention.version_prefix
        if not value:
            problems.append(_missing_token_message(token, config))
        elif not re.match(rf"^{re.escape(prefix)}\d+$", value):
            problems.append(f"Version '{value}' must be {prefix} followed by digits")
    elif token == "date":
        date_token = value.split(".")[0] if value else ""
        if not date_token:
            problems.append(_missing_token_message(token, config))
        elif not re.match(r"^\d{8}$", date_token):
            problems.append(f"Date '{date_token}' must be 8 digits (YYYYMMDD)")
        elif _parse_date(date_token) is None:
            problems.append(f"Date '{date_token}' is not a valid calendar date")

    return problems


# ---------------------------------------------------------------------------
# Legacy Pixera parser (default when convention disabled)
# ---------------------------------------------------------------------------

def _parse_legacy(filename: str) -> ParseResult:
    p = Path(filename)
    stem = p.stem
    ext = p.suffix

    m = _FULL_RE.match(stem)
    if m:
        prefix, slug, version_str, date_str = m.groups()
        parsed_date = _parse_date(date_str)
        if parsed_date is None:
            return PartialMatch(
                screen_prefix=prefix,
                original=filename,
                problems=[f"Date '{date_str}' is not a valid calendar date"],
            )
        return FullMatch(
            parsed=ParsedFilename(
                screen_prefix=prefix,
                slug=slug,
                version=int(version_str[1:]),
                date=parsed_date,
                extension=ext,
                is_loop=slug.endswith("-LOOP"),
                original_name=filename,
            )
        )

    parts = stem.split("_")
    token = parts[0]

    if _PREFIX_STRICT_RE.match(token):
        problems = _diagnose_legacy(parts, token)
        return PartialMatch(screen_prefix=token, original=filename, problems=problems)

    if _PREFIX_LOOSE_RE.match(token):
        problems = [f"'{token}' is not a valid prefix — "] + _diagnose_prefix(token)
        problems += _diagnose_legacy(parts, token)
        return PartialMatch(screen_prefix=token, original=filename, problems=problems)

    return NoMatch(original=filename, problems=["No recognisable screen prefix"])


def _parse_date(date_str: str) -> date | None:
    try:
        return date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    except ValueError:
        return None


def _diagnose_prefix(token: str) -> list[str]:
    problems: list[str] = []
    if token.upper() == "AUD":
        return []
    if re.match(r"^SCR\d+$", token):
        digits = token[3:]
        if len(digits) != 2:
            problems.append(
                f"Screen number must be exactly 2 digits, zero-padded (e.g. SCR01 not SCR{digits})"
            )
    elif re.match(r"^SCRwide", token, re.IGNORECASE):
        if not re.match(r"^SCRwide(?:-\d{2})+$", token):
            problems.append(
                "SCRwide prefix must list screens as 2-digit pairs: SCRwide-01-02"
            )
    elif re.match(r"^SCR", token):
        problems.append(
            f"Unrecognised SCR prefix format: '{token}'. "
            "Expected SCR## (e.g. SCR01), SCRwide-##-##, or SCRall."
        )
    return problems


def _diagnose_legacy(parts: list[str], prefix: str) -> list[str]:
    problems: list[str] = []
    if len(parts) < 2 or not parts[1]:
        problems.append("Missing content slug (expected SCR##_<Slug>_v##_YYYYMMDD)")
        return problems

    slug = parts[1]
    if not re.match(rf"^{_SLUG_PAT}$", slug):
        problems.append(
            f"Slug '{slug}' contains invalid characters — only letters, digits, and dashes allowed"
        )

    if len(parts) < 3 or not parts[2]:
        problems.append("Missing version field (expected v##, e.g. v01)")
        return problems

    version = parts[2]
    if not re.match(rf"^{_VERSION_PAT}$", version):
        problems.append(
            f"Version '{version}' is invalid — must start with lowercase 'v' followed by digits (e.g. v01)"
        )

    if len(parts) < 4 or not parts[3]:
        problems.append("Missing date field (expected YYYYMMDD, e.g. 20260425)")
        return problems

    date_token = parts[3].split(".")[0]
    if not re.match(r"^\d{8}$", date_token):
        problems.append(
            f"Date field '{date_token}' is invalid — must be 8 digits in YYYYMMDD format"
        )
    elif _parse_date(date_token) is None:
        problems.append(f"Date '{date_token}' is not a valid calendar date")

    return problems
