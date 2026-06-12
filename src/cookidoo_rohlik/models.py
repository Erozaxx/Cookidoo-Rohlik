"""Core data models for the Cookidoo -> Rohlik planner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class ItemClass(str, Enum):
    """Classification of an ingredient for ordering strategy."""

    FRESH = "fresh"      # order at most `fresh_horizon_days` ahead
    DURABLE = "durable"  # order once per week
    PANTRY = "pantry"    # assumed at home, never ordered


class OrderKind(str, Enum):
    """Kind of a planned order (drives checkout behaviour)."""

    WEEKLY_DURABLE = "weekly_durable"  # auto-checkout
    FRESH = "fresh"                    # cart + manual confirmation


@dataclass(frozen=True)
class Ingredient:
    """A single ingredient required by a recipe on a given day."""

    name: str
    quantity: str  # raw quantity string from Cookidoo, e.g. "500 g"
    recipe_name: str
    needed_on: date


@dataclass
class DayPlan:
    """Recipes planned in Cookidoo for one day."""

    day: date
    recipe_ids: list[str] = field(default_factory=list)
    recipe_names: list[str] = field(default_factory=list)


@dataclass
class OrderItem:
    """An aggregated ingredient inside a planned order."""

    name: str
    quantities: list[str] = field(default_factory=list)
    recipes: list[str] = field(default_factory=list)
    needed_on: list[date] = field(default_factory=list)


@dataclass
class PlannedOrder:
    """One Rohlik order to be created.

    delivery_date: the morning the order should arrive.
    covers_days: cooking days whose ingredients are included.
    """

    kind: OrderKind
    delivery_date: date
    covers_days: list[date]
    items: list[OrderItem] = field(default_factory=list)
