"""Config flow for electricityinfo integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from electricityinfo_nz import AsyncMarketPricesClient
from electricityinfo_nz.exceptions import AuthenticationError, TransportError
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_FORWARD_PRICES_COUNT,
    CONF_MARKET_TYPE,
    CONF_NODE,
    CONF_SCHEDULE_TYPE,
    CONF_SENSOR_NAME,
    DEFAULT_FORWARD_PRICES_COUNT,
    DEVELOPER_PORTAL_URL,
    DOMAIN,
    MARKET_NODE_OPTIONS,
    MARKET_NODES,
    MARKET_TYPE_OPTIONS,
    MARKET_TYPES,
    MAX_VALIDATION_ATTEMPTS,
    SCHEDULE_TYPE_OPTIONS,
    SCHEDULE_TYPES,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigFlowResult

_LOGGER = logging.getLogger(__name__)


def _sensor_title(data: dict[str, Any]) -> str:
    """Derive a display title from sensor form data."""
    name = (data.get(CONF_SENSOR_NAME) or "").strip()
    node = data.get(CONF_NODE, "")
    schedule = data.get(CONF_SCHEDULE_TYPE, "")
    market = data.get(CONF_MARKET_TYPE, "")
    config_label = f"{node} {schedule} ({market})"
    if name:
        return f"{name} · {config_label}"
    return config_label


def _build_sensor_form_schema(
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build the voluptuous schema for the add/edit sensor form."""
    d = defaults or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_SENSOR_NAME,
                default=d.get(CONF_SENSOR_NAME, ""),
            ): str,
            vol.Required(
                CONF_SCHEDULE_TYPE,
                **(
                    {"default": d[CONF_SCHEDULE_TYPE]}
                    if CONF_SCHEDULE_TYPE in d
                    else {}
                ),
            ): SelectSelector(SelectSelectorConfig(options=SCHEDULE_TYPE_OPTIONS)),
            vol.Required(
                CONF_MARKET_TYPE,
                **({"default": d[CONF_MARKET_TYPE]} if CONF_MARKET_TYPE in d else {}),
            ): SelectSelector(SelectSelectorConfig(options=MARKET_TYPE_OPTIONS)),
            vol.Required(
                CONF_NODE,
                **({"default": d[CONF_NODE]} if CONF_NODE in d else {}),
            ): SelectSelector(SelectSelectorConfig(options=MARKET_NODE_OPTIONS)),
            vol.Optional(
                CONF_FORWARD_PRICES_COUNT,
                default=d.get(CONF_FORWARD_PRICES_COUNT, DEFAULT_FORWARD_PRICES_COUNT),
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=84, mode=NumberSelectorMode.SLIDER)
            ),
        }
    )


def _validate_sensor_fields(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate sensor form fields and return a dict of field → error key."""
    errors: dict[str, str] = {}
    if user_input.get(CONF_SCHEDULE_TYPE) not in SCHEDULE_TYPES:
        errors[CONF_SCHEDULE_TYPE] = "schedule_type_invalid"
    if user_input.get(CONF_MARKET_TYPE) not in MARKET_TYPES:
        errors[CONF_MARKET_TYPE] = "market_type_invalid"
    if user_input.get(CONF_NODE) not in MARKET_NODES:
        errors[CONF_NODE] = "node_invalid"
    return errors


def _build_sensor_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Build sensor data dict from validated user input."""
    data: dict[str, Any] = {
        CONF_SCHEDULE_TYPE: user_input[CONF_SCHEDULE_TYPE],
        CONF_MARKET_TYPE: user_input[CONF_MARKET_TYPE],
        CONF_NODE: user_input[CONF_NODE],
        CONF_FORWARD_PRICES_COUNT: int(
            user_input.get(CONF_FORWARD_PRICES_COUNT, DEFAULT_FORWARD_PRICES_COUNT)
        ),
    }
    name = (user_input.get(CONF_SENSOR_NAME) or "").strip()
    if name:
        data[CONF_SENSOR_NAME] = name
    return data


class ElectricityInfoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for electricityinfo_nz."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        super().__init__()
        self.client_id: str | None = None
        self.client_secret: str | None = None
        self.access_token: str | None = None
        self.validation_attempts: int = 0

    @classmethod
    def async_get_supported_subentry_types(
        cls,
        config_entry: config_entries.ConfigEntry,  # noqa: ARG003
    ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
        """Return supported subentry types."""
        return {"sensor": SensorSubentryFlowHandler}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step (credential input)."""
        _LOGGER.debug("async_step_user called with user_input: %s", bool(user_input))
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("Processing user credentials submission")
            if not user_input.get(CONF_CLIENT_ID):
                errors[CONF_CLIENT_ID] = "client_id_required"
                _LOGGER.warning("Missing client_id")
            if not user_input.get(CONF_CLIENT_SECRET):
                errors[CONF_CLIENT_SECRET] = "client_secret_required"
                _LOGGER.warning("Missing client_secret")

            if not errors:
                self.client_id = user_input[CONF_CLIENT_ID]
                self.client_secret = user_input[CONF_CLIENT_SECRET]
                _LOGGER.info(
                    "Credentials received, proceeding to token exchange and validation"
                )
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return await self.async_step_auth_validate()

        _LOGGER.debug("Showing user credentials form")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
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
            _LOGGER.info("Validating credentials by calling get_schedules()")
            session = async_get_clientsession(self.hass)
            client = AsyncMarketPricesClient(
                client_id=self.client_id,
                client_secret=self.client_secret,
                session=session,
            )
            await client.get_schedules()
            _LOGGER.info("✓ Credential validation successful")

        except AuthenticationError:
            _LOGGER.exception(
                "✗ Token exchange/validation failed with AuthenticationError"
            )
            errors["base"] = "invalid_auth"
            self.validation_attempts = 0
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_CLIENT_ID, default=self.client_id): str,
                        vol.Required(CONF_CLIENT_SECRET): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.PASSWORD)
                        ),
                    }
                ),
                errors=errors,
                description_placeholders={
                    "help_url": DEVELOPER_PORTAL_URL,
                },
            )

        except (TransportError, TimeoutError) as err:
            self.validation_attempts += 1
            _LOGGER.warning(
                "Token exchange/validation transient error (attempt %d/%d): %s",
                self.validation_attempts,
                MAX_VALIDATION_ATTEMPTS,
                err,
            )

            if self.validation_attempts < MAX_VALIDATION_ATTEMPTS:
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="auth_validate",
                    errors=errors,
                    description_placeholders={
                        "help_url": DEVELOPER_PORTAL_URL,
                    },
                    last_step=False,
                )
            _LOGGER.exception(
                "Token exchange/validation failed after %d attempts",
                MAX_VALIDATION_ATTEMPTS,
            )
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="auth_validate",
                errors=errors,
                last_step=True,
            )

        _LOGGER.info("✓ Creating config entry for Electricityinfo NZ")
        return self.async_create_entry(
            title="Electricityinfo NZ",
            data={
                CONF_CLIENT_ID: self.client_id,
                CONF_CLIENT_SECRET: self.client_secret,
            },
        )


class SensorSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Handle sensor subentry flows (add / reconfigure)."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Create a new price sensor subentry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_sensor_fields(user_input)
            if not errors:
                return self.async_create_entry(
                    title=_sensor_title(user_input),
                    data=_build_sensor_data(user_input),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_sensor_form_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Edit an existing sensor subentry."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_sensor_fields(user_input)
            if not errors:
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=_sensor_title(user_input),
                    data=_build_sensor_data(user_input),
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_sensor_form_schema(dict(subentry.data)),
            errors=errors,
        )
