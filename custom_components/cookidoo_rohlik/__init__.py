"""Cookidoo → Rohlík: plan the week, prepare Rohlik carts, notify.

Services (scheduling is left to user automations, see examples/):
- cookidoo_rohlik.plan_week:      fetch Cookidoo plan, show planned orders
- cookidoo_rohlik.prepare_orders: match products for orders delivered on a
  date (default: tomorrow); with execute=true fill the Rohlik cart.
  Always ends with a notification; checkout is manual in the Rohlik app.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

import voluptuous as vol
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_DATE,
    ATTR_EXECUTE,
    ATTR_WEEK,
    CONF_COOKIDOO_EMAIL,
    CONF_COOKIDOO_PASSWORD,
    CONF_ROHLIK_EMAIL,
    CONF_ROHLIK_PASSWORD,
    DEFAULT_AUTO_EXECUTE,
    DEFAULT_FRESH_HORIZON_DAYS,
    DOMAIN,
    EVENT_ORDERS_PREPARED,
    OPT_AUTO_EXECUTE,
    OPT_FRESH_HORIZON_DAYS,
    OPT_OVERRIDES_JSON,
    PRODUCT_MAP_FILENAME,
    SERVICE_PLAN_WEEK,
    SERVICE_PREPARE_ORDERS,
)
from .core.classify import Classifier, load_map_overrides
from .core.cookidoo_client import CookidooWeekClient
from .core.matching import ProductMatcher
from .core.models import Ingredient, PlannedOrder
from .core.orchestrator import render_resolution, resolve_order
from .core.planner import plan_orders
from .core.render import render_markdown
from .core.rohlik_client import RohlikClient

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLAN_WEEK_SCHEMA = vol.Schema({vol.Optional(ATTR_WEEK): cv.date})
PREPARE_ORDERS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DATE): cv.date,
        vol.Optional(ATTR_EXECUTE): cv.boolean,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry
    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


def _entry(hass: HomeAssistant) -> ConfigEntry:
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise RuntimeError("Cookidoo → Rohlík is not configured")
    return entries[0]


def _classifier(hass: HomeAssistant, entry: ConfigEntry) -> Classifier:
    overrides = json.loads(entry.options.get(OPT_OVERRIDES_JSON, "{}") or "{}")
    classifier = Classifier.from_config({"classification": {"overrides": overrides}})
    # class: fields in product_map.yaml win (one curation file for users)
    classifier.overrides.update(
        load_map_overrides(Path(hass.config.path(PRODUCT_MAP_FILENAME)))
    )
    return classifier


async def _fetch_week(
    entry: ConfigEntry, week_day: date
) -> list[Ingredient]:
    client = CookidooWeekClient(
        entry.data[CONF_COOKIDOO_EMAIL], entry.data[CONF_COOKIDOO_PASSWORD]
    )
    _, ingredients = await client.fetch_week_ingredients(week_day)
    return ingredients


def _plan(
    hass: HomeAssistant, entry: ConfigEntry, ingredients: list[Ingredient]
) -> list[PlannedOrder]:
    horizon = int(
        entry.options.get(OPT_FRESH_HORIZON_DAYS, DEFAULT_FRESH_HORIZON_DAYS)
    )
    return plan_orders(ingredients, _classifier(hass, entry), fresh_horizon_days=horizon)


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_PLAN_WEEK):
        return

    async def handle_plan_week(call: ServiceCall) -> None:
        entry = _entry(hass)
        week_day: date = call.data.get(ATTR_WEEK) or date.today()
        ingredients = await _fetch_week(entry, week_day)
        orders = _plan(hass, entry, ingredients)
        persistent_notification.async_create(
            hass,
            render_markdown(orders),
            title=f"Cookidoo → Rohlík: plán týdne {week_day.isoformat()}",
            notification_id=f"{DOMAIN}_plan",
        )

    async def handle_prepare_orders(call: ServiceCall) -> None:
        entry = _entry(hass)
        target: date = call.data.get(ATTR_DATE) or (date.today() + timedelta(days=1))
        execute: bool = call.data.get(
            ATTR_EXECUTE, entry.options.get(OPT_AUTO_EXECUTE, DEFAULT_AUTO_EXECUTE)
        )

        ingredients = await _fetch_week(entry, target)
        orders = [o for o in _plan(hass, entry, ingredients) if o.delivery_date == target]
        if not orders:
            _LOGGER.info("No planned order with delivery date %s", target)
            return

        matcher = ProductMatcher(
            cache_path=Path(hass.config.path(PRODUCT_MAP_FILENAME))
        )
        reports: list[str] = []
        unmatched: list[str] = []
        estimated = 0.0
        async with RohlikClient(
            entry.data[CONF_ROHLIK_EMAIL], entry.data[CONF_ROHLIK_PASSWORD]
        ) as client:
            for order in orders:
                res = await resolve_order(order, matcher, client, execute=execute)
                reports.append(render_resolution(res))
                unmatched.extend(m.item.name for m in res.unmatched)
                estimated += res.estimated_price

        footer = (
            "\n\n➡️ **Košík je naplněn — dokonči objednávku v aplikaci Rohlík.**"
            if execute
            else "\n\n(dry-run — košík nebyl změněn)"
        )
        persistent_notification.async_create(
            hass,
            "\n\n---\n\n".join(reports) + footer,
            title=f"Cookidoo → Rohlík: objednávka na {target.isoformat()}",
            notification_id=f"{DOMAIN}_prepare_{target.isoformat()}",
        )
        hass.bus.async_fire(
            EVENT_ORDERS_PREPARED,
            {
                "date": target.isoformat(),
                "executed": execute,
                "orders": len(orders),
                "estimated_price": round(estimated, 2),
                "unmatched": unmatched,
            },
        )

    hass.services.async_register(
        DOMAIN, SERVICE_PLAN_WEEK, handle_plan_week, schema=PLAN_WEEK_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PREPARE_ORDERS,
        handle_prepare_orders,
        schema=PREPARE_ORDERS_SCHEMA,
    )
