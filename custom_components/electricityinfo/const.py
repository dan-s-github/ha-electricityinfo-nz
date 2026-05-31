"""Constants for electricityinfo_nz."""

from logging import Logger, getLogger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.helpers.selector import SelectOptionDict

LOGGER: Logger = getLogger(__package__)

DOMAIN = "electricityinfo"

# OAuth2 Client Credentials Configuration
OAUTH_BASE_URL = "https://api.electricityinfo.co.nz"

# Config Flow
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"  # noqa: S105

# Help URLs
DEVELOPER_PORTAL_URL = "https://developer.electricityinfo.co.nz"

# Validation retry configuration
MAX_VALIDATION_ATTEMPTS = 3
VALIDATION_TIMEOUT = 10  # seconds

# Coordinator update / retry configuration
UPDATE_INTERVAL_MINUTES = 5
RETRY_INTERVAL_MINUTES = 1
MAX_RETRIES = 2

# RTD fetch configuration
RTD_BACK_PERIODS = 3  # fetch 3 x 5-min RTD dispatch intervals (~15 min of history)

# Staleness guard for LivePriceSensor restore — kept at 30 min regardless of poll
LIVE_PRICE_RESTORE_STALENESS_MINUTES = 30

# Sensor Configuration Options
CONF_SENSOR_NAME = "name"
CONF_SCHEDULE_TYPE = "schedule_type"
CONF_MARKET_TYPE = "market_type"
CONF_NODE = "node"
CONF_FORWARD_PRICES_COUNT = "forward_prices_count"

# 003 market node subentry configuration
SUBENTRY_TYPE = "market_node"
CONF_PRICE_UNIT = "price_unit"
CONF_ENABLE_LIVE_PRICE = "enable_live_price"
CONF_ENABLE_FORECAST = "enable_forecast"
CONF_FORECAST_TYPE = "forecast_type"
CONF_FORECAST_HORIZONS = "forecast_horizons"
CONF_FORECAST_RETENTION_HOURS = "forecast_retention_hours"
CONF_ENABLE_ACCOUNTING = "enable_accounting"
CONF_ACCOUNTING_RETENTION_HOURS = "accounting_retention_hours"
CONF_IMPORT_METER_ENTITY_ID = "import_meter_entity_id"
CONF_EXPORT_METER_ENTITY_ID = "export_meter_entity_id"

# Default Sensor Configuration
DEFAULT_FORWARD_PRICES_COUNT = 24
DEFAULT_FORECAST_RETENTION_HOURS = 24
DEFAULT_ACCOUNTING_RETENTION_HOURS = 24

# Allowed Schedule Types (WITS API codes)
SCHEDULE_TYPES = [
    "Final",
    "Interim",
    "NRSL",
    "NRSS",
    "PRSL",
    "PRSS",
    "RTD",
    "WDS",
]

FORECAST_TYPES = ["price_responsive", "non_responsive"]
FORECAST_HORIZONS = ["day_ahead", "intraday"]
FORECAST_RETENTION_OPTIONS = [6, 12, 24]
ACCOUNTING_RETENTION_OPTIONS = [24, 48]

PRICE_UNITS = ["c/kWh", "NZD/kWh"]
PRICE_UNIT_OPTIONS: list[SelectOptionDict] = [
    {"value": "c/kWh", "label": "c/kWh (cents per kilowatt-hour)"},
    {"value": "NZD/kWh", "label": "NZD/kWh (dollars per kilowatt-hour)"},
]

FORECAST_TYPE_OPTIONS: list[SelectOptionDict] = [
    {"value": "price_responsive", "label": "Price-responsive (PRSL/PRSS)"},
    {"value": "non_responsive", "label": "Non-responsive (NRSL/NRSS)"},
]

FORECAST_HORIZON_OPTIONS: list[SelectOptionDict] = [
    {"value": "day_ahead", "label": "Day-ahead (24h / 48 periods)"},
    {"value": "intraday", "label": "Intraday (4h forward / 8 periods)"},
]

FORECAST_RETENTION_OPTIONS_SELECT: list[SelectOptionDict] = [
    {"value": "6", "label": "6 hours"},
    {"value": "12", "label": "12 hours"},
    {"value": "24", "label": "24 hours"},
]

ACCOUNTING_RETENTION_OPTIONS_SELECT: list[SelectOptionDict] = [
    {"value": "24", "label": "24 hours"},
    {"value": "48", "label": "48 hours"},
]

FORECAST_SCHEDULE_MAP: dict[str, dict[str, str]] = {
    "price_responsive": {"day_ahead": "PRSL", "intraday": "PRSS"},
    "non_responsive": {"day_ahead": "NRSL", "intraday": "NRSS"},
}

# UI label/value pairs for schedule type selector
# Note: Final and Interim schedule types are not yet supported
SCHEDULE_TYPE_OPTIONS: list[SelectOptionDict] = [
    {"value": "NRSL", "label": "NRSL (Non-responsive long)"},
    {"value": "NRSS", "label": "NRSS (Non-responsive short)"},
    {"value": "PRSL", "label": "PRSL (Price-responsive long)"},
    {"value": "PRSS", "label": "PRSS (Price-responsive short)"},
    {"value": "RTD", "label": "RTD (Real-time dispatch)"},
    {"value": "WDS", "label": "WDS (Weekly dispatch schedule)"},
]

# Allowed Market Types (WITS API codes)
MARKET_TYPES = [
    "E",
    "R",
]

# UI label/value pairs for market type selector
MARKET_TYPE_OPTIONS: list[SelectOptionDict] = [
    {"value": "E", "label": "Energy (E)"},
    {"value": "R", "label": "Reserve (R)"},
]

# Market nodes (WITS grid reference nodes)
MARKET_NODES = [
    "BRB0331",
    "OTA2201",
    "HLY2201",
    "WKM2201",
    "TUI1101",
    "SFD2201",
    "HAY2201",
    "STK2201",
    "DOB0661",
    "ISL2201",
    "BEN2201",
    "HWB2201",
    "INV2201",
]

# UI label/value pairs for node selector (NI = North Island, SI = South Island)
MARKET_NODE_OPTIONS: list[SelectOptionDict] = [
    {"value": "BRB0331", "label": "BRB0331 (Bream Bay, NI)"},
    {"value": "OTA2201", "label": "OTA2201 (Otahuhu, NI)"},
    {"value": "HLY2201", "label": "HLY2201 (Huntly, NI)"},
    {"value": "WKM2201", "label": "WKM2201 (Waikamaka, NI)"},
    {"value": "TUI1101", "label": "TUI1101 (Tuai, NI)"},
    {"value": "SFD2201", "label": "SFD2201 (Stratford, NI)"},
    {"value": "HAY2201", "label": "HAY2201 (Haywards, NI)"},
    {"value": "STK2201", "label": "STK2201 (Stoke, SI)"},
    {"value": "DOB0661", "label": "DOB0661 (Dobson, SI)"},
    {"value": "ISL2201", "label": "ISL2201 (Islington, SI)"},
    {"value": "BEN2201", "label": "BEN2201 (Benmore, SI)"},
    {"value": "HWB2201", "label": "HWB2201 (Hawea, SI)"},
    {"value": "INV2201", "label": "INV2201 (Invercargill, SI)"},
]

# Price Unit Conversion (1 NZD/MWh = 0.1 c/kWh)
NZD_PER_MWH_TO_C_PER_KWH = 0.1
C_PER_KWH_TO_NZD_PER_MWH = 10.0
NZD_PER_MWH_TO_NZD_PER_KWH = 0.001

DAY_AHEAD_FORWARD_PERIODS = 48
INTRADAY_FORWARD_PERIODS = 8
