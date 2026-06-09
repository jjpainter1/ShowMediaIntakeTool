"""Filename convention parsing and validation."""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Regex building blocks
# ---------------------------------------------------------------------------

# Valid strict screen prefixes
_SCR_NUM    = r"SCR\d{2}"                    # SCR01 … SCR99
_SCR_WIDE   = r"SCRwide(?:-\d{2})+"          # SCRwide-01-02-03
_SCR_ALL    = r"SCRall"
_AUD        = r"AUD"

_PREFIX_STRICT_PAT = rf"(?:{_SCR_NUM}|{_SCR_WIDE}|{_SCR_ALL}|{_AUD})"

# Slug: letters/digits/dashes, must start with a letter or digit
_SLUG_PAT    = r"[A-Za-z0-9][A-Za-z0-9-]*"
_VERSION_PAT = r"v\d+"
_DATE_PAT    = r"\d{8}"

# Full match on the stem (filename without extension)
_FULL_RE = re.compile(
    rf"^({_PREFIX_STRICT_PAT})_({_SLUG_PAT})_({_VERSION_PAT})_({_DATE_PAT})$"
)

# Strict prefix alone (for partial-match routing)
_PREFIX_STRICT_RE = re.compile(rf"^({_PREFIX_STRICT_PAT})$")

# "Looks like" a prefix — catches non-zero-padded SCR#, SCRwide without numbers, etc.
# Anything that starts with SCR (any suffix) or is exactly AUD counts as intent.
_PREFIX_LOOSE_RE = re.compile(r"^(?:SCR[A-Za-z0-9-]*|AUD)$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ParsedFilename:
    """All structured fields extracted from a fully valid delivery filename."""
    screen_prefix: str
    slug: str
    version: int
    date: date
    extension: str
    is_loop: bool
    original_name: str


@dataclass
class FullMatch:
    """Filename matched the full convention; all fields valid."""
    parsed: ParsedFilename


@dataclass
class PartialMatch:
    """Filename has a recognizable screen prefix but one or more other fields are malformed."""
    screen_prefix: str   # best-effort prefix, may be malformed
    original: str
    problems: list[str]


@dataclass
class NoMatch:
    """Filename has no recognizable screen prefix."""
    original: str
    problems: list[str]


ParseResult = FullMatch | PartialMatch | NoMatch


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_valid_prefix(token: str) -> bool:
    """Return True if token is a recognised strict screen prefix (SCR##, SCRwide-##, SCRall, AUD)."""
    return bool(_PREFIX_STRICT_RE.match(token))


def extract_screen_prefix(filename: str) -> str | None:
    """Return the strict screen prefix from filename, or None if not recognised.

    Only returns a value when the prefix before the first underscore matches a
    known, properly-formatted pattern (SCR##, SCRwide-##[-##...], SCRall, AUD).
    """
    token = Path(filename).stem.split("_")[0]
    return token if _PREFIX_STRICT_RE.match(token) else None


def parse_filename(filename: str) -> ParseResult:
    """Parse a media filename against the delivery convention.

    Returns one of:
      FullMatch    — all fields valid; parsed data in .parsed
      PartialMatch — prefix recognised but other fields malformed
      NoMatch      — no recognisable prefix
    """
    p = Path(filename)
    stem = p.stem
    ext  = p.suffix  # includes the leading dot, e.g. ".mov"

    # --- Try full match first ---
    m = _FULL_RE.match(stem)
    if m:
        prefix, slug, version_str, date_str = m.groups()
        parsed_date = _parse_date(date_str)
        if parsed_date is None:
            # Prefix and fields look right but date is calendar-invalid → partial
            return PartialMatch(
                screen_prefix=prefix,
                original=filename,
                problems=[f"Date '{date_str}' is not a valid calendar date"],
            )
        return FullMatch(
            parsed=ParsedFilename(
                screen_prefix=prefix,
                slug=slug,
                version=int(version_str[1:]),   # strip leading 'v'
                date=parsed_date,
                extension=ext,
                is_loop=slug.endswith("-LOOP"),
                original_name=filename,
            )
        )

    # --- Full match failed — try to identify why ---
    parts = stem.split("_")
    token = parts[0]

    # Check for a strictly valid prefix
    if _PREFIX_STRICT_RE.match(token):
        problems = _diagnose(parts, token)
        return PartialMatch(screen_prefix=token, original=filename, problems=problems)

    # Check for a loosely recognisable prefix (e.g. SCR1, SCRwide without numbers)
    if _PREFIX_LOOSE_RE.match(token):
        problems = [f"'{token}' is not a valid prefix — "] + _diagnose_prefix(token)
        problems += _diagnose(parts, token)
        return PartialMatch(screen_prefix=token, original=filename, problems=problems)

    return NoMatch(original=filename, problems=["No recognisable screen prefix"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_date(date_str: str) -> date | None:
    """Parse YYYYMMDD string to a date object; return None if invalid."""
    try:
        return date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    except ValueError:
        return None


def _diagnose_prefix(token: str) -> list[str]:
    """Return human-readable problems specific to a malformed prefix token."""
    problems: list[str] = []
    if token.upper() == "AUD":
        return []  # AUD is fine if case is off, but we flag it below
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


def _diagnose(parts: list[str], prefix: str) -> list[str]:
    """Check the non-prefix parts of a split stem and return problem descriptions."""
    problems: list[str] = []
    # parts[0] is the prefix; we expect parts[1]=slug, parts[2]=version, parts[3]=date
    if len(parts) < 2 or not parts[1]:
        problems.append("Missing content slug (expected SCR##_<Slug>_v##_YYYYMMDD)")
        return problems  # can't meaningfully check further

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

    # Date may include the extension if there was no dot-extension; handle both
    date_token = parts[3].split(".")[0]
    if not re.match(r"^\d{8}$", date_token):
        problems.append(
            f"Date field '{date_token}' is invalid — must be 8 digits in YYYYMMDD format"
        )
    elif _parse_date(date_token) is None:
        problems.append(f"Date '{date_token}' is not a valid calendar date")

    return problems
