"""Data update coordinator for Electricityinfo NZ integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from electricityinfo_nz import AsyncMarketPricesClient
from electricityinfo_nz.exceptions import AuthenticationError, MarketPricesAPIError
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    MAX_RETRIES,
    RETRY_INTERVAL_MINUTES,
    UPDATE_INTERVAL_MINUTES,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER: logging.Logger = logging.getLogger(__name__)


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
        self.client: AsyncMarketPricesClient | None = None
        self._retry_count = 0

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch price data from API."""
        try:
            if not self.client:
                # Initialize client from config entry
                client_id = self.entry.data.get(CONF_CLIENT_ID)
                client_secret = self.entry.data.get(CONF_CLIENT_SECRET)

                if not client_id or not client_secret:
                    msg = "Missing OAuth credentials"
                    raise ConfigEntryAuthFailed(msg)  # noqa: TRY301

                self.client = AsyncMarketPricesClient(
                    client_id=client_id,
                    client_secret=client_secret,
                    session=async_get_clientsession(self.hass),
                )

            # Fetch prices for all configured sensor subentries
            subentries = [
                s for s in self.entry.subentries.values() if s.subentry_type == "sensor"
            ]
            if not subentries:
                _LOGGER.debug("No sensors configured")
                return {}

            price_data: dict[str, Any] = {}

            for subentry in subentries:
                sensor_id = subentry.subentry_id
                sensor_config = dict(subentry.data)
                node = sensor_config.get("node")
                schedule_type = sensor_config.get("schedule_type")
                market_type = sensor_config.get("market_type")
                forward_hours = sensor_config.get("forward_prices_count", 24)
                # Each hour has 2 trading periods (30-min intervals)
                forward_prices = forward_hours * 2

                try:
                    schedule_details = await self.client.get_schedule_prices(
                        schedule=schedule_type,
                        market_type=market_type,
                        nodes=[node] if node else None,
                        forward=forward_prices,
                    )

                    if schedule_details:
                        price_data[sensor_id] = {
                            "prices": schedule_details,
                            "config": sensor_config,
                        }
                        _LOGGER.debug(
                            "Updated prices for sensor %s: %s %s",
                            sensor_id,
                            schedule_type,
                            market_type,
                        )
                    else:
                        _LOGGER.warning(
                            "No price data returned for sensor %s"
                            " (node=%s, schedule=%s)",
                            sensor_id,
                            node,
                            schedule_type,
                        )

                except (AuthenticationError, MarketPricesAPIError) as err:
                    _LOGGER.exception(
                        "Error fetching prices for sensor %s",
                        sensor_id,
                    )
                    price_data[sensor_id] = {
                        "error": str(err),
                        "config": sensor_config,
                    }

            # Reset retry counter on successful update
            self._retry_count = 0

        except AuthenticationError as err:
            _LOGGER.exception("Authentication error")
            msg = "Authentication failed"
            raise ConfigEntryAuthFailed(msg) from err
        except (MarketPricesAPIError, Exception) as err:
            _LOGGER.exception("Error fetching price data")

            # Implement exponential backoff
            self._retry_count += 1
            if self._retry_count >= MAX_RETRIES:
                _LOGGER.error(  # noqa: TRY400
                    "Max retries exceeded, marking coordinator as failed"
                )
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

            msg = f"Error fetching prices: {err}"
            raise UpdateFailed(msg) from err

        return price_data
