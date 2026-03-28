"""Bidirectional mapping between Crouton quantity types and human-readable forms."""

from __future__ import annotations

from fractions import Fraction

# Crouton internal type → (abbreviation, full name)
_QUANTITY_MAP: dict[str, tuple[str, str]] = {
    "BOTTLE": ("bottle", "bottle"),
    "BUNCH": ("bunch", "bunch"),
    "CAN": ("can", "can"),
    "CENTILITER": ("cl", "centiliter"),
    "CUP": ("cup", "cup"),
    "GRAMS": ("g", "gram"),
    "ITEM": ("", "item"),  # no unit displayed for items
    "KGS": ("kg", "kilogram"),
    "LITRES": ("L", "litre"),
    "MILLS": ("ml", "millilitre"),
    "OUNCE": ("oz", "ounce"),
    "PACKET": ("packet", "packet"),
    "PINCH": ("pinch", "pinch"),
    "POUND": ("lb", "pound"),
    "SECTION": ("section", "section"),
    "TABLESPOON": ("tbsp", "tablespoon"),
    "TEASPOON": ("tsp", "teaspoon"),
}

# Reverse lookup: abbreviation/full name → Crouton type
_REVERSE_MAP: dict[str, str] = {}
for _crouton_type, (_abbr, _full) in _QUANTITY_MAP.items():
    if _abbr:
        _REVERSE_MAP[_abbr] = _crouton_type
        _REVERSE_MAP[_abbr.lower()] = _crouton_type
    _REVERSE_MAP[_full] = _crouton_type
    _REVERSE_MAP[_full.lower()] = _crouton_type
    _REVERSE_MAP[_full + "s"] = _crouton_type  # plural
    _REVERSE_MAP[_crouton_type.lower()] = _crouton_type

# Additional common aliases
_REVERSE_MAP.update(
    {
        "cups": "CUP",
        "tablespoons": "TABLESPOON",
        "teaspoons": "TEASPOON",
        "ounces": "OUNCE",
        "pounds": "POUND",
        "grams": "GRAMS",
        "kilograms": "KGS",
        "litres": "LITRES",
        "liters": "LITRES",
        "liter": "LITRES",
        "litre": "LITRES",
        "millilitres": "MILLS",
        "milliliters": "MILLS",
        "milliliter": "MILLS",
        "millilitre": "MILLS",
        "centiliters": "CENTILITER",
        "centilitres": "CENTILITER",
        "bottles": "BOTTLE",
        "bunches": "BUNCH",
        "cans": "CAN",
        "packets": "PACKET",
        "pinches": "PINCH",
        "sections": "SECTION",
        "items": "ITEM",
        "lbs": "POUND",
    }
)


def to_display(quantity_type: str) -> str:
    """Convert a Crouton quantity type to its display abbreviation."""
    entry = _QUANTITY_MAP.get(quantity_type)
    if entry is None:
        return quantity_type.lower()
    return entry[0]


def to_crouton_type(display: str) -> str | None:
    """Convert a display abbreviation or full name to a Crouton quantity type."""
    return _REVERSE_MAP.get(display.lower().strip())


# Common fractions for display
_FRACTION_MAP = {
    0.25: "¼",
    0.333: "⅓",
    0.3333333333333333: "⅓",
    0.5: "½",
    0.667: "⅔",
    0.6666666666666666: "⅔",
    0.75: "¾",
    0.125: "⅛",
    0.375: "⅜",
    0.625: "⅝",
    0.875: "⅞",
}

# Reverse: unicode fraction → decimal
_UNICODE_FRACTION_MAP = {
    "¼": 0.25,
    "⅓": 1 / 3,
    "½": 0.5,
    "⅔": 2 / 3,
    "¾": 0.75,
    "⅛": 0.125,
    "⅜": 0.375,
    "⅝": 0.625,
    "⅞": 0.875,
}


def format_amount(amount: float | None) -> str:
    """Format a numeric amount for display, using fractions where appropriate."""
    if amount is None or amount == 0:
        return ""

    whole = int(amount)
    frac = amount - whole

    # Check for known fractions
    frac_str = ""
    if frac > 0.01:
        # Try exact match first, then with rounding tolerance
        frac_str = _FRACTION_MAP.get(round(frac, 4), "")
        if not frac_str:
            for key, symbol in _FRACTION_MAP.items():
                if abs(frac - key) < 0.001:
                    frac_str = symbol
                    break
        if not frac_str:
            # Try Fraction for arbitrary values
            f = Fraction(frac).limit_denominator(16)
            if f.numerator > 0:
                frac_str = f"{f.numerator}/{f.denominator}"

    if whole > 0 and frac_str:
        return f"{whole} {frac_str}"
    elif whole > 0:
        return str(whole)
    elif frac_str:
        return frac_str
    else:
        # Fall back to clean decimal
        if amount == int(amount):
            return str(int(amount))
        return f"{amount:g}"


def parse_amount(text: str) -> float | None:
    """Parse a human-readable amount string back to a float."""
    text = text.strip()
    if not text:
        return None

    total = 0.0
    parts = text.split()
    for part in parts:
        # Check unicode fractions
        if part in _UNICODE_FRACTION_MAP:
            total += _UNICODE_FRACTION_MAP[part]
        elif "/" in part:
            try:
                num, den = part.split("/", 1)
                total += float(num) / float(den)
            except (ValueError, ZeroDivisionError):
                return None
        else:
            try:
                total += float(part)
            except ValueError:
                return None

    return total if total > 0 else None
