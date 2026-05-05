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
