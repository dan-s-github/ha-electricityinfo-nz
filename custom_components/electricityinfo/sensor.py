"""Support for Electricityinfo NZ sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the example sensor entity."""
    async_add_entities([ElectricityInfoSensor(entry)])


class ElectricityInfoSensor(SensorEntity):
    """Representation of a scaffold sensor entity."""

    _attr_has_entity_name = True
    _attr_name = "Status"
    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize entity."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> int:
        """Return a constant value for scaffold verification."""
        return 1

    @property
    def available(self) -> bool:
        """Return availability based on entry state in hass data."""
        return self._entry.entry_id in self.hass.data.get(DOMAIN, {})
