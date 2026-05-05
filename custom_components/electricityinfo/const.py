"""Constants for electricityinfo_nz."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "electricityinfo"
VERSION = "1.0.0"

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

# Sensor Configuration Options
CONF_SENSORS = "sensors"
CONF_SENSOR_ID = "id"
CONF_SCHEDULE_TYPE = "schedule_type"
CONF_MARKET_TYPE = "market_type"
CONF_NODE = "node"
CONF_FORWARD_PRICES_COUNT = "forward_prices_count"
CONF_UNIT_PREFERENCE = "unit_preference"

# Allowed Schedule Types (Electricityinfo API)
SCHEDULE_TYPES = [
    "daily_spot",
    "forward_market",
    "generation_forecast",
]

# Allowed Market Types (Electricityinfo API)
MARKET_TYPES = [
    "energy",
    "ancillary_services",
    "reserve",
]

# Allowed Market Nodes (New Zealand Electricity Commission)
# NEA = North East Auckland, MID = Midlands, SOU = South
MARKET_NODES = [
    "NEA",
    "MID",
    "SOU",
    "HLY",
    "OTA",
    "CIC",
]

# Price Unit Preferences
PRICE_UNITS = [
    "NZD/MWh",
    "c/kWh",
]

# Default Sensor Configuration
DEFAULT_FORWARD_PRICES_COUNT = 24
DEFAULT_UNIT_PREFERENCE = "NZD/MWh"

# Update Coordinator Configuration
UPDATE_INTERVAL_MINUTES = 30
RETRY_INTERVAL_MINUTES = 1
MAX_RETRIES = 2

# Price Unit Conversion (1 NZD/MWh = 0.1 c/kWh)
NZD_PER_MWH_TO_C_PER_KWH = 0.1
C_PER_KWH_TO_NZD_PER_MWH = 10.0
