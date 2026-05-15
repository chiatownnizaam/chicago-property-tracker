"""
Normalization helpers shared by every ingest path.

Goal: make sure the same physical property always maps to the same row,
regardless of which source it came from or how the address was written.
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Optional

# Standard postal abbreviations — applied AFTER uppercase
_STREET_SUFFIXES = {
    "STREET": "ST", "AVENUE": "AVE", "BOULEVARD": "BLVD", "DRIVE": "DR",
    "ROAD": "RD", "LANE": "LN", "PLACE": "PL", "TERRACE": "TER",
    "COURT": "CT", "CIRCLE": "CIR", "PARKWAY": "PKWY", "HIGHWAY": "HWY",
    "SQUARE": "SQ", "TRAIL": "TRL",
}

_DIRECTIONS = {
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
    "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW",
}


def normalize_address(addr: Optional[str]) -> str:
    """
    Returns a canonical uppercase, whitespace-collapsed, suffix-abbreviated
    version of the address. Used as the dedup key.
    """
    if not addr:
        return ""
    s = addr.upper().strip()
    s = re.sub(r"\s+", " ", s)         # collapse internal whitespace
    s = re.sub(r"[.,]", "", s)         # drop periods and commas
    tokens = s.split(" ")
    out = []
    for t in tokens:
        if t in _STREET_SUFFIXES:
            out.append(_STREET_SUFFIXES[t])
        elif t in _DIRECTIONS:
            out.append(_DIRECTIONS[t])
        else:
            out.append(t)
    return " ".join(out)


def normalize_city(city: Optional[str]) -> str:
    """Title-cased canonical city name. Empty string if missing."""
    if not city:
        return ""
    return city.strip().title()


def normalize_pin(pin: Optional[str]) -> Optional[str]:
    """
    Cook County PINs are 14 digits formatted as 10-12-345-678-9000 or all-digits.
    Strip everything non-numeric so dedup works across formats.
    Returns None for empty/invalid input.
    """
    if not pin:
        return None
    digits = re.sub(r"\D", "", str(pin))
    return digits or None


def to_decimal(val, places: int = 2) -> Optional[Decimal]:
    """
    Convert a possibly-string, possibly-None numeric value to a Decimal.
    Default `places=2` is money precision; pass higher values for coords
    (e.g. `places=7` for lat/lon).
    """
    if val is None or val == "":
        return None
    try:
        if isinstance(val, str):
            val = re.sub(r"[$,\s]", "", val)
        quant = Decimal("1").scaleb(-places)
        return Decimal(str(val)).quantize(quant)
    except (InvalidOperation, ValueError, TypeError):
        return None


def to_coord(val) -> Optional[Decimal]:
    """Lat/lon convenience — 7 decimal places ≈ 11mm precision."""
    return to_decimal(val, places=7)


def escape_soql_string(value: str) -> str:
    """Escape single quotes for inclusion in a Socrata SoQL WHERE clause."""
    return value.replace("'", "''")


def safe_soql_in_list(values) -> str:
    """
    Build the value list for a SoQL `IN()` clause, quoting and escaping each.
    Returns the parenthesized string ready to substitute.
    """
    quoted = [f"'{escape_soql_string(str(v))}'" for v in values if v is not None and v != ""]
    return f"({', '.join(quoted)})" if quoted else "('')"
