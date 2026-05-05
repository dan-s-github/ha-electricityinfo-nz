"""The Electricityinfo NZ integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from electricityinfo_nz import MarketPricesClient
from electricityinfo_nz.exceptions import AuthenticationError, MarketPricesAPIError
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DOMAIN,
    MAX_RETRIES,
    RETRY_INTERVAL_MINUTES,
    UPDATE_INTERVAL_MINUTES,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


class ElectricityInfoCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching electricity price data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Electricityinfo NZ Price Coordinator",
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self.entry = entry
        self.client: MarketPricesClient | None = None
        self._retry_count = 0

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch price data from API."""
        try:
            if not self.client:
                # Initialize client from config entry
                client_id = self.entry.data.get(CONF_CLIENT_ID)
                client_secret = self.entry.data.get(CONF_CLIENT_SECRET)

                if not client_id or not client_secret:
                    raise ConfigEntryAuthFailed("Missing OAuth credentials")

                self.client = MarketPricesClient(
                    client_id=client_id,
                    client_secret=client_secret,
                )

            # Fetch prices for all configured sensors
            sensor_configs = self.entry.options.get("sensors", [])
            if not sensor_configs:
                _LOGGER.debug("No sensors configured")
                return {}

            price_data: dict[str, Any] = {}

            for sensor_config in sensor_configs:
                sensor_id = sensor_config.get("id")
                node = sensor_config.get("node")
                schedule_type = sensor_config.get("schedule_type")
                market_type = sensor_config.get("market_type")

                try:
                    # Fetch schedules from API
                    schedules = await self.client.get_schedules(
                        node=node,
                        schedule_type=schedule_type,
                        market_type=market_type,
                    )

                    if schedules:
                        # Store first schedule result for this sensor
                        price_data[sensor_id] = {
                            "prices": schedules,
                            "config": sensor_config,
                        }
                        _LOGGER.debug(
                            "Updated prices for sensor %s: %s",
                            sensor_id,
                            schedules[0] if schedules else "empty",
                        )
                    else:
                        _LOGGER.warning(
                            "No price data returned for sensor %s (node=%s, type=%s)",
                            sensor_id,
                            node,
                            schedule_type,
                        )

                except (AuthenticationError, MarketPricesAPIError) as err:
                    _LOGGER.exception(
                        "Error fetching prices for sensor %s",
                        sensor_id,
                    )
                    # Store error for this sensor but continue with others
                    price_data[sensor_id] = {
                        "error": str(err),
                        "config": sensor_config,
                    }

            # Reset retry counter on successful update
            self._retry_count = 0
            return price_data

        except AuthenticationError as err:
            _LOGGER.exception("Authentication error")
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except (MarketPricesAPIError, Exception) as err:
            _LOGGER.exception("Error fetching price data")

            # Implement exponential backoff
            self._retry_count += 1
            if self._retry_count >= MAX_RETRIES:
                _LOGGER.error("Max retries exceeded, marking coordinator as failed")
                self.last_update_success = False

            # Calculate next retry interval
            retry_interval = RETRY_INTERVAL_MINUTES * (2 ** (self._retry_count - 1))
            self.update_interval = timedelta(minutes=retry_interval)
            _LOGGER.debug(
                "Retry %d/%d, next retry in %d minutes",
                self._retry_count,
                MAX_RETRIES,
                retry_interval,
            )

            raise UpdateFailed(f"Error fetching prices: {err}") from err


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
    except Exception as err:
        _LOGGER.debug(
            "Initial refresh failed (expected if no sensors configured): %s", err
        )

    # Setup sensor platform with coordinator
    if PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = True
    if PLATFORMS:
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
