"""Parse quantity strings from Cookidoo and Rohlik.

Cookidoo: "500 g", "2 ks", "1 kg", "250 ml", "1 lžíce", "1 svazek"
Rohlik textualAmount: "500 g", "1 kg", "10 ks", "1 l"

Only mass (g), volume (ml) and pieces (ks) are converted; anything else
(lžíce, hrst, svazek, špetka, ...) is unparseable and defaults to one
package of the matched product.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

# unit -> (canonical unit, factor to canonical)
_UNITS: dict[str, tuple[str, float]] = {
    "g": ("g", 1), "gram": ("g", 1), "gramu": ("g", 1), "gramy": ("g", 1),
    "dag": ("g", 10), "dkg": ("g", 10),
    "kg": ("g", 1000),
    "ml": ("ml", 1), "l": ("ml", 1000), "litr": ("ml", 1000),
    "ks": ("ks", 1), "kus": ("ks", 1), "kusy": ("ks", 1), "kusu": ("ks", 1),
}

_QTY_RE = re.compile(
    r"(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>[^\W\d_]+)?",
    re.UNICODE,
)


@dataclass(frozen=True)
class Quantity:
    """Normalized quantity: amount in canonical unit (g / ml / ks)."""

    amount: float
    unit: str


def parse_quantity(text: str) -> Quantity | None:
    """Parse a quantity string; None if not convertible."""
    if not text:
        return None
    m = _QTY_RE.search(text.strip().lower())
    if not m:
        return None
    amount = float(m.group("amount").replace(",", "."))
    unit_raw = (m.group("unit") or "ks").strip()
    if unit_raw not in _UNITS:
        return None
    unit, factor = _UNITS[unit_raw]
    return Quantity(amount=amount * factor, unit=unit)


def total_needed(quantities: list[str]) -> Quantity | None:
    """Sum a list of quantity strings if they share one canonical unit.

    Returns None when nothing is parseable or units are mixed.
    """
    parsed = [q for q in (parse_quantity(t) for t in quantities) if q]
    if not parsed:
        return None
    units = {q.unit for q in parsed}
    if len(units) != 1:
        return None
    return Quantity(amount=sum(q.amount for q in parsed), unit=parsed[0].unit)


def packages_needed(needed: Quantity | None, package_text: str) -> int:
    """How many packages of `package_text` size cover `needed`.

    Falls back to 1 when either side is unparseable or units differ.
    """
    if needed is None:
        return 1
    package = parse_quantity(package_text)
    if package is None or package.unit != needed.unit or package.amount <= 0:
        return 1
    return max(1, math.ceil(needed.amount / package.amount))
