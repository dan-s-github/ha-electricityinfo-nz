"""Data update coordinator for Electricityinfo NZ integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from electricityinfo_nz import AsyncMarketPricesClient
from electricityinfo_nz.exceptions import AuthenticationError, MarketPricesAPIError
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    ACCOUNTING_BACK_PERIODS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENABLE_ACCOUNTING,
    CONF_ENABLE_FORECAST,
    CONF_ENABLE_LIVE_PRICE,
    CONF_EXPORT_METER_ENTITY_ID,
    CONF_FORECAST_HORIZONS,
    CONF_FORECAST_RETENTION_HOURS,
    CONF_FORECAST_TYPE,
    CONF_IMPORT_METER_ENTITY_ID,
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
NZ_TZ = ZoneInfo("Pacific/Auckland")


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


def _extract_live_price_payload(
    day_ahead: Any,
) -> dict[str, Any] | None:
    """Extract current trade period and future forecast entries from day-ahead data."""
    if not day_ahead or not getattr(day_ahead, "prices", None):
        return None

    sorted_prices = sorted(day_ahead.prices, key=lambda p: p.trading_datetime)
    now = dt_util.utcnow()
    current = None
    for price in sorted_prices:
        if (
            price.trading_datetime
            <= now
            < (price.trading_datetime + timedelta(minutes=30))
        ):
            current = price
            break
    if current is None:
        past = [p for p in sorted_prices if p.trading_datetime <= now]
        current = past[-1] if past else sorted_prices[0]

    return {
        "timestamp": current.trading_datetime.isoformat(),
        "trading_period": current.trading_period,
        "node": current.node,
        "schedule": current.schedule,
        "price": current.price,
    }


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
        self._meter_prev_import: dict[str, float | None] = {}
        self._meter_prev_export: dict[str, float | None] = {}

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

    def _get_client(self) -> AsyncMarketPricesClient:
        """Return an initialized API client."""
        if self.client is None:
            msg = "API client is not initialized"
            raise ConfigEntryAuthFailed(msg)
        return self.client

    async def _fetch_legacy_sensor_data(self, subentry: Any) -> dict[str, Any]:
        """Fetch data for legacy 002 sensor subentry type."""
        client = self._get_client()
        sensor_config = dict(subentry.data)
        node = sensor_config.get(CONF_NODE)
        schedule_type = sensor_config.get(CONF_SCHEDULE_TYPE)
        market_type = sensor_config.get(CONF_MARKET_TYPE)
        forward_hours = sensor_config.get("forward_prices_count", 24)
        forward_prices = int(forward_hours) * 2

        schedule_details = await client.get_schedule_prices(
            schedule=schedule_type,
            market_type=market_type,
            nodes=[node] if node else None,
            forward=forward_prices,
        )
        return {"prices": schedule_details, "config": sensor_config}

    async def _fetch_market_node_data(self, subentry: Any) -> dict[str, Any]:
        """Fetch data for 003 market_node subentry."""
        client = self._get_client()
        config = dict(subentry.data)
        node = config.get(CONF_NODE)
        price_unit = config.get(CONF_PRICE_UNIT, "c/kWh")

        node_data: dict[str, Any] = {
            "node": node,
            "day_ahead": None,
            "intraday": None,
            "accounting": None,
            "live_current": None,
            "settled_price": None,
            "settled_timestamp": None,
            "settled_trading_period": None,
            "import_energy_delta": None,
            "export_energy_delta": None,
            "import_cost_delta": None,
            "export_revenue_delta": None,
            "accounting_date_nzt": None,
            "config": config,
            "error": None,
        }

        forecast_type = config.get(CONF_FORECAST_TYPE, "price_responsive")
        schedule_map = FORECAST_SCHEDULE_MAP.get(
            forecast_type, FORECAST_SCHEDULE_MAP["price_responsive"]
        )
        horizons = _normalized_horizons(config.get(CONF_FORECAST_HORIZONS, []))
        forecast_back = (
            int(config.get(CONF_FORECAST_RETENTION_HOURS, 24)) * 2
            if config.get(CONF_ENABLE_FORECAST)
            else None
        )

        if config.get(CONF_ENABLE_LIVE_PRICE) or (
            config.get(CONF_ENABLE_FORECAST) and "day_ahead" in horizons
        ):
            day_ahead_kwargs: dict[str, Any] = {
                "schedule": schedule_map["day_ahead"],
                "market_type": "E",
                "nodes": [node] if node else None,
                "forward": DAY_AHEAD_FORWARD_PERIODS,
            }
            if forecast_back is not None:
                day_ahead_kwargs["back"] = forecast_back
            _LOGGER.debug(
                "Fetching day-ahead prices for node %s with params: %s",
                node,
                day_ahead_kwargs,
            )
            day_ahead = await client.get_schedule_prices(**day_ahead_kwargs)
            price_count = (
                len(day_ahead.prices)
                if day_ahead and hasattr(day_ahead, "prices")
                else 0
            )
            _LOGGER.debug(
                "Day-ahead prices response for node %s: %s prices returned",
                node,
                price_count,
            )
            if day_ahead:
                for p in day_ahead.prices:
                    p.price = _convert_price(p.price, price_unit)
            node_data["day_ahead"] = day_ahead
            node_data["live_current"] = _extract_live_price_payload(day_ahead)

        if config.get(CONF_ENABLE_FORECAST) and "intraday" in horizons:
            intraday_kwargs: dict[str, Any] = {
                "schedule": schedule_map["intraday"],
                "market_type": "E",
                "nodes": [node] if node else None,
                "forward": INTRADAY_FORWARD_PERIODS,
            }
            if forecast_back is not None:
                intraday_kwargs["back"] = forecast_back
            _LOGGER.debug(
                "Fetching intraday prices for node %s with params: %s",
                node,
                intraday_kwargs,
            )
            intraday = await client.get_schedule_prices(**intraday_kwargs)
            intraday_price_count = (
                len(intraday.prices) if intraday and hasattr(intraday, "prices") else 0
            )
            _LOGGER.debug(
                "Intraday prices response for node %s: %s prices returned",
                node,
                intraday_price_count,
            )
            if intraday:
                for p in intraday.prices:
                    p.price = _convert_price(p.price, price_unit)
            node_data["intraday"] = intraday

        if config.get(CONF_ENABLE_ACCOUNTING):
            accounting_kwargs: dict[str, Any] = {
                "schedule": "Interim",
                "market_type": "E",
                "nodes": [node] if node else None,
                "back": ACCOUNTING_BACK_PERIODS,
            }
            _LOGGER.debug(
                "Fetching accounting prices for node %s with params: %s",
                node,
                accounting_kwargs,
            )
            accounting = await client.get_schedule_prices(**accounting_kwargs)
            accounting_price_count = (
                len(accounting.prices)
                if accounting and hasattr(accounting, "prices")
                else 0
            )
            _LOGGER.debug(
                "Accounting prices response for node %s: %s prices returned",
                node,
                accounting_price_count,
            )
            if accounting:
                for p in accounting.prices:
                    p.price = _convert_price(p.price, price_unit)
            node_data["accounting"] = accounting
            self._populate_accounting_metrics(subentry.subentry_id, config, node_data)

        return node_data

    def _read_energy_meter(self, entity_id: str | None) -> float | None:
        """Read current energy meter value from hass state machine."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None:
            return None
        try:
            return float(state.state)
        except TypeError, ValueError:
            return None

    @staticmethod
    def _compute_delta(previous: float | None, current: float | None) -> float | None:
        """Return current minus previous when both values are available."""
        if previous is None or current is None:
            return None
        return current - previous

    def _populate_accounting_metrics(
        self,
        subentry_id: str,
        config: dict[str, Any],
        node_data: dict[str, Any],
    ) -> None:
        """Populate settled and meter-derived accounting fields for subentry."""
        accounting = node_data.get("accounting")
        if not accounting or not getattr(accounting, "prices", None):
            return

        settled_prices = [p for p in accounting.prices if p.price is not None]
        if not settled_prices:
            return

        latest = max(settled_prices, key=lambda p: p.trading_datetime)
        node_data["settled_price"] = latest.price
        node_data["settled_timestamp"] = latest.trading_datetime
        node_data["settled_trading_period"] = latest.trading_period
        node_data["accounting_date_nzt"] = latest.trading_datetime.astimezone(
            NZ_TZ
        ).date()

        import_meter = config.get(CONF_IMPORT_METER_ENTITY_ID)
        export_meter = config.get(CONF_EXPORT_METER_ENTITY_ID) or import_meter
        bidirectional = bool(
            import_meter and export_meter and import_meter == export_meter
        )

        import_current = self._read_energy_meter(import_meter)
        export_current = self._read_energy_meter(export_meter)

        import_previous = self._meter_prev_import.get(subentry_id)
        export_previous = self._meter_prev_export.get(subentry_id)

        self._meter_prev_import[subentry_id] = import_current
        self._meter_prev_export[subentry_id] = export_current

        import_delta: float | None
        export_delta: float | None
        if import_meter and bidirectional:
            delta = self._compute_delta(import_previous, import_current)
            if delta is None:
                return
            import_delta = max(delta, 0.0)
            export_delta = abs(min(delta, 0.0))
        else:
            import_delta_raw = self._compute_delta(import_previous, import_current)
            export_delta_raw = self._compute_delta(export_previous, export_current)
            import_delta = (
                max(import_delta_raw, 0.0) if import_delta_raw is not None else None
            )
            export_delta = (
                max(export_delta_raw, 0.0) if export_delta_raw is not None else None
            )

        settled_price = node_data.get("settled_price")
        node_data["import_energy_delta"] = import_delta
        node_data["export_energy_delta"] = export_delta
        if settled_price is not None and import_delta is not None:
            node_data["import_cost_delta"] = round(settled_price * import_delta, 6)
        if settled_price is not None and export_delta is not None:
            node_data["export_revenue_delta"] = round(settled_price * export_delta, 6)

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
