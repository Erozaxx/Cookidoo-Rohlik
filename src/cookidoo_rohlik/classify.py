"""Classify ingredients as fresh / durable / pantry.

Keyword based, fully overridable from config. Matching is done on a
normalized (lowercased, diacritics-stripped) ingredient name using
substring search, so "kuřecí prsa" matches keyword "kurec".
Precedence: explicit overrides > pantry > fresh > durable (default).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models import ItemClass

# Defaults are a starting point for Czech households; tune in config.yaml.
DEFAULT_FRESH_KEYWORDS: tuple[str, ...] = (
    # meat & fish
    "maso", "kurec", "kureci", "hovezi", "veprov", "mlete", "krut",
    "slanina", "sunka", "klobas", "ryba", "losos", "treska", "krevet",
    # dairy & eggs
    "mleko", "smetana", "jogurt", "tvaroh", "syr", "mozzarella",
    "parmazan", "mascarpone", "ricotta", "vejce", "maslo",
    # bakery
    "peciv", "rohlik", "bageta", "chleb", "toust",
    # fresh produce & herbs
    "salat", "rajc", "okurk", "paprik", "cuket", "lilek", "brokolice",
    "kvetak", "spenat", "zampion", "houb", "porek", "celer", "mrkev",
    "petrzel", "pazitka", "koriandr", "bazalka", "kopr", "mata",
    "tymian", "rozmaryn", "avokad", "citron", "limet", "jablk",
    "banan", "hrozn", "jahod", "malin", "boruvk",
)

DEFAULT_PANTRY_KEYWORDS: tuple[str, ...] = (
    "sul", "pepr", "voda", "olej", "ocet", "cukr", "mouka",
    "prasek do peciva", "kypric", "vanilkov", "skorice", "kmin",
    "papriku mletou", "kari", "kurkuma", "oregano", "sojova omacka",
)


def normalize(text: str) -> str:
    """Lowercase and strip diacritics for robust keyword matching."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


@dataclass
class Classifier:
    """Keyword classifier with per-ingredient overrides."""

    fresh_keywords: tuple[str, ...] = DEFAULT_FRESH_KEYWORDS
    pantry_keywords: tuple[str, ...] = DEFAULT_PANTRY_KEYWORDS
    # exact normalized ingredient name -> class
    overrides: dict[str, ItemClass] = field(default_factory=dict)

    def classify(self, ingredient_name: str) -> ItemClass:
        name = normalize(ingredient_name)
        if name in self.overrides:
            return self.overrides[name]
        if any(kw in name for kw in self.pantry_keywords):
            return ItemClass.PANTRY
        if any(kw in name for kw in self.fresh_keywords):
            return ItemClass.FRESH
        return ItemClass.DURABLE

    @classmethod
    def from_config(cls, cfg: dict) -> "Classifier":
        """Build a classifier from the `classification` config section."""
        section = cfg.get("classification", {}) or {}
        fresh = tuple(normalize(k) for k in section.get("fresh_keywords", DEFAULT_FRESH_KEYWORDS))
        pantry = tuple(normalize(k) for k in section.get("pantry_keywords", DEFAULT_PANTRY_KEYWORDS))
        overrides = {
            normalize(name): ItemClass(value)
            for name, value in (section.get("overrides", {}) or {}).items()
        }
        return cls(fresh_keywords=fresh, pantry_keywords=pantry, overrides=overrides)


def load_map_overrides(map_path: Path) -> dict[str, ItemClass]:
    """Extract `class:` overrides from the product_map.yaml file.

    Entries there may carry an optional `class: fresh|durable|pantry`
    so users curate product mapping AND classification in one place.
    Invalid values are skipped with a warning-by-omission (validated
    by ItemClass).
    """
    if not map_path.exists():
        return {}
    raw = yaml.safe_load(map_path.read_text(encoding="utf-8")) or {}
    overrides: dict[str, ItemClass] = {}
    for name, entry in raw.items():
        if isinstance(entry, dict) and "class" in entry:
            try:
                overrides[normalize(name)] = ItemClass(entry["class"])
            except ValueError:
                pass
    return overrides
