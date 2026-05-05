"""Support for Electricityinfo NZ price sensors."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    RestoreEntity,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_MARKET_TYPE,
    CONF_NODE,
    CONF_SCHEDULE_TYPE,
    CONF_SENSOR_ID,
    CONF_SENSORS,
    CONF_UNIT_PREFERENCE,
    DOMAIN,
    NZD_PER_MWH_TO_C_PER_KWH,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from . import ElectricityInfoCoordinator


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up price sensor entities from config entry."""
    coordinator: ElectricityInfoCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    sensors = entry.options.get(CONF_SENSORS, [])
    entities = []

    for sensor_config in sensors:
        entity = PriceSensorEntity(
            coordinator=coordinator,
            entry=entry,
            sensor_config=sensor_config,
        )
        entities.append(entity)
        _LOGGER.debug("Created sensor entity for %s", sensor_config.get(CONF_SENSOR_ID))

    if entities:
        async_add_entities(entities)


class PriceSensorEntity(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Representation of an electricity price sensor entity."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: ElectricityInfoCoordinator,
        entry: ConfigEntry,
        sensor_config: dict[str, Any],
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._sensor_config = sensor_config
        self._attr_icon = "mdi:flash"

        # Extract configuration
        sensor_id = sensor_config.get(CONF_SENSOR_ID, "unknown")
        node = sensor_config.get(CONF_NODE, "").lower()
        schedule_type = sensor_config.get(CONF_SCHEDULE_TYPE, "")
        market_type = sensor_config.get(CONF_MARKET_TYPE, "")
        unit = sensor_config.get(CONF_UNIT_PREFERENCE, "NZD/MWh")

        # Set entity identifiers
        self._attr_unique_id = f"electricityinfo_nz_{entry.entry_id}_{sensor_id}"

        # Format entity_id: sensor.electricityinfo_nz_{node}_{schedule_type}_{market_type}_{unit}
        unit_suffix = unit.replace("/", "_").lower()
        self.entity_id = f"sensor.electricityinfo_nz_{node}_{schedule_type}_{market_type}_{unit_suffix}"

        # Set friendly name
        self._attr_name = (
            f"Electricityinfo NZ {node.upper()} {schedule_type} {market_type} ({unit})"
        )

        # State storage
        self._native_value: float | None = None
        self._attributes: dict[str, Any] = {}

    @property
    def native_value(self) -> float | None:
        """Return the current price in the configured unit."""
        if self._native_value is None:
            return None

        unit_pref = self._sensor_config.get(CONF_UNIT_PREFERENCE, "NZD/MWh")
        if unit_pref == "c/kWh":
            # Convert from NZD/MWh to c/kWh (multiply by 0.1)
            return round(self._native_value * NZD_PER_MWH_TO_C_PER_KWH, 2)
        return self._native_value

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement based on configuration."""
        return self._sensor_config.get(CONF_UNIT_PREFERENCE, "NZD/MWh")

    @property
    def available(self) -> bool:
        """Return True if the sensor is available."""
        if not self.coordinator.last_update_success:
            return False

        sensor_id = self._sensor_config.get(CONF_SENSOR_ID)
        if not sensor_id or not self.coordinator.data:
            return False

        return (
            sensor_id in self.coordinator.data
            and "error" not in self.coordinator.data[sensor_id]
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = dict(self._attributes)

        # Convert prices_array if unit is c/kWh
        unit_pref = self._sensor_config.get(CONF_UNIT_PREFERENCE, "NZD/MWh")
        if unit_pref == "c/kWh" and "prices_array" in attrs:
            attrs["prices_array"] = [
                round(p * NZD_PER_MWH_TO_C_PER_KWH, 2) for p in attrs["prices_array"]
            ]

        return attrs

    async def async_added_to_hass(self) -> None:
        """Restore state when entity is added to Home Assistant."""
        await super().async_added_to_hass()

        # Try to restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            self._native_value = (
                float(last_state.state)
                if last_state.state not in ("unknown", "unavailable")
                else None
            )
            self._attributes = dict(last_state.attributes)
            _LOGGER.debug(
                "Restored state for %s: %s",
                self._sensor_config.get(CONF_SENSOR_ID),
                self._native_value,
            )

        # Request immediate refresh
        await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        sensor_id = self._sensor_config.get(CONF_SENSOR_ID)
        node = self._sensor_config.get(CONF_NODE)
        unit_pref = self._sensor_config.get(CONF_UNIT_PREFERENCE, "NZD/MWh")

        if not self.coordinator.data or sensor_id not in self.coordinator.data:
            _LOGGER.debug("No data for sensor %s", sensor_id)
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        sensor_data = self.coordinator.data[sensor_id]

        # Check for errors
        if "error" in sensor_data:
            _LOGGER.warning(
                "Error for sensor %s: %s",
                sensor_id,
                sensor_data.get("error"),
            )
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        # Extract price data
        prices = sensor_data.get("prices", [])
        if not prices:
            _LOGGER.warning("No prices returned for sensor %s", sensor_id)
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        price_info = prices[0]
        current_price = price_info.get("price_value", 0.0)

        # Store value in NZD/MWh internally, conversion happens in property getter
        self._native_value = current_price

        # Build attributes
        self._attributes = {
            "timestamp": price_info.get("timestamp"),
            "confidence_level": price_info.get("confidence_level"),
            "forecast_period": price_info.get("forecast_period"),
            "market_type": price_info.get("market_type"),
            "node": price_info.get("node"),
            "schedule_type": price_info.get("schedule_type"),
        }

        # Add prices array (stored in NZD/MWh internally)
        if "prices" in price_info:
            self._attributes["prices_array"] = price_info.get("prices", [])

        _LOGGER.debug(
            "Updated sensor %s: price=%s %s",
            sensor_id,
            current_price,
            unit_pref,
        )

        self.async_write_ha_state()
