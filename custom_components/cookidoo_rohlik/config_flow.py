"""Config flow for the Cookidoo → Rohlík integration."""

from __future__ import annotations

import json
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_COOKIDOO_EMAIL,
    CONF_COOKIDOO_PASSWORD,
    CONF_ROHLIK_EMAIL,
    CONF_ROHLIK_PASSWORD,
    DEFAULT_AUTO_EXECUTE,
    DEFAULT_FRESH_HORIZON_DAYS,
    DEFAULT_OVERRIDES_JSON,
    DOMAIN,
    OPT_AUTO_EXECUTE,
    OPT_FRESH_HORIZON_DAYS,
    OPT_OVERRIDES_JSON,
)
from .core.rohlik_client import RohlikAuthError, RohlikClient

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COOKIDOO_EMAIL): str,
        vol.Required(CONF_COOKIDOO_PASSWORD): str,
        vol.Required(CONF_ROHLIK_EMAIL): str,
        vol.Required(CONF_ROHLIK_PASSWORD): str,
    }
)


class CookidooRohlikConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Single-instance config flow; validates Rohlik credentials on setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                async with RohlikClient(
                    user_input[CONF_ROHLIK_EMAIL], user_input[CONF_ROHLIK_PASSWORD]
                ):
                    pass
            except RohlikAuthError:
                errors["base"] = "invalid_rohlik_auth"
            except Exception:  # noqa: BLE001 - surface as generic error in UI
                _LOGGER.exception("Rohlik validation failed")
                errors["base"] = "cannot_connect"
            # Cookidoo credentials are validated lazily on first plan_week
            # call (the unofficial login flow is heavier; keep setup fast).
            if not errors:
                return self.async_create_entry(
                    title="Cookidoo → Rohlík", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "CookidooRohlikOptionsFlow":
        return CookidooRohlikOptionsFlow()


class CookidooRohlikOptionsFlow(config_entries.OptionsFlow):
    """Options: fresh horizon, auto cart fill, classification overrides."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                overrides = json.loads(user_input[OPT_OVERRIDES_JSON])
                if not isinstance(overrides, dict):
                    raise ValueError
            except ValueError:
                errors["base"] = "invalid_overrides_json"
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    OPT_FRESH_HORIZON_DAYS,
                    default=options.get(
                        OPT_FRESH_HORIZON_DAYS, DEFAULT_FRESH_HORIZON_DAYS
                    ),
                ): vol.All(int, vol.Range(min=1, max=4)),
                vol.Required(
                    OPT_AUTO_EXECUTE,
                    default=options.get(OPT_AUTO_EXECUTE, DEFAULT_AUTO_EXECUTE),
                ): bool,
                vol.Required(
                    OPT_OVERRIDES_JSON,
                    default=options.get(OPT_OVERRIDES_JSON, DEFAULT_OVERRIDES_JSON),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
