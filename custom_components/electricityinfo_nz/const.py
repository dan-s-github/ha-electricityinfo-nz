"""Constants for electricityinfo_nz."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "electricityinfo_nz"
VERSION = "1.0.0"

# OAuth Configuration
OAUTH_AUTHORIZE_URL = "https://developer.electricityinfo.co.nz/oauth/authorize"
OAUTH_TOKEN_URL = "https://developer.electricityinfo.co.nz/oauth/token"  # noqa: S105
OAUTH_SCOPES = ["electricity:read"]

# Config Flow
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"  # noqa: S105
CONF_TOKEN = "token"  # noqa: S105

# Help URLs
DEVELOPER_PORTAL_URL = "https://developer.electricityinfo.co.nz"
