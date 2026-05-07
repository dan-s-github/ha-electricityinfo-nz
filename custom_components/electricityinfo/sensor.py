"""Support for Electricityinfo NZ price sensors."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    RestoreEntity,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.core import HomeAssistant  # noqa: TC002
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback  # noqa: TC002
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_MARKET_TYPE,
    CONF_NODE,
    CONF_SCHEDULE_TYPE,
    DOMAIN,
    NZD_PER_MWH_TO_C_PER_KWH,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry

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

    for subentry in entry.subentries.values():
        if subentry.subentry_type == "sensor":
            entities = [
                PriceSensorEntity(
                    coordinator=coordinator, entry=entry, subentry=subentry, unit=unit
                )
                for unit in ("NZD/MWh", "c/kWh")
            ]
            async_add_entities(entities, config_subentry_id=subentry.subentry_id)


class PriceSensorEntity(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Representation of an electricity price sensor entity."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ElectricityInfoCoordinator,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        unit: str,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._subentry = subentry
        self._sensor_config = dict(subentry.data)
        self._sensor_id = subentry.subentry_id
        self._unit = unit
        self._attr_icon = "mdi:flash"
        self._attr_name = unit

        # Extract configuration
        node = self._sensor_config.get(CONF_NODE, "")
        schedule_type = self._sensor_config.get(CONF_SCHEDULE_TYPE, "")
        market_type = self._sensor_config.get(CONF_MARKET_TYPE, "")

        # Unique ID: one per unit
        unit_suffix = unit.replace("/", "_").lower()
        self._attr_unique_id = (
            f"electricityinfo_nz_{entry.entry_id}_{self._sensor_id}_{unit_suffix}"
        )

        # entity_id: sensor.electricityinfo_nz_{node}_{schedule}_{market}_{unit}
        self.entity_id = (
            f"sensor.electricityinfo_nz"
            f"_{node}_{schedule_type}_{market_type}_{unit_suffix}".lower()
        )

        # Device: one device per subentry, both unit entities share it
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._sensor_id)},
            name=subentry.title,
            manufacturer="Electricity Info NZ",
            entry_type=DeviceEntryType.SERVICE,
        )

        # State storage
        self._native_value: float | None = None
        self._attributes: dict[str, Any] = {}

    @property
    def native_value(self) -> float | None:
        """Return the current price in the configured unit."""
        if self._native_value is None:
            return None
        if self._unit == "c/kWh":
            return round(self._native_value * NZD_PER_MWH_TO_C_PER_KWH, 2)
        return self._native_value

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit

    @property
    def available(self) -> bool:
        """Return True if the sensor is available."""
        if not self.coordinator.last_update_success:
            return False

        if not self.coordinator.data:
            return False

        return (
            self._sensor_id in self.coordinator.data
            and "error" not in self.coordinator.data[self._sensor_id]
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = dict(self._attributes)

        if self._unit == "c/kWh" and "prices_array" in attrs:
            attrs["prices_array"] = [
                round(p * NZD_PER_MWH_TO_C_PER_KWH, 2) for p in attrs["prices_array"]
            ]

        return attrs

    async def async_added_to_hass(self) -> None:
        """Restore state when entity is added to Home Assistant."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            self._native_value = (
                float(last_state.state)
                if last_state.state not in ("unknown", "unavailable")
                else None
            )
            self._attributes = dict(last_state.attributes)
            _LOGGER.debug(
                "Restored state for %s: %s",
                self._sensor_id,
                self._native_value,
            )

        await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data or self._sensor_id not in self.coordinator.data:
            _LOGGER.debug("No data for sensor %s", self._sensor_id)
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        sensor_data = self.coordinator.data[self._sensor_id]

        if "error" in sensor_data:
            _LOGGER.warning(
                "Error for sensor %s: %s",
                self._sensor_id,
                sensor_data.get("error"),
            )
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        schedule_details = sensor_data.get("prices")
        if not schedule_details or not hasattr(schedule_details, "prices"):
            _LOGGER.warning("No schedule details for sensor %s", self._sensor_id)
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        prices = schedule_details.prices
        if not prices:
            _LOGGER.warning(
                "No prices in schedule details for sensor %s", self._sensor_id
            )
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        price_info = prices[0]
        current_price = price_info.price or 0.0

        # Store value in NZD/MWh internally; conversion happens in property getter
        self._native_value = current_price

        self._attributes = {
            "timestamp": price_info.trading_datetime.isoformat()
            if price_info.trading_datetime
            else None,
            "trading_period": price_info.trading_period,
            "node": price_info.node,
            "schedule": price_info.schedule,
            "run_type": price_info.run_type,
        }

        if prices:
            self._attributes["prices_array"] = [
                p.price for p in prices if p.price is not None
            ]

        _LOGGER.debug(
            "Updated sensor %s: price=%s %s",
            self._sensor_id,
            current_price,
            self._unit,
        )

        self.async_write_ha_state()
