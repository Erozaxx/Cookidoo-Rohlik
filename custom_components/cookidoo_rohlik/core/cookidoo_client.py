"""Thin async wrapper around the unofficial `cookidoo-api` package.

Fetches the calendar week and resolves each recipe's ingredients into
flat `Ingredient` records with the day they are needed on.

Verified against cookidoo-api 0.17.x:
- Cookidoo.get_recipes_in_calendar_week(day: date) -> list[CookidooCalendarDay]
- Cookidoo.get_recipe_details(id: str) -> CookidooShoppingRecipeDetails
  (.ingredients: list[CookidooIngredient(id, name, description)];
   `description` holds the quantity string, e.g. "500 g")
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime

import aiohttp
from cookidoo_api import Cookidoo, CookidooConfig, CookidooLocalizationConfig

from .models import DayPlan, Ingredient

logger = logging.getLogger(__name__)

CZ_LOCALIZATION = CookidooLocalizationConfig(
    country_code="cz",
    language="cs-CZ",
    url="https://cookidoo.cz/foundation/cs-CZ",
)


class CookidooWeekClient:
    """Fetch a week of planned recipes and their ingredients."""

    def __init__(
        self,
        email: str,
        password: str,
        localization: CookidooLocalizationConfig = CZ_LOCALIZATION,
    ) -> None:
        self._cfg = CookidooConfig(localization=localization, email=email, password=password)

    async def fetch_week_ingredients(
        self, week_day: date
    ) -> tuple[list[DayPlan], list[Ingredient]]:
        """Return (day plans, flat ingredient list) for the week containing `week_day`."""
        async with aiohttp.ClientSession(
            cookie_jar=aiohttp.CookieJar(unsafe=True)
        ) as session:
            api = Cookidoo(session, self._cfg)
            await api.login()

            calendar_days = await api.get_recipes_in_calendar_week(week_day)

            day_plans: list[DayPlan] = []
            ingredients: list[Ingredient] = []
            for cal_day in calendar_days:
                day = _parse_day_id(cal_day.id)
                plan = DayPlan(day=day)
                for recipe in cal_day.recipes:
                    plan.recipe_ids.append(recipe.id)
                    plan.recipe_names.append(recipe.name)
                day_plans.append(plan)

            # Resolve ingredients per recipe (sequential & gentle to the
            # unofficial API; the volume is small anyway).
            for plan in day_plans:
                for recipe_id, recipe_name in zip(plan.recipe_ids, plan.recipe_names):
                    details = await api.get_recipe_details(recipe_id)
                    for ing in details.ingredients:
                        ingredients.append(
                            Ingredient(
                                name=ing.name,
                                quantity=ing.description or "",
                                recipe_name=recipe_name,
                                needed_on=plan.day,
                            )
                        )
                    await asyncio.sleep(0.5)

            logger.info(
                "Fetched %d days, %d recipes, %d ingredient lines",
                len(day_plans),
                sum(len(p.recipe_ids) for p in day_plans),
                len(ingredients),
            )
            return day_plans, ingredients


def _parse_day_id(day_id: str) -> date:
    """Calendar day ids are ISO dates (e.g. '2026-06-15')."""
    return datetime.strptime(day_id[:10], "%Y-%m-%d").date()
