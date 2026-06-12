"""Split a week of ingredients into Rohlik orders.

Strategy
--------
- PANTRY items are dropped (assumed at home).
- DURABLE items go into one weekly order, delivered on the morning of
  the first cooking day (or a configured weekly delivery day).
- FRESH items are grouped greedily: an order delivered on the morning
  of cooking day D covers fresh ingredients for cooking days within
  [D, D + fresh_horizon_days - 1]. Default horizon is 2 days, i.e.
  "today and tomorrow at most".

The output is deterministic: orders sorted by delivery date, items
sorted by name.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from .classify import Classifier, normalize
from .models import Ingredient, ItemClass, OrderItem, OrderKind, PlannedOrder


def _aggregate(ingredients: list[Ingredient]) -> list[OrderItem]:
    """Merge ingredients with the same normalized name into one item."""
    by_name: dict[str, OrderItem] = {}
    for ing in ingredients:
        key = normalize(ing.name)
        item = by_name.get(key)
        if item is None:
            item = OrderItem(name=ing.name)
            by_name[key] = item
        if ing.quantity:
            item.quantities.append(ing.quantity)
        if ing.recipe_name not in item.recipes:
            item.recipes.append(ing.recipe_name)
        if ing.needed_on not in item.needed_on:
            item.needed_on.append(ing.needed_on)
    items = list(by_name.values())
    for item in items:
        item.needed_on.sort()
    items.sort(key=lambda i: normalize(i.name))
    return items


def _group_fresh_days(cooking_days: list[date], horizon_days: int) -> list[list[date]]:
    """Greedily group cooking days into windows of `horizon_days` calendar days.

    Each window starts on a cooking day; the order is delivered that
    morning and may cover further cooking days up to
    start + horizon_days - 1.
    """
    groups: list[list[date]] = []
    remaining = sorted(set(cooking_days))
    while remaining:
        start = remaining[0]
        window_end = start + timedelta(days=horizon_days - 1)
        group = [d for d in remaining if d <= window_end]
        groups.append(group)
        remaining = [d for d in remaining if d > window_end]
    return groups


def plan_orders(
    ingredients: list[Ingredient],
    classifier: Classifier,
    fresh_horizon_days: int = 2,
    weekly_delivery_day: date | None = None,
) -> list[PlannedOrder]:
    """Produce the list of orders for one week of ingredients."""
    if fresh_horizon_days < 1:
        raise ValueError("fresh_horizon_days must be >= 1")

    fresh: list[Ingredient] = []
    durable: list[Ingredient] = []
    for ing in ingredients:
        cls = classifier.classify(ing.name)
        if cls is ItemClass.PANTRY:
            continue
        (fresh if cls is ItemClass.FRESH else durable).append(ing)

    orders: list[PlannedOrder] = []

    if durable:
        cooking_days = sorted({i.needed_on for i in durable})
        delivery = weekly_delivery_day or cooking_days[0]
        if delivery > cooking_days[0]:
            raise ValueError(
                f"weekly_delivery_day {delivery} is after first cooking day {cooking_days[0]}"
            )
        orders.append(
            PlannedOrder(
                kind=OrderKind.WEEKLY_DURABLE,
                delivery_date=delivery,
                covers_days=cooking_days,
                items=_aggregate(durable),
            )
        )

    if fresh:
        by_day: dict[date, list[Ingredient]] = defaultdict(list)
        for ing in fresh:
            by_day[ing.needed_on].append(ing)
        for group in _group_fresh_days(sorted(by_day), fresh_horizon_days):
            group_ingredients = [i for d in group for i in by_day[d]]
            orders.append(
                PlannedOrder(
                    kind=OrderKind.FRESH,
                    delivery_date=group[0],
                    covers_days=group,
                    items=_aggregate(group_ingredients),
                )
            )

    orders.sort(key=lambda o: (o.delivery_date, o.kind.value))
    return orders
