"""Constants for the Cookidoo → Rohlík integration."""

DOMAIN = "cookidoo_rohlik"

CONF_COOKIDOO_EMAIL = "cookidoo_email"
CONF_COOKIDOO_PASSWORD = "cookidoo_password"
CONF_ROHLIK_EMAIL = "rohlik_email"
CONF_ROHLIK_PASSWORD = "rohlik_password"

OPT_FRESH_HORIZON_DAYS = "fresh_horizon_days"
OPT_AUTO_EXECUTE = "auto_execute"
OPT_OVERRIDES_JSON = "overrides_json"

DEFAULT_FRESH_HORIZON_DAYS = 2
DEFAULT_AUTO_EXECUTE = False
DEFAULT_OVERRIDES_JSON = '{"cibule": "durable", "česnek": "durable", "brambory": "durable"}'

SERVICE_PLAN_WEEK = "plan_week"
SERVICE_PREPARE_ORDERS = "prepare_orders"

ATTR_WEEK = "week"
ATTR_DATE = "date"
ATTR_EXECUTE = "execute"

EVENT_ORDERS_PREPARED = f"{DOMAIN}_orders_prepared"

PRODUCT_MAP_FILENAME = "cookidoo_rohlik_product_map.json"
