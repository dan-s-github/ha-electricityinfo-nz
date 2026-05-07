"""Constants for electricityinfo_nz."""

from logging import Logger, getLogger

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
UPDATE_INTERVAL_MINUTES = 30
RETRY_INTERVAL_MINUTES = 1
MAX_RETRIES = 2

# Sensor Configuration Options
CONF_SENSOR_NAME = "name"
CONF_SCHEDULE_TYPE = "schedule_type"
CONF_MARKET_TYPE = "market_type"
CONF_NODE = "node"
CONF_FORWARD_PRICES_COUNT = "forward_prices_count"

# Default Sensor Configuration
DEFAULT_FORWARD_PRICES_COUNT = 24

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

# UI label/value pairs for schedule type selector
SCHEDULE_TYPE_OPTIONS = [
    {"value": "Final", "label": "Final (Final settled prices)"},
    {"value": "Interim", "label": "Interim (Interim prices)"},
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
MARKET_TYPE_OPTIONS = [
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
MARKET_NODE_OPTIONS = [
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
