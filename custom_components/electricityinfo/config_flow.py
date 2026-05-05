"""Config flow for electricityinfo integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from electricityinfo_nz.auth import OAuth2ClientCredentials
from electricityinfo_nz.client import MarketPricesClient
from electricityinfo_nz.exceptions import AuthenticationError, TransportError
from homeassistant import config_entries
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DEVELOPER_PORTAL_URL,
    DOMAIN,
    MAX_VALIDATION_ATTEMPTS,
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
        self.access_token: str | None = None
        self.validation_attempts: int = 0

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this entry."""
        return OptionsFlowHandler()

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
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()

                # Proceed to token exchange and validation
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
            # Step 2: Exchange credentials using Client Credentials flow
            _LOGGER.info("Exchanging credentials for access token")
            oauth = OAuth2ClientCredentials(
                client_id=self.client_id,
                client_secret=self.client_secret,
                base_url=OAUTH_BASE_URL,
            )
            self.access_token = await self.hass.async_add_executor_job(oauth.get_token)
            _LOGGER.info("✓ Successfully obtained access token")

            # Step 3: Validate credentials using MarketPricesClient
            _LOGGER.info("Validating credentials by calling get_schedules()")
            client = MarketPricesClient(access_token=self.access_token)
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
            # Transient errors - allow retry
            self.validation_attempts += 1
            _LOGGER.warning(
                "Token exchange/validation transient error (attempt %d/%d): %s",
                self.validation_attempts,
                MAX_VALIDATION_ATTEMPTS,
                err,
            )

            if self.validation_attempts < MAX_VALIDATION_ATTEMPTS:
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
                MAX_VALIDATION_ATTEMPTS,
            )
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="auth_validate",
                errors=errors,
                last_step=True,
            )

        # Successful validation - create config entry
        # Set unique_id again to verify single instance
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        _LOGGER.info("✓ Creating config entry for Electricityinfo NZ")
        return self.async_create_entry(
            title="Electricityinfo NZ",
            data={
                CONF_CLIENT_ID: self.client_id,
                CONF_CLIENT_SECRET: self.client_secret,
            },
            options={
                "sensors": [],
            },
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for sensor configuration."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Manage the options for sensor configuration."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["configure_sensors"],
        )

    async def async_step_configure_sensors(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Show sensor list and allow CRUD operations."""
        from .const import (
            CONF_SENSORS,
        )

        sensors = self.config_entry.options.get(CONF_SENSORS, [])

        # Create menu entries for each sensor and add button
        menu_options = []
        for idx, sensor in enumerate(sensors):
            menu_options.append(f"edit_sensor_{idx}")
        menu_options.append("add_sensor")

        if not sensors:
            # No sensors configured yet, go straight to add
            return await self.async_step_add_sensor()

        return self.async_show_menu(
            step_id="configure_sensors",
            menu_options=menu_options,
            description_placeholders={
                "sensor_count": str(len(sensors)),
            },
        )

    async def async_step_add_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a new price sensor."""
        from homeassistant.helpers.selector import (
            NumberSelector,
            NumberSelectorConfig,
            NumberSelectorMode,
            SelectSelector,
            SelectSelectorConfig,
        )

        from .const import (
            CONF_FORWARD_PRICES_COUNT,
            CONF_MARKET_TYPE,
            CONF_NODE,
            CONF_SCHEDULE_TYPE,
            CONF_SENSOR_ID,
            CONF_SENSORS,
            CONF_UNIT_PREFERENCE,
            DEFAULT_FORWARD_PRICES_COUNT,
            DEFAULT_UNIT_PREFERENCE,
            MARKET_NODES,
            MARKET_TYPES,
            PRICE_UNITS,
            SCHEDULE_TYPES,
        )

        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate sensor configuration
            sensors = self.config_entry.options.get(CONF_SENSORS, [])
            sensor_id = user_input.get(CONF_SENSOR_ID, "").strip()

            # Check for duplicate ID
            if any(s.get(CONF_SENSOR_ID) == sensor_id for s in sensors):
                errors[CONF_SENSOR_ID] = "sensor_id_duplicate"

            # Validate required fields
            if not sensor_id:
                errors[CONF_SENSOR_ID] = "sensor_id_required"
            if not user_input.get(CONF_SCHEDULE_TYPE):
                errors[CONF_SCHEDULE_TYPE] = "schedule_type_required"
            if not user_input.get(CONF_MARKET_TYPE):
                errors[CONF_MARKET_TYPE] = "market_type_required"
            if not user_input.get(CONF_NODE):
                errors[CONF_NODE] = "node_required"

            if not errors:
                # Add new sensor
                new_sensor = {
                    CONF_SENSOR_ID: sensor_id,
                    CONF_SCHEDULE_TYPE: user_input[CONF_SCHEDULE_TYPE],
                    CONF_MARKET_TYPE: user_input[CONF_MARKET_TYPE],
                    CONF_NODE: user_input[CONF_NODE],
                    CONF_FORWARD_PRICES_COUNT: user_input.get(
                        CONF_FORWARD_PRICES_COUNT, DEFAULT_FORWARD_PRICES_COUNT
                    ),
                    CONF_UNIT_PREFERENCE: user_input.get(
                        CONF_UNIT_PREFERENCE, DEFAULT_UNIT_PREFERENCE
                    ),
                }
                sensors.append(new_sensor)

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    options={**self.config_entry.options, CONF_SENSORS: sensors},
                )
                return self.async_abort(reason="sensor_added")

        return self.async_show_form(
            step_id="add_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SENSOR_ID): str,
                    vol.Required(CONF_SCHEDULE_TYPE): SelectSelector(
                        SelectSelectorConfig(options=SCHEDULE_TYPES)
                    ),
                    vol.Required(CONF_MARKET_TYPE): SelectSelector(
                        SelectSelectorConfig(options=MARKET_TYPES)
                    ),
                    vol.Required(CONF_NODE): SelectSelector(
                        SelectSelectorConfig(options=MARKET_NODES)
                    ),
                    vol.Optional(
                        CONF_FORWARD_PRICES_COUNT,
                        default=DEFAULT_FORWARD_PRICES_COUNT,
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=168, mode=NumberSelectorMode.SLIDER
                        )
                    ),
                    vol.Optional(
                        CONF_UNIT_PREFERENCE,
                        default=DEFAULT_UNIT_PREFERENCE,
                    ): SelectSelector(SelectSelectorConfig(options=PRICE_UNITS)),
                }
            ),
            errors=errors,
        )

    async def async_step_edit_sensor_0(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit sensor at index 0."""
        return await self._async_edit_sensor(0, user_input)

    async def async_step_edit_sensor_1(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit sensor at index 1."""
        return await self._async_edit_sensor(1, user_input)

    async def async_step_edit_sensor_2(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit sensor at index 2."""
        return await self._async_edit_sensor(2, user_input)

    async def async_step_edit_sensor_3(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit sensor at index 3."""
        return await self._async_edit_sensor(3, user_input)

    async def async_step_edit_sensor_4(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit sensor at index 4."""
        return await self._async_edit_sensor(4, user_input)

    async def _async_edit_sensor(
        self, index: int, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit a sensor configuration."""
        from homeassistant.helpers.selector import (
            NumberSelector,
            NumberSelectorConfig,
            NumberSelectorMode,
            SelectSelector,
            SelectSelectorConfig,
        )

        from .const import (
            CONF_FORWARD_PRICES_COUNT,
            CONF_MARKET_TYPE,
            CONF_NODE,
            CONF_SCHEDULE_TYPE,
            CONF_SENSOR_ID,
            CONF_SENSORS,
            CONF_UNIT_PREFERENCE,
            MARKET_NODES,
            MARKET_TYPES,
            PRICE_UNITS,
            SCHEDULE_TYPES,
        )

        sensors = self.config_entry.options.get(CONF_SENSORS, [])
        if index >= len(sensors):
            return self.async_abort(reason="sensor_not_found")

        sensor = sensors[index]
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get("delete"):
                # Delete sensor
                sensors.pop(index)
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    options={**self.config_entry.options, CONF_SENSORS: sensors},
                )
                return self.async_abort(reason="sensor_deleted")

            # Update sensor
            sensors[index] = {
                CONF_SENSOR_ID: sensor[CONF_SENSOR_ID],  # Keep original ID
                CONF_SCHEDULE_TYPE: user_input[CONF_SCHEDULE_TYPE],
                CONF_MARKET_TYPE: user_input[CONF_MARKET_TYPE],
                CONF_NODE: user_input[CONF_NODE],
                CONF_FORWARD_PRICES_COUNT: user_input.get(
                    CONF_FORWARD_PRICES_COUNT,
                    sensor.get(CONF_FORWARD_PRICES_COUNT),
                ),
                CONF_UNIT_PREFERENCE: user_input.get(
                    CONF_UNIT_PREFERENCE,
                    sensor.get(CONF_UNIT_PREFERENCE),
                ),
            }

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                options={**self.config_entry.options, CONF_SENSORS: sensors},
            )
            return self.async_abort(reason="sensor_updated")

        return self.async_show_form(
            step_id=f"edit_sensor_{index}",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCHEDULE_TYPE,
                        default=sensor.get(CONF_SCHEDULE_TYPE),
                    ): SelectSelector(SelectSelectorConfig(options=SCHEDULE_TYPES)),
                    vol.Required(
                        CONF_MARKET_TYPE,
                        default=sensor.get(CONF_MARKET_TYPE),
                    ): SelectSelector(SelectSelectorConfig(options=MARKET_TYPES)),
                    vol.Required(
                        CONF_NODE,
                        default=sensor.get(CONF_NODE),
                    ): SelectSelector(SelectSelectorConfig(options=MARKET_NODES)),
                    vol.Optional(
                        CONF_FORWARD_PRICES_COUNT,
                        default=sensor.get(CONF_FORWARD_PRICES_COUNT),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=168, mode=NumberSelectorMode.SLIDER
                        )
                    ),
                    vol.Optional(
                        CONF_UNIT_PREFERENCE,
                        default=sensor.get(CONF_UNIT_PREFERENCE),
                    ): SelectSelector(SelectSelectorConfig(options=PRICE_UNITS)),
                    vol.Optional("delete", default=False): bool,
                }
            ),
            errors=errors,
            description_placeholders={
                "sensor_id": sensor.get(CONF_SENSOR_ID, "Unknown"),
            },
        )
