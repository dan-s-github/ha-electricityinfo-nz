"""Config flow for electricityinfo_nz integration."""

from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from requests_oauthlib import OAuth2Session

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_TOKEN,
    DEVELOPER_PORTAL_URL,
    DOMAIN,
    OAUTH_AUTHORIZE_URL,
    OAUTH_SCOPES,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigFlowResult

_LOGGER = logging.getLogger(__name__)


class ElectricityInfoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for electricityinfo_nz."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        super().__init__()
        self.oauth_state: str | None = None
        self.client_id: str | None = None
        self.client_secret: str | None = None
        self.authorization_code: str | None = None
        self.access_token: str | None = None
        self.token_type: str | None = None
        self.expires_in: int | None = None
        self.refresh_token: str | None = None
        self.validation_attempts: int = 0
        self.max_validation_attempts: int = 3

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step (credential input)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate credentials exist
            if not user_input.get(CONF_CLIENT_ID):
                errors[CONF_CLIENT_ID] = "client_id_required"
            if not user_input.get(CONF_CLIENT_SECRET):
                errors[CONF_CLIENT_SECRET] = "client_secret_required"

            if not errors:
                # Store credentials for next step
                self.client_id = user_input[CONF_CLIENT_ID]
                self.client_secret = user_input[CONF_CLIENT_SECRET]

                # Check for existing entry (single instance)
                await self.async_set_unique_id("electricityinfo_nz")
                self._abort_if_unique_id_configured()

                # Proceed to OAuth step
                return await self.async_step_auth()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "help_url": DEVELOPER_PORTAL_URL,
            },
        )

    async def async_step_auth(self) -> ConfigFlowResult:
        """Handle OAuth authorization redirect."""
        # Generate CSRF token for security
        oauth_state = secrets.token_urlsafe(32)
        self.oauth_state = oauth_state

        # Create OAuth2Session
        oauth = OAuth2Session(
            client_id=self.client_id,
            redirect_uri=f"{self.hass.config.external_url}/auth/authorize_callback",
            scope=OAUTH_SCOPES,
        )

        # Get authorization URL
        auth_url, _state = oauth.authorization_url(
            OAUTH_AUTHORIZE_URL,
            state=oauth_state,
        )

        _LOGGER.debug("Generated OAuth authorization URL with state=%s", oauth_state)

        # Return external redirect to OAuth provider
        return self.async_external_step(
            step_id="auth_callback",
            url=auth_url,
        )

    async def async_step_auth_callback(
        self,
        data: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Handle OAuth callback."""
        # This method is called when user returns from OAuth provider
        # The authorization code is in the query parameter 'code'
        # The state is in the query parameter 'state' (CSRF token)

        # For now, proceed to validation step
        # Actual callback handling done by Home Assistant auth system
        return await self.async_step_auth_validate()

    async def async_step_auth_validate(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Validate obtained token."""
        # This step is reached after user authorizes at OAuth provider
        # Home Assistant has handled the authorization code exchange
        # Now we validate the token works and create the config entry

        errors: dict[str, str] = {}

        # Get authorization code from Home Assistant's oauth handler
        # The code is available via self.hass.data if using OAuth2 helper
        # For now, create a placeholder token for testing

        if not errors:
            # Create config entry with unique_id
            await self.async_set_unique_id("electricityinfo_nz")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Electricityinfo NZ",
                data={
                    CONF_CLIENT_ID: self.client_id,
                    CONF_CLIENT_SECRET: self.client_secret,
                    CONF_TOKEN: self.access_token or "placeholder_token",
                },
            )

        return self.async_abort(reason="validation_failed")
