"""Tests for classification and order planning."""

from datetime import date

from cookidoo_rohlik.classify import Classifier
from cookidoo_rohlik.models import Ingredient, ItemClass, OrderKind
from cookidoo_rohlik.planner import _group_fresh_days, plan_orders


def ing(name: str, day: date, qty: str = "1 ks", recipe: str = "r") -> Ingredient:
    return Ingredient(name=name, quantity=qty, recipe_name=recipe, needed_on=day)


class TestClassifier:
    def test_defaults(self) -> None:
        c = Classifier()
        assert c.classify("Kuřecí stehna") is ItemClass.FRESH
        assert c.classify("těstoviny penne") is ItemClass.DURABLE
        assert c.classify("sůl") is ItemClass.PANTRY

    def test_diacritics_insensitive(self) -> None:
        c = Classifier()
        assert c.classify("SMETANA ke šlehání") is ItemClass.FRESH

    def test_override_wins(self) -> None:
        c = Classifier.from_config(
            {"classification": {"overrides": {"cibule": "durable"}}}
        )
        assert c.classify("Cibule") is ItemClass.DURABLE


class TestGroupFreshDays:
    def test_consecutive_days_grouped_by_two(self) -> None:
        days = [date(2026, 6, 15), date(2026, 6, 16), date(2026, 6, 17)]
        assert _group_fresh_days(days, 2) == [
            [date(2026, 6, 15), date(2026, 6, 16)],
            [date(2026, 6, 17)],
        ]

    def test_gap_breaks_group(self) -> None:
        days = [date(2026, 6, 15), date(2026, 6, 18)]
        assert _group_fresh_days(days, 2) == [
            [date(2026, 6, 15)],
            [date(2026, 6, 18)],
        ]

    def test_horizon_one_means_daily(self) -> None:
        days = [date(2026, 6, 15), date(2026, 6, 16)]
        assert _group_fresh_days(days, 1) == [
            [date(2026, 6, 15)],
            [date(2026, 6, 16)],
        ]


class TestPlanOrders:
    def test_hybrid_split(self) -> None:
        mon, tue, thu = date(2026, 6, 15), date(2026, 6, 16), date(2026, 6, 18)
        ingredients = [
            ing("kuřecí prsa", mon),
            ing("těstoviny", mon),
            ing("mozzarella", tue),
            ing("losos filet", thu),
            ing("rýže", thu),
            ing("sůl", mon),  # pantry -> dropped
        ]
        orders = plan_orders(ingredients, Classifier(), fresh_horizon_days=2)

        kinds = [o.kind for o in orders]
        assert kinds.count(OrderKind.WEEKLY_DURABLE) == 1
        assert kinds.count(OrderKind.FRESH) == 2

        weekly = next(o for o in orders if o.kind is OrderKind.WEEKLY_DURABLE)
        assert weekly.delivery_date == mon
        assert {i.name for i in weekly.items} == {"těstoviny", "rýže"}

        fresh_deliveries = [o.delivery_date for o in orders if o.kind is OrderKind.FRESH]
        assert fresh_deliveries == [mon, thu]  # mon order covers mon+tue

    def test_same_ingredient_aggregated(self) -> None:
        mon = date(2026, 6, 15)
        ingredients = [
            ing("Cibule", mon, "1 ks", "Guláš"),
            ing("cibule", mon, "2 ks", "Polévka"),
        ]
        orders = plan_orders(ingredients, Classifier(), fresh_horizon_days=2)
        assert len(orders) == 1
        item = orders[0].items[0]
        assert item.quantities == ["1 ks", "2 ks"]
        assert item.recipes == ["Guláš", "Polévka"]

    def test_no_ingredients_no_orders(self) -> None:
        assert plan_orders([], Classifier()) == []

    def test_deterministic_item_order(self) -> None:
        mon = date(2026, 6, 15)
        ingredients = [ing("rýže", mon), ing("čočka", mon), ing("kuskus", mon)]
        orders = plan_orders(ingredients, Classifier())
        names = [i.name for i in orders[0].items]
        # sorted by normalized (diacritics-stripped) name
        assert names == ["čočka", "kuskus", "rýže"]
