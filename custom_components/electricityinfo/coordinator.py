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
    ACCOUNTING_BACK_PERIODS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENABLE_ACCOUNTING,
    CONF_ENABLE_FORECAST,
    CONF_ENABLE_LIVE_PRICE,
    CONF_FORECAST_HORIZONS,
    CONF_FORECAST_TYPE,
    CONF_MARKET_TYPE,
    CONF_NODE,
    CONF_PRICE_UNIT,
    CONF_SCHEDULE_TYPE,
    DAY_AHEAD_FORWARD_PERIODS,
    FORECAST_SCHEDULE_MAP,
    INTRADAY_FORWARD_PERIODS,
    MAX_RETRIES,
    NZD_PER_MWH_TO_C_PER_KWH,
    NZD_PER_MWH_TO_NZD_PER_KWH,
    RETRY_INTERVAL_MINUTES,
    SUBENTRY_TYPE,
    UPDATE_INTERVAL_MINUTES,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER: logging.Logger = logging.getLogger(__name__)


def _convert_price(price_nzd_mwh: float | None, price_unit: str) -> float | None:
    """Convert API NZD/MWh price to configured display unit."""
    if price_nzd_mwh is None:
        return None
    if price_unit == "c/kWh":
        return round(price_nzd_mwh * NZD_PER_MWH_TO_C_PER_KWH, 4)
    return round(price_nzd_mwh * NZD_PER_MWH_TO_NZD_PER_KWH, 6)


def _normalized_horizons(raw_horizons: Any) -> set[str]:
    """Return valid forecast horizons from config payload."""
    if isinstance(raw_horizons, str):
        values = [raw_horizons]
    elif isinstance(raw_horizons, list):
        values = [value for value in raw_horizons if isinstance(value, str)]
    else:
        values = []
    return {horizon for horizon in values if horizon in {"day_ahead", "intraday"}}


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

    def _ensure_client(self) -> None:
        """Initialize API client from config entry if needed."""
        if self.client:
            return

        client_id = self.entry.data.get(CONF_CLIENT_ID)
        client_secret = self.entry.data.get(CONF_CLIENT_SECRET)
        if not client_id or not client_secret:
            msg = "Missing OAuth credentials"
            raise ConfigEntryAuthFailed(msg)

        self.client = AsyncMarketPricesClient(
            client_id=client_id,
            client_secret=client_secret,
            session=async_get_clientsession(self.hass),
        )

    async def _fetch_legacy_sensor_data(self, subentry: Any) -> dict[str, Any]:
        """Fetch data for legacy 002 sensor subentry type."""
        sensor_config = dict(subentry.data)
        node = sensor_config.get(CONF_NODE)
        schedule_type = sensor_config.get(CONF_SCHEDULE_TYPE)
        market_type = sensor_config.get(CONF_MARKET_TYPE)
        forward_hours = sensor_config.get("forward_prices_count", 24)
        forward_prices = int(forward_hours) * 2

        schedule_details = await self.client.get_schedule_prices(
            schedule=schedule_type,
            market_type=market_type,
            nodes=[node] if node else None,
            forward=forward_prices,
        )
        return {"prices": schedule_details, "config": sensor_config}

    async def _fetch_market_node_data(self, subentry: Any) -> dict[str, Any]:
        """Fetch data for 003 market_node subentry."""
        config = dict(subentry.data)
        node = config.get(CONF_NODE)
        price_unit = config.get(CONF_PRICE_UNIT, "c/kWh")

        node_data: dict[str, Any] = {
            "node": node,
            "day_ahead": None,
            "intraday": None,
            "accounting": None,
            "config": config,
            "error": None,
        }

        forecast_type = config.get(CONF_FORECAST_TYPE, "price_responsive")
        schedule_map = FORECAST_SCHEDULE_MAP.get(
            forecast_type, FORECAST_SCHEDULE_MAP["price_responsive"]
        )
        horizons = _normalized_horizons(config.get(CONF_FORECAST_HORIZONS, []))

        if config.get(CONF_ENABLE_LIVE_PRICE) or (
            config.get(CONF_ENABLE_FORECAST) and "day_ahead" in horizons
        ):
            day_ahead = await self.client.get_schedule_prices(
                schedule=schedule_map["day_ahead"],
                market_type="E",
                nodes=[node] if node else None,
                forward=DAY_AHEAD_FORWARD_PERIODS,
            )
            if day_ahead:
                for p in day_ahead.prices:
                    p.price = _convert_price(p.price, price_unit)
            node_data["day_ahead"] = day_ahead

        if config.get(CONF_ENABLE_FORECAST) and "intraday" in horizons:
            intraday = await self.client.get_schedule_prices(
                schedule=schedule_map["intraday"],
                market_type="E",
                nodes=[node] if node else None,
                forward=INTRADAY_FORWARD_PERIODS,
            )
            if intraday:
                for p in intraday.prices:
                    p.price = _convert_price(p.price, price_unit)
            node_data["intraday"] = intraday

        if config.get(CONF_ENABLE_ACCOUNTING):
            accounting = await self.client.get_schedule_prices(
                schedule="Interim",
                market_type="E",
                nodes=[node] if node else None,
                back=ACCOUNTING_BACK_PERIODS,
            )
            if accounting:
                for p in accounting.prices:
                    p.price = _convert_price(p.price, price_unit)
            node_data["accounting"] = accounting

        return node_data

    async def _async_update_data(self) -> dict[str, Any]:  # noqa: PLR0912
        """Fetch price data from API."""
        try:
            self._ensure_client()

            subentries = list(self.entry.subentries.values())
            if not subentries:
                return {}

            previous_data = self.data if isinstance(self.data, dict) else {}
            data: dict[str, Any] = {}
            for subentry in subentries:
                subentry_id = subentry.subentry_id
                try:
                    if subentry.subentry_type == "sensor":
                        data[subentry_id] = await self._fetch_legacy_sensor_data(
                            subentry
                        )
                    elif subentry.subentry_type == SUBENTRY_TYPE:
                        data[subentry_id] = await self._fetch_market_node_data(subentry)
                    else:
                        continue
                except AuthenticationError:
                    raise
                except Exception as err:  # noqa: BLE001
                    data[subentry_id] = {
                        "error": str(err),
                        "node": dict(subentry.data).get(CONF_NODE),
                        "config": dict(subentry.data),
                    }

            for subentry in subentries:
                subentry_id = subentry.subentry_id
                if subentry_id in data:
                    continue
                if subentry_id in previous_data:
                    data[subentry_id] = previous_data[subentry_id]

            self._retry_count = 0
            self.update_interval = timedelta(minutes=UPDATE_INTERVAL_MINUTES)

        except AuthenticationError as err:
            msg = "Authentication failed"
            raise ConfigEntryAuthFailed(msg) from err
        except (MarketPricesAPIError, Exception) as err:
            self._retry_count += 1
            if self._retry_count >= MAX_RETRIES:
                self.last_update_success = False

            retry_interval = RETRY_INTERVAL_MINUTES * (2 ** (self._retry_count - 1))
            self.update_interval = timedelta(minutes=retry_interval)
            msg = f"Error fetching prices: {err}"
            raise UpdateFailed(msg) from err
        else:
            return data
