"""Config flow for electricityinfo_nz integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from electricityinfo_nz.auth import OAuth2ClientCredentials
from electricityinfo_nz.client import MarketPricesClient
from electricityinfo_nz.exceptions import AuthenticationError, TransportError
from homeassistant import config_entries

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DEVELOPER_PORTAL_URL,
    DOMAIN,
    OAUTH_BASE_URL,
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
        self.client_id: str | None = None
        self.client_secret: str | None = None
        self.validation_attempts: int = 0
        self.max_validation_attempts: int = 3

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step (credential input)."""
        _LOGGER.debug("async_step_user called with user_input: %s", bool(user_input))
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("Processing user credentials submission")
            # Validate credentials exist
            if not user_input.get(CONF_CLIENT_ID):
                errors[CONF_CLIENT_ID] = "client_id_required"
                _LOGGER.warning("Missing client_id")
            if not user_input.get(CONF_CLIENT_SECRET):
                errors[CONF_CLIENT_SECRET] = "client_secret_required"
                _LOGGER.warning("Missing client_secret")

            if not errors:
                # Store credentials for next step
                self.client_id = user_input[CONF_CLIENT_ID]
                self.client_secret = user_input[CONF_CLIENT_SECRET]
                _LOGGER.info(
                    "Credentials received, proceeding to token exchange and validation"
                )

                # Check for existing entry (single instance)
                await self.async_set_unique_id("electricityinfo_nz")
                self._abort_if_unique_id_configured()

                # Proceed to token exchange and validation
                return await self.async_step_auth_validate()

        _LOGGER.debug("Showing user credentials form")
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

    async def async_step_auth_validate(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Exchange credentials for token and validate it works."""
        _LOGGER.info("Starting token exchange and validation step")
        errors: dict[str, str] = {}

        try:
            # Step 2: Exchange credentials using Client Credentials flow
            _LOGGER.info(
                "Exchanging credentials for access token with client_id: %s",
                self.client_id,
            )
            oauth = OAuth2ClientCredentials(
                client_id=self.client_id,
                client_secret=self.client_secret,
                base_url=OAUTH_BASE_URL,
            )
            await self.hass.async_add_executor_job(oauth.get_token)
            _LOGGER.info("✓ Successfully obtained access token")

            # Step 3: Validate credentials using MarketPricesClient
            _LOGGER.info("Validating credentials by calling get_schedules()")
            client = MarketPricesClient(
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            await self.hass.async_add_executor_job(client.get_schedules)
            _LOGGER.info("✓ Credential validation successful")

        except AuthenticationError:
            # Permanent authentication error - credentials invalid
            _LOGGER.exception(
                "✗ Token exchange/validation failed with AuthenticationError"
            )
            errors["base"] = "invalid_auth"
            self.validation_attempts = 0
            # Return to step 1 with help link
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_CLIENT_ID, default=self.client_id): str,
                        vol.Required(CONF_CLIENT_SECRET): str,
                    }
                ),
                errors=errors,
                description_placeholders={
                    "help_url": DEVELOPER_PORTAL_URL,
                },
            )

        except (TransportError, TimeoutError) as err:
            # Transient errors - allow retry
            self.validation_attempts += 1
            _LOGGER.warning(
                "Token exchange/validation transient error (attempt %d/%d): %s",
                self.validation_attempts,
                self.max_validation_attempts,
                err,
            )

            if self.validation_attempts < self.max_validation_attempts:
                # Show retry option with error message
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="auth_validate",
                    errors=errors,
                    description_placeholders={
                        "help_url": DEVELOPER_PORTAL_URL,
                    },
                    last_step=False,
                )
            # Max attempts reached
            _LOGGER.exception(
                "Token exchange/validation failed after %d attempts",
                self.max_validation_attempts,
            )
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="auth_validate",
                errors=errors,
                last_step=True,
            )

        # Successful validation - create config entry
        # Set unique_id again to verify single instance
        await self.async_set_unique_id("electricityinfo_nz")
        self._abort_if_unique_id_configured()

        _LOGGER.info("✓ Creating config entry for Electricityinfo NZ")
        return self.async_create_entry(
            title="Electricityinfo NZ",
            data={
                CONF_CLIENT_ID: self.client_id,
                CONF_CLIENT_SECRET: self.client_secret,
            },
        )
