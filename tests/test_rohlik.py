"""Tests for quantity parsing, product matching and order resolution."""

import asyncio
from datetime import date
from pathlib import Path

from cookidoo_rohlik.matching import ProductMatcher, score
from cookidoo_rohlik.models import OrderItem, OrderKind, PlannedOrder
from cookidoo_rohlik.orchestrator import resolve_order
from cookidoo_rohlik.quantity import Quantity, packages_needed, parse_quantity, total_needed
from cookidoo_rohlik.rohlik_client import Product


class TestQuantity:
    def test_parse_basic(self) -> None:
        assert parse_quantity("500 g") == Quantity(500, "g")
        assert parse_quantity("1,5 kg") == Quantity(1500, "g")
        assert parse_quantity("250 ml") == Quantity(250, "ml")
        assert parse_quantity("2 l") == Quantity(2000, "ml")
        assert parse_quantity("3 ks") == Quantity(3, "ks")
        assert parse_quantity("2") == Quantity(2, "ks")  # bare number -> pieces

    def test_parse_unparseable(self) -> None:
        assert parse_quantity("1 lžíce") is None
        assert parse_quantity("špetka") is None
        assert parse_quantity("") is None

    def test_total_needed_sums_same_unit(self) -> None:
        assert total_needed(["500 g", "1 kg"]) == Quantity(1500, "g")

    def test_total_needed_mixed_units(self) -> None:
        assert total_needed(["500 g", "2 ks"]) is None

    def test_packages_needed(self) -> None:
        assert packages_needed(Quantity(800, "g"), "500 g") == 2
        assert packages_needed(Quantity(500, "g"), "500 g") == 1
        assert packages_needed(Quantity(4, "ks"), "10 ks") == 1
        assert packages_needed(None, "500 g") == 1          # unparseable need
        assert packages_needed(Quantity(500, "g"), "1 l") == 1  # unit mismatch


class TestScore:
    def test_exact_and_partial(self) -> None:
        assert score("kuřecí stehna", "Kuřecí stehna chlazená") == 1.0
        assert score("losos filet", "Losos atlantský filet s kůží") == 1.0
        assert 0 < score("rajčata cherry", "Rajčata keříková") < 1.0

    def test_stopwords_ignored(self) -> None:
        assert score("bazalka čerstvá", "Bazalka květináč") == 1.0


class FakeRohlik:
    """Offline stand-in for RohlikClient search."""

    def __init__(self) -> None:
        self.catalog = {
            "kuřecí stehna": [
                Product(1, "Kuřecí stehna chlazená", "Vodňanské", 89.9, "CZK", "600 g"),
                Product(2, "Kuřecí stehenní řízky", "Vodňanské", 119.9, "CZK", "500 g"),
            ],
            "smetana ke šlehání": [
                Product(3, "Smetana ke šlehání 31%", "Tatra", 49.9, "CZK", "250 ml"),
            ],
            "kapary": [],
        }
        self.cart: list[tuple[int, int]] = []

    async def search_products(self, query: str, limit: int = 10) -> list[Product]:
        return self.catalog.get(query, [])

    async def add_to_cart(self, product_id: int, quantity: int) -> None:
        self.cart.append((product_id, quantity))


def make_order(items: list[OrderItem]) -> PlannedOrder:
    return PlannedOrder(
        kind=OrderKind.FRESH,
        delivery_date=date(2026, 6, 15),
        covers_days=[date(2026, 6, 15)],
        items=items,
    )


class TestMatcherAndOrchestrator:
    def test_match_search_then_cache(self, tmp_path: Path) -> None:
        matcher = ProductMatcher(cache_path=tmp_path / "map.yaml")
        fake = FakeRohlik()
        item = OrderItem(name="kuřecí stehna", quantities=["1,2 kg"])

        first = asyncio.run(matcher.match(item, fake))
        assert first.matched and first.product.id == 1
        assert first.packages == 2  # 1200 g / 600 g
        assert not first.from_cache

        matcher.save_cache()
        matcher2 = ProductMatcher(cache_path=tmp_path / "map.yaml")
        second = asyncio.run(matcher2.match(item, fake))
        assert second.from_cache and second.product.id == 1

    def test_resolve_order_reports_unmatched_and_fills_cart(self, tmp_path: Path) -> None:
        matcher = ProductMatcher(cache_path=tmp_path / "map.yaml")
        fake = FakeRohlik()
        order = make_order([
            OrderItem(name="kuřecí stehna", quantities=["600 g"]),
            OrderItem(name="smetana ke šlehání", quantities=["250 ml"]),
            OrderItem(name="kapary", quantities=["1 lžíce"]),
        ])

        res = asyncio.run(resolve_order(order, matcher, fake, execute=True))

        assert {m.product.id for m in res.matched} == {1, 3}
        assert [m.item.name for m in res.unmatched] == ["kapary"]
        assert sorted(fake.cart) == [(1, 1), (3, 1)]
        assert res.executed
        assert res.estimated_price == 89.9 + 49.9

    def test_legacy_json_cache_migrated(self, tmp_path: Path) -> None:
        import json

        legacy = tmp_path / "map.json"
        legacy.write_text(json.dumps({
            "kureci stehna": {
                "product_id": 1, "product_name": "Kuřecí stehna chlazená",
                "brand": "", "price": 89.9, "currency": "CZK",
                "textual_amount": "600 g",
            }
        }), encoding="utf-8")
        matcher = ProductMatcher(cache_path=tmp_path / "map.yaml")
        item = OrderItem(name="kuřecí stehna", quantities=["600 g"])
        res = asyncio.run(matcher.match(item, FakeRohlik()))
        assert res.from_cache and res.product.id == 1
        matcher.save_cache()
        text = (tmp_path / "map.yaml").read_text(encoding="utf-8")
        assert "product_id: 1" in text and text.startswith("# Mapování")

    def test_class_override_in_map_file(self, tmp_path: Path) -> None:
        from cookidoo_rohlik.classify import Classifier, load_map_overrides
        from cookidoo_rohlik.models import ItemClass

        map_file = tmp_path / "map.yaml"
        map_file.write_text(
            "rajčatový protlak:\n  class: durable\n"
            "kapary:\n  class: pantry\n"
            "kuřecí stehna:\n  product_id: 1\n  textual_amount: 600 g\n",
            encoding="utf-8",
        )
        c = Classifier()
        c.overrides.update(load_map_overrides(map_file))
        assert c.classify("Rajčatový protlak") is ItemClass.DURABLE
        assert c.classify("kapary") is ItemClass.PANTRY
        assert c.classify("kuřecí stehna") is ItemClass.FRESH  # no class field

    def test_class_only_entry_still_searches_product(self, tmp_path: Path) -> None:
        map_file = tmp_path / "map.yaml"
        map_file.write_text("kuřecí stehna:\n  class: fresh\n", encoding="utf-8")
        matcher = ProductMatcher(cache_path=map_file)
        res = asyncio.run(
            matcher.match(OrderItem(name="kuřecí stehna", quantities=["600 g"]), FakeRohlik())
        )
        assert res.matched and not res.from_cache  # searched despite entry
        matcher.save_cache()
        text = map_file.read_text(encoding="utf-8")
        assert "class: fresh" in text and "product_id: 1" in text  # both preserved
