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
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
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
    CONF_IMPORT_METER_ENTITY_ID,
    CONF_NODE,
    CONF_PRICE_UNIT,
    DAY_AHEAD_FORWARD_PERIODS,
    DOMAIN,
    FORECAST_SCHEDULE_MAP,
    INTRADAY_FORWARD_PERIODS,
    METER_READING_MAX_AGE_MINUTES,
    METER_STORE_VERSION,
    NZD_PER_MWH_TO_C_PER_KWH,
    NZD_PER_MWH_TO_NZD_PER_KWH,
    RETRY_INTERVAL_MINUTES,
    RTD_BACK_PERIODS,
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


def meter_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    """Return the store holding the last meter readings for a config entry."""
    return Store(hass, METER_STORE_VERSION, f"{DOMAIN}.{entry_id}.meter_readings")


def _normalized_horizons(raw_horizons: Any) -> set[str]:
    """Return valid forecast horizons from config payload."""
    if isinstance(raw_horizons, str):
        values = [raw_horizons]
    elif isinstance(raw_horizons, list):
        values = [value for value in raw_horizons if isinstance(value, str)]
    else:
        values = []
    return {horizon for horizon in values if horizon in {"day_ahead", "intraday"}}


def _schedule_requests(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the price schedule requests for a market node, keyed by feature."""
    requests: dict[str, dict[str, Any]] = {}
    if config.get(CONF_ENABLE_LIVE_PRICE):
        requests["rtd"] = {"schedule": "RTD", "back": RTD_BACK_PERIODS}

    if config.get(CONF_ENABLE_FORECAST):
        schedule_map = FORECAST_SCHEDULE_MAP.get(
            config.get(CONF_FORECAST_TYPE, "price_responsive"),
            FORECAST_SCHEDULE_MAP["price_responsive"],
        )
        forecast_back = int(config.get(CONF_FORECAST_RETENTION_HOURS, 24)) * 2
        horizons = _normalized_horizons(config.get(CONF_FORECAST_HORIZONS, []))
        forward_periods = {
            "day_ahead": DAY_AHEAD_FORWARD_PERIODS,
            "intraday": INTRADAY_FORWARD_PERIODS,
        }
        for horizon, forward in forward_periods.items():
            if horizon in horizons:
                requests[horizon] = {
                    "schedule": schedule_map[horizon],
                    "forward": forward,
                    "back": forecast_back,
                }

    if config.get(CONF_ENABLE_ACCOUNTING):
        requests["accounting"] = {
            "schedule": "Interim",
            "back": int(config.get(CONF_ACCOUNTING_RETENTION_HOURS, 24)) * 2,
        }
    return requests


def _extract_live_price_payload(
    rtd: Any,
) -> dict[str, Any] | None:
    """Extract the most recently dispatched RTD period from RTD data."""
    if not rtd or not getattr(rtd, "prices", None):
        return None

    now = dt_util.utcnow()
    past = [p for p in rtd.prices if p.trading_datetime <= now]
    current = max(past, key=lambda p: p.trading_datetime) if past else None
    if current is None:
        return None

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
        self._meter_store = meter_store(hass, entry.entry_id)
        self._meter_readings: dict[str, dict[str, Any]] = {}

    async def async_load_meter_readings(self) -> None:
        """Restore recent meter readings saved before a restart or reload."""
        stored = await self._meter_store.async_load() or {}
        now = dt_util.utcnow()
        max_age = timedelta(minutes=METER_READING_MAX_AGE_MINUTES)
        for subentry in self.entry.subentries.values():
            reading = stored.get(subentry.subentry_id)
            if not isinstance(reading, dict):
                continue
            saved_at = dt_util.parse_datetime(str(reading.get("saved_at")))
            if saved_at is None or now - saved_at > max_age:
                continue
            config = dict(subentry.data)
            # Only reuse a reading taken from the meter still configured.
            if reading.get("import_entity") == config.get(CONF_IMPORT_METER_ENTITY_ID):
                self._meter_prev_import[subentry.subentry_id] = reading.get("import")
            if reading.get("export_entity") == config.get(CONF_EXPORT_METER_ENTITY_ID):
                self._meter_prev_export[subentry.subentry_id] = reading.get("export")

    async def async_save_meter_readings(self) -> None:
        """Write the latest meter readings to storage immediately."""
        await self._meter_store.async_save(self._meter_readings)

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

    @staticmethod
    async def _fetch_schedule(
        client: AsyncMarketPricesClient,
        node: str | None,
        price_unit: str,
        key: str,
        params: dict[str, Any],
    ) -> Any:
        """Fetch one price schedule for a node, converted to the display unit."""
        kwargs = {"market_type": "E", "nodes": [node] if node else None, **params}
        _LOGGER.debug("Fetching %s prices for node %s: %s", key, node, kwargs)
        schedule = await client.get_schedule_prices(**kwargs)
        if schedule:
            for p in schedule.prices:
                p.price = _convert_price(p.price, price_unit)
        _LOGGER.debug(
            "%s response for node %s: %s prices returned",
            key,
            node,
            len(getattr(schedule, "prices", None) or []),
        )
        return schedule

    async def _fetch_market_node_data(self, subentry: Any) -> dict[str, Any]:
        """Fetch data for 003 market_node subentry."""
        client = self._get_client()
        config = dict(subentry.data)
        node = config.get(CONF_NODE)
        price_unit = config.get(CONF_PRICE_UNIT, "c/kWh")

        node_data: dict[str, Any] = {
            "node": node,
            "rtd": None,
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

        # Each schedule is fetched independently so one failing endpoint only
        # blanks its own sensors; the node errors only if every fetch failed.
        requests = _schedule_requests(config)
        errors: list[Exception] = []
        for key, params in requests.items():
            try:
                node_data[key] = await self._fetch_schedule(
                    client, node, price_unit, key, params
                )
            except AuthenticationError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("%s fetch failed for node %s: %s", key, node, err)
                errors.append(err)

        if errors and len(errors) == len(requests):
            raise errors[-1]

        if node_data["rtd"] is not None:
            node_data["live_current"] = _extract_live_price_payload(node_data["rtd"])
        if node_data["accounting"] is not None:
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

        now = dt_util.utcnow()
        sorted_settled = sorted(settled_prices, key=lambda p: p.trading_datetime)
        current = next(
            (
                p
                for p in sorted_settled
                if p.trading_datetime
                <= now
                < p.trading_datetime + timedelta(minutes=30)
            ),
            None,
        )
        if current is not None:
            selected = current
        else:
            past = [p for p in sorted_settled if p.trading_datetime <= now]
            if not past:
                return  # No settled periods; accounting sensors remain unavailable
            selected = past[-1]

        node_data["settled_price"] = selected.price
        node_data["settled_timestamp"] = selected.trading_datetime
        node_data["settled_trading_period"] = selected.trading_period
        node_data["accounting_date_nzt"] = selected.trading_datetime.astimezone(
            NZ_TZ
        ).date()

        import_meter = config.get(CONF_IMPORT_METER_ENTITY_ID)
        export_meter = config.get(CONF_EXPORT_METER_ENTITY_ID)

        if import_meter and export_meter and import_meter == export_meter:
            _LOGGER.warning(
                "Subentry %s: import and export meter are the same entity (%s). "
                "Accounting skipped until configuration is corrected.",
                subentry_id,
                import_meter,
            )
            return

        import_current = self._read_energy_meter(import_meter)
        export_current = self._read_energy_meter(export_meter)

        import_previous = self._meter_prev_import.get(subentry_id)
        export_previous = self._meter_prev_export.get(subentry_id)

        self._meter_prev_import[subentry_id] = import_current
        self._meter_prev_export[subentry_id] = export_current
        self._meter_readings[subentry_id] = {
            "saved_at": dt_util.utcnow().isoformat(),
            "import_entity": import_meter,
            "import": import_current,
            "export_entity": export_meter,
            "export": export_current,
        }
        self._meter_store.async_delay_save(lambda: self._meter_readings, 0)

        import_delta_raw = self._compute_delta(import_previous, import_current)
        export_delta_raw = self._compute_delta(export_previous, export_current)
        import_delta: float | None = (
            max(import_delta_raw, 0.0) if import_delta_raw is not None else None
        )
        export_delta: float | None = (
            max(export_delta_raw, 0.0) if export_delta_raw is not None else None
        )

        settled_price = node_data.get("settled_price")
        node_data["import_energy_delta"] = import_delta
        node_data["export_energy_delta"] = export_delta
        if settled_price is not None and import_delta is not None:
            node_data["import_cost_delta"] = round(settled_price * import_delta, 6)
        if settled_price is not None and export_delta is not None:
            node_data["export_revenue_delta"] = round(settled_price * export_delta, 6)

    async def _async_update_data(self) -> dict[str, Any]:
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
                    if subentry.subentry_type == SUBENTRY_TYPE:
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
            # Back off exponentially, but never poll less often than normal.
            retry_interval = min(
                RETRY_INTERVAL_MINUTES * (2 ** (self._retry_count - 1)),
                UPDATE_INTERVAL_MINUTES,
            )
            self.update_interval = timedelta(minutes=retry_interval)
            msg = f"Error fetching prices: {err}"
            raise UpdateFailed(msg) from err
        else:
            return data
