"""Config flow for electricityinfo_nz integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DEVELOPER_PORTAL_URL,
    DOMAIN,
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
        # Placeholder: Will be implemented in Phase 3 (US1)
        _LOGGER.debug("OAuth redirect step not yet implemented")
        return self.async_abort(reason="not_implemented")

    async def async_step_auth_callback(
        self,
        data: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Handle OAuth callback."""
        # Placeholder: Will be implemented in Phase 3 (US1)
        _LOGGER.debug("OAuth callback step not yet implemented")
        return self.async_abort(reason="not_implemented")

    async def async_step_auth_validate(self) -> ConfigFlowResult:
        """Validate obtained token."""
        # Placeholder: Will be implemented in Phase 4 (US2)
        _LOGGER.debug("Token validation step not yet implemented")
        return self.async_abort(reason="not_implemented")
