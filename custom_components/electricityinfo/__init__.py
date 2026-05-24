"""The Electricityinfo NZ integration."""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import TYPE_CHECKING

from electricityinfo_nz import AsyncMarketPricesClient
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import Platform

from .const import (
    CONF_ACCOUNTING_RETENTION_HOURS,
    CONF_ENABLE_ACCOUNTING,
    CONF_ENABLE_FORECAST,
    CONF_ENABLE_LIVE_PRICE,
    CONF_FORECAST_HORIZONS,
    CONF_FORECAST_RETENTION_HOURS,
    CONF_FORECAST_TYPE,
    CONF_NODE,
    CONF_PRICE_UNIT,
    DEFAULT_ACCOUNTING_RETENTION_HOURS,
    DEFAULT_FORECAST_RETENTION_HOURS,
    DOMAIN,
    SUBENTRY_TYPE,
)
from .coordinator import ElectricityInfoCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

__all__ = ["AsyncMarketPricesClient", "ElectricityInfoCoordinator"]
MIGRATION_VERSION = 2


def _migrate_legacy_schedule(
    schedule_type: str | None,
) -> tuple[bool, str | None, list[str]]:
    """Map 002 schedule type to 003 forecast settings."""
    if schedule_type == "PRSL":
        return True, "price_responsive", ["day_ahead"]
    if schedule_type == "PRSS":
        return True, "price_responsive", ["intraday"]
    if schedule_type == "NRSL":
        return True, "non_responsive", ["day_ahead"]
    if schedule_type == "NRSS":
        return True, "non_responsive", ["intraday"]
    return False, None, []


def _build_migrated_node_data(legacy_data: dict) -> dict:
    """Build 003 market-node data from legacy sensor subentry data."""
    enable_forecast, forecast_type, horizons = _migrate_legacy_schedule(
        legacy_data.get("schedule_type")
    )
    migrated: dict = {
        CONF_NODE: legacy_data.get("node"),
        CONF_PRICE_UNIT: "NZD/kWh",
        CONF_ENABLE_LIVE_PRICE: True,
        CONF_ENABLE_FORECAST: enable_forecast,
        CONF_ENABLE_ACCOUNTING: False,
        CONF_FORECAST_RETENTION_HOURS: DEFAULT_FORECAST_RETENTION_HOURS,
        CONF_ACCOUNTING_RETENTION_HOURS: DEFAULT_ACCOUNTING_RETENTION_HOURS,
    }
    if enable_forecast:
        migrated[CONF_FORECAST_TYPE] = forecast_type
        migrated[CONF_FORECAST_HORIZONS] = horizons
    return migrated


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to version 2."""
    if entry.version >= MIGRATION_VERSION:
        return True

    seen_nodes: set[str] = set()
    subentries_to_remove: list[str] = []

    for subentry_id, subentry in list(entry.subentries.items()):
        if subentry.subentry_type != "sensor":
            continue
        subentries_to_remove.append(subentry_id)
        node = subentry.data.get("node")
        if not node:
            _LOGGER.warning(
                "Skipping legacy sensor subentry without node: %s", subentry_id
            )
            continue
        if node in seen_nodes:
            _LOGGER.warning(
                "Migration dedupe for market_node=%s; keep first, skip later entries",
                node,
            )
            continue
        seen_nodes.add(node)
        migrated_data = _build_migrated_node_data(dict(subentry.data))
        migrated_subentry = ConfigSubentry(
            data=MappingProxyType(migrated_data),
            subentry_type=SUBENTRY_TYPE,
            title=f"{node} [{migrated_data[CONF_PRICE_UNIT]}]",
            unique_id=None,
        )
        hass.config_entries.async_add_subentry(entry, migrated_subentry)
        _LOGGER.warning(
            "Entity IDs changed during migration for market_node=%s",
            node,
        )

    for subentry_id in subentries_to_remove:
        hass.config_entries.async_remove_subentry(entry, subentry_id)

    hass.config_entries.async_update_entry(entry, version=MIGRATION_VERSION)
    _LOGGER.info("Migrated config entry to version 2")
    return True


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
