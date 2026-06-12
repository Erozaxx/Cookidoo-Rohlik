"""Match Cookidoo ingredient names to Rohlik products.

Strategy:
1. Persistent cache first (learned/curated mapping, YAML file).
2. Otherwise search Rohlik and score candidates by token overlap of
   normalized names; ties broken by price (cheaper wins).
3. Below `min_score` the item is reported as UNMATCHED for manual review
   (and shows up in the notification instead of silently guessing).

The cache file doubles as a curation point: it is human-friendly YAML
keyed by the original ingredient name (lookup is case/diacritics
insensitive); users edit it to pin an exact product id. A legacy
`.json` cache next to the YAML path is migrated automatically.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import yaml

from .classify import normalize
from .models import OrderItem
from .quantity import packages_needed, total_needed
from .rohlik_client import Product

logger = logging.getLogger(__name__)

# Czech stopwords that carry no product meaning
_STOPWORDS = {"cerstvy", "cerstva", "cerstve", "mleta", "mlety", "cely", "cela"}


def _tokens(name: str) -> set[str]:
    return {t for t in normalize(name).split() if len(t) > 2 and t not in _STOPWORDS}


def score(ingredient_name: str, product_name: str) -> float:
    """Fraction of ingredient tokens found in the product name (prefix match)."""
    ing = _tokens(ingredient_name)
    if not ing:
        return 0.0
    prod = _tokens(product_name)
    hits = sum(
        1 for t in ing if any(p.startswith(t) or t.startswith(p) for p in prod)
    )
    return hits / len(ing)


@dataclass(frozen=True)
class MatchResult:
    item: OrderItem
    product: Product | None
    packages: int
    score: float
    from_cache: bool

    @property
    def matched(self) -> bool:
        return self.product is not None


class SearchClient(Protocol):
    """Anything that can search products (RohlikClient or a fake in tests)."""

    async def search_products(self, query: str, limit: int = 10) -> list[Product]: ...


_CACHE_HEADER = """\
# Mapování ingredience Cookidoo -> produkt Rohlík (kurátorovatelné).
# Klíč je název ingredience (na velikosti písmen a diakritice nezáleží).
# Povinné je jen product_id; product_name a textual_amount (velikost
# balení, např. "500 g") doporučujeme vyplnit — z textual_amount se
# počítá počet kusů. Smaž řádek/blok a matcher si produkt najde znovu.
"""


class ProductMatcher:
    def __init__(self, cache_path: Path, min_score: float = 0.5) -> None:
        self._cache_path = cache_path
        self._min_score = min_score
        # normalized name -> entry; entry["ingredient"] keeps display name
        self._cache: dict[str, dict] = {}
        raw: dict | None = None
        if cache_path.exists():
            raw = yaml.safe_load(cache_path.read_text(encoding="utf-8"))
        else:
            legacy = cache_path.with_suffix(".json")
            if legacy.exists():  # migrate pre-YAML cache transparently
                import json

                raw = json.loads(legacy.read_text(encoding="utf-8"))
                logger.info("Migrating legacy JSON cache %s", legacy)
        for name, entry in (raw or {}).items():
            entry = dict(entry)
            entry.setdefault("ingredient", name)
            self._cache[normalize(name)] = entry

    def save_cache(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        out = {
            entry.get("ingredient", key): {
                k: v for k, v in entry.items() if k != "ingredient"
            }
            for key, entry in self._cache.items()
        }
        self._cache_path.write_text(
            _CACHE_HEADER
            + yaml.safe_dump(out, allow_unicode=True, sort_keys=True,
                             default_flow_style=False),
            encoding="utf-8",
        )

    async def match(self, item: OrderItem, client: SearchClient) -> MatchResult:
        key = normalize(item.name)
        needed = total_needed(item.quantities)

        cached = self._cache.get(key)
        if cached:
            product = Product(
                id=int(cached["product_id"]),
                name=cached["product_name"],
                brand=cached.get("brand", ""),
                price=float(cached.get("price", 0)),
                currency=cached.get("currency", "CZK"),
                textual_amount=cached.get("textual_amount", ""),
            )
            return MatchResult(
                item=item,
                product=product,
                packages=packages_needed(needed, product.textual_amount),
                score=1.0,
                from_cache=True,
            )

        candidates = await client.search_products(item.name, limit=10)
        best: Product | None = None
        best_score = 0.0
        for product in candidates:
            s = score(item.name, product.name)
            if s > best_score or (
                s == best_score and best is not None and product.price < best.price
            ):
                best, best_score = product, s

        if best is None or best_score < self._min_score:
            logger.warning("No match for %r (best score %.2f)", item.name, best_score)
            return MatchResult(item=item, product=None, packages=0,
                               score=best_score, from_cache=False)

        self._cache[key] = {
            "ingredient": item.name,
            "product_id": best.id,
            "product_name": best.name,
            "brand": best.brand,
            "price": best.price,
            "currency": best.currency,
            "textual_amount": best.textual_amount,
        }
        return MatchResult(
            item=item,
            product=best,
            packages=packages_needed(needed, best.textual_amount),
            score=best_score,
            from_cache=False,
        )
