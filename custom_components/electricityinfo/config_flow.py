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
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
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
    ACCOUNTING_RETENTION_OPTIONS,
    ACCOUNTING_RETENTION_OPTIONS_SELECT,
    CONF_ACCOUNTING_RETENTION_HOURS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENABLE_ACCOUNTING,
    CONF_ENABLE_FORECAST,
    CONF_ENABLE_LIVE_PRICE,
    CONF_EXPORT_METER_ENTITY_ID,
    CONF_FORECAST_HORIZONS,
    CONF_FORECAST_RETENTION_HOURS,
    CONF_FORECAST_TYPE,
    CONF_FORWARD_PRICES_COUNT,
    CONF_IMPORT_METER_ENTITY_ID,
    CONF_MARKET_TYPE,
    CONF_NODE,
    CONF_PRICE_UNIT,
    CONF_SCHEDULE_TYPE,
    CONF_SENSOR_NAME,
    DEFAULT_ACCOUNTING_RETENTION_HOURS,
    DEFAULT_FORECAST_RETENTION_HOURS,
    DEFAULT_FORWARD_PRICES_COUNT,
    DEVELOPER_PORTAL_URL,
    DOMAIN,
    FORECAST_HORIZON_OPTIONS,
    FORECAST_HORIZONS,
    FORECAST_RETENTION_OPTIONS,
    FORECAST_RETENTION_OPTIONS_SELECT,
    FORECAST_TYPE_OPTIONS,
    FORECAST_TYPES,
    MARKET_NODE_OPTIONS,
    MARKET_NODES,
    MARKET_TYPE_OPTIONS,
    MARKET_TYPES,
    MAX_VALIDATION_ATTEMPTS,
    PRICE_UNIT_OPTIONS,
    PRICE_UNITS,
    SCHEDULE_TYPE_OPTIONS,
    SCHEDULE_TYPES,
    SUBENTRY_TYPE,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigFlowResult
    from homeassistant.core import HomeAssistant

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
    """Build the voluptuous schema for the legacy add/edit sensor form."""
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
    """Validate legacy sensor form fields and return a dict of field → error key."""
    errors: dict[str, str] = {}
    if user_input.get(CONF_SCHEDULE_TYPE) not in SCHEDULE_TYPES:
        errors[CONF_SCHEDULE_TYPE] = "schedule_type_invalid"
    if user_input.get(CONF_MARKET_TYPE) not in MARKET_TYPES:
        errors[CONF_MARKET_TYPE] = "market_type_invalid"
    if user_input.get(CONF_NODE) not in MARKET_NODES:
        errors[CONF_NODE] = "node_invalid"
    return errors


def _build_sensor_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Build legacy sensor data dict from validated user input."""
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


def _node_title(data: dict[str, Any]) -> str:
    """Derive display title from market node form data."""
    node = data.get(CONF_NODE, "")
    unit = data.get(CONF_PRICE_UNIT, "")
    return f"{node} [{unit}]"


def _build_node_form_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build schema for market node subentry flow."""
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_NODE, default=d.get(CONF_NODE, MARKET_NODES[0])
            ): SelectSelector(SelectSelectorConfig(options=MARKET_NODE_OPTIONS)),
            vol.Required(
                CONF_PRICE_UNIT, default=d.get(CONF_PRICE_UNIT, "c/kWh")
            ): SelectSelector(SelectSelectorConfig(options=PRICE_UNIT_OPTIONS)),
            vol.Optional(
                CONF_ENABLE_LIVE_PRICE, default=d.get(CONF_ENABLE_LIVE_PRICE, True)
            ): BooleanSelector(),
            vol.Optional(
                CONF_ENABLE_FORECAST, default=d.get(CONF_ENABLE_FORECAST, False)
            ): BooleanSelector(),
            vol.Optional(
                CONF_FORECAST_TYPE,
                default=d.get(CONF_FORECAST_TYPE, "price_responsive"),
            ): SelectSelector(SelectSelectorConfig(options=FORECAST_TYPE_OPTIONS)),
            vol.Optional(
                CONF_FORECAST_HORIZONS,
                default=d.get(CONF_FORECAST_HORIZONS, ["day_ahead"]),
            ): SelectSelector(
                SelectSelectorConfig(options=FORECAST_HORIZON_OPTIONS, multiple=True)
            ),
            vol.Optional(
                CONF_FORECAST_RETENTION_HOURS,
                default=str(
                    d.get(
                        CONF_FORECAST_RETENTION_HOURS,
                        DEFAULT_FORECAST_RETENTION_HOURS,
                    )
                ),
            ): SelectSelector(
                SelectSelectorConfig(options=FORECAST_RETENTION_OPTIONS_SELECT)
            ),
            vol.Optional(
                CONF_ENABLE_ACCOUNTING, default=d.get(CONF_ENABLE_ACCOUNTING, False)
            ): BooleanSelector(),
            vol.Optional(
                CONF_ACCOUNTING_RETENTION_HOURS,
                default=str(
                    d.get(
                        CONF_ACCOUNTING_RETENTION_HOURS,
                        DEFAULT_ACCOUNTING_RETENTION_HOURS,
                    )
                ),
            ): SelectSelector(
                SelectSelectorConfig(options=ACCOUNTING_RETENTION_OPTIONS_SELECT)
            ),
            vol.Optional(
                CONF_IMPORT_METER_ENTITY_ID,
            ): EntitySelector(
                EntitySelectorConfig(domain="sensor", device_class="energy")
            ),
            vol.Optional(
                CONF_EXPORT_METER_ENTITY_ID,
            ): EntitySelector(
                EntitySelectorConfig(domain="sensor", device_class="energy")
            ),
        }
    )


def _validate_meter_entity(hass: HomeAssistant, entity_id: str | None) -> bool:
    """Validate meter entity is an energy sensor with kWh unit."""
    if not entity_id:
        return True
    state = hass.states.get(entity_id)
    if state is None:
        return False
    return (
        state.attributes.get("device_class") == "energy"
        and state.attributes.get("unit_of_measurement") == "kWh"
    )


def _normalize_forecast_horizons(value: Any) -> list[str]:
    """Normalize forecast horizons from selector payload."""
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = [item for item in value if isinstance(item, str)]
    else:
        candidates = []

    normalized: list[str] = []
    for horizon in FORECAST_HORIZONS:
        if horizon in candidates and horizon not in normalized:
            normalized.append(horizon)
    return normalized


def _validate_node_fields(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str]:
    """Validate market node fields and return dict of field -> error key."""
    errors: dict[str, str] = {}

    if user_input.get(CONF_NODE) not in MARKET_NODES:
        errors[CONF_NODE] = "node_invalid"
    if user_input.get(CONF_PRICE_UNIT) not in PRICE_UNITS:
        errors[CONF_PRICE_UNIT] = "price_unit_invalid"

    enable_live = bool(user_input.get(CONF_ENABLE_LIVE_PRICE, False))
    enable_forecast = bool(user_input.get(CONF_ENABLE_FORECAST, False))
    enable_accounting = bool(user_input.get(CONF_ENABLE_ACCOUNTING, False))
    if not (enable_live or enable_forecast or enable_accounting):
        errors["base"] = "no_sensor_type_enabled"

    if enable_forecast:
        if user_input.get(CONF_FORECAST_TYPE) not in FORECAST_TYPES:
            errors[CONF_FORECAST_TYPE] = "forecast_type_invalid"
        horizons = _normalize_forecast_horizons(
            user_input.get(CONF_FORECAST_HORIZONS, [])
        )
        if not horizons:
            errors[CONF_FORECAST_HORIZONS] = "forecast_horizons_empty"

        retention = int(
            user_input.get(
                CONF_FORECAST_RETENTION_HOURS, DEFAULT_FORECAST_RETENTION_HOURS
            )
        )
        if retention not in FORECAST_RETENTION_OPTIONS:
            errors[CONF_FORECAST_RETENTION_HOURS] = "forecast_retention_invalid"

    if enable_accounting:
        retention = int(
            user_input.get(
                CONF_ACCOUNTING_RETENTION_HOURS, DEFAULT_ACCOUNTING_RETENTION_HOURS
            )
        )
        if retention not in ACCOUNTING_RETENTION_OPTIONS:
            errors[CONF_ACCOUNTING_RETENTION_HOURS] = "accounting_retention_invalid"

        import_meter = user_input.get(CONF_IMPORT_METER_ENTITY_ID)
        export_meter = user_input.get(CONF_EXPORT_METER_ENTITY_ID)
        if import_meter and not _validate_meter_entity(hass, import_meter):
            errors[CONF_IMPORT_METER_ENTITY_ID] = "entity_not_energy_import"
        if export_meter and not _validate_meter_entity(hass, export_meter):
            errors[CONF_EXPORT_METER_ENTITY_ID] = "entity_not_energy_export"

    return errors


def _build_node_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Build normalized market node subentry data."""
    data: dict[str, Any] = {
        CONF_NODE: user_input[CONF_NODE],
        CONF_PRICE_UNIT: user_input[CONF_PRICE_UNIT],
        CONF_ENABLE_LIVE_PRICE: bool(user_input.get(CONF_ENABLE_LIVE_PRICE, False)),
        CONF_ENABLE_FORECAST: bool(user_input.get(CONF_ENABLE_FORECAST, False)),
        CONF_ENABLE_ACCOUNTING: bool(user_input.get(CONF_ENABLE_ACCOUNTING, False)),
    }

    if data[CONF_ENABLE_FORECAST]:
        data[CONF_FORECAST_TYPE] = user_input.get(
            CONF_FORECAST_TYPE, "price_responsive"
        )
        data[CONF_FORECAST_HORIZONS] = _normalize_forecast_horizons(
            user_input.get(CONF_FORECAST_HORIZONS, ["day_ahead"])
        )
        data[CONF_FORECAST_RETENTION_HOURS] = int(
            user_input.get(
                CONF_FORECAST_RETENTION_HOURS, DEFAULT_FORECAST_RETENTION_HOURS
            )
        )

    if data[CONF_ENABLE_ACCOUNTING]:
        data[CONF_ACCOUNTING_RETENTION_HOURS] = int(
            user_input.get(
                CONF_ACCOUNTING_RETENTION_HOURS, DEFAULT_ACCOUNTING_RETENTION_HOURS
            )
        )
        data[CONF_IMPORT_METER_ENTITY_ID] = (
            user_input.get(CONF_IMPORT_METER_ENTITY_ID) or None
        )
        data[CONF_EXPORT_METER_ENTITY_ID] = (
            user_input.get(CONF_EXPORT_METER_ENTITY_ID)
            or user_input.get(CONF_IMPORT_METER_ENTITY_ID)
            or None
        )

    return data


def _is_duplicate_market_node(
    entry: config_entries.ConfigEntry,
    node: str,
    exclude_subentry_id: str | None = None,
) -> bool:
    """Return True when another market_node subentry already uses node."""
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE:
            continue
        if exclude_subentry_id and subentry.subentry_id == exclude_subentry_id:
            continue
        if subentry.data.get(CONF_NODE) == node:
            return True
    return False


class ElectricityInfoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for electricityinfo_nz."""

    VERSION = 2

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
        # Keep legacy sensor flow for backward compatibility while 003 is implemented.
        return {
            SUBENTRY_TYPE: MarketNodeSubentryFlow,
            "sensor": SensorSubentryFlowHandler,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step (credential input)."""
        _LOGGER.debug("async_step_user called with user_input: %s", bool(user_input))
        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input.get(CONF_CLIENT_ID):
                errors[CONF_CLIENT_ID] = "client_id_required"
            if not user_input.get(CONF_CLIENT_SECRET):
                errors[CONF_CLIENT_SECRET] = "client_secret_required"

            if not errors:
                self.client_id = user_input[CONF_CLIENT_ID]
                self.client_secret = user_input[CONF_CLIENT_SECRET]
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return await self.async_step_auth_validate()

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
        errors: dict[str, str] = {}

        try:
            session = async_get_clientsession(self.hass)
            client = AsyncMarketPricesClient(
                client_id=self.client_id,
                client_secret=self.client_secret,
                session=session,
            )
            await client.get_schedules()

        except AuthenticationError:
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

        except TransportError, TimeoutError:
            self.validation_attempts += 1

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
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="auth_validate",
                errors=errors,
                last_step=True,
            )

        return self.async_create_entry(
            title="Electricityinfo NZ",
            data={
                CONF_CLIENT_ID: self.client_id,
                CONF_CLIENT_SECRET: self.client_secret,
            },
        )


class MarketNodeSubentryFlow(config_entries.ConfigSubentryFlow):
    """Handle market node subentry flows (add / reconfigure)."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Create a new market node subentry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_node_fields(self.hass, user_input)
            if not errors and _is_duplicate_market_node(
                self._get_entry(), user_input[CONF_NODE]
            ):
                errors[CONF_NODE] = "node_already_configured"
            if not errors:
                return self.async_create_entry(
                    title=_node_title(user_input),
                    data=_build_node_data(user_input),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_node_form_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Edit an existing market node subentry."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_node_fields(self.hass, user_input)
            if not errors and _is_duplicate_market_node(
                self._get_entry(),
                user_input[CONF_NODE],
                exclude_subentry_id=subentry.subentry_id,
            ):
                errors[CONF_NODE] = "node_already_configured"
            if not errors:
                updated_data = _build_node_data(user_input)
                updated_title = _node_title(user_input)
                if (
                    dict(subentry.data) == updated_data
                    and subentry.title == updated_title
                ):
                    return self.async_abort(reason="reconfigure_successful")
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=updated_title,
                    data=updated_data,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_node_form_schema(dict(subentry.data)),
            errors=errors,
        )


class SensorSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Handle legacy sensor subentry flows (add / reconfigure)."""

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
