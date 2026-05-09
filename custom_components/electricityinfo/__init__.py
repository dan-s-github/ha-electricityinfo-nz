"""The Electricityinfo NZ integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from electricityinfo_nz import AsyncMarketPricesClient
from homeassistant.const import Platform

from .const import DOMAIN
from .coordinator import ElectricityInfoCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

__all__ = ["AsyncMarketPricesClient", "ElectricityInfoCoordinator"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Electricityinfo NZ from a config entry."""
    _LOGGER.debug("Setting up Electricityinfo NZ integration")

    # Create coordinator
    coordinator = ElectricityInfoCoordinator(hass, entry)

    # Store coordinator in hass data before setup
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "title": entry.title,
        "data": dict(entry.data),
        "coordinator": coordinator,
    }

    # Do initial refresh (allow failures gracefully)
    try:
        await coordinator.async_refresh()
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug(
            "Initial refresh failed (expected if no sensors configured): %s", err
        )

    # Setup sensor platform with coordinator
    if PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options changes to reload platforms with new sensors
    async def async_reload_platforms(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Reload sensor platform when options change."""
        _LOGGER.debug("Options updated, reloading sensor platform")
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(async_reload_platforms))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = True
    if PLATFORMS:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
