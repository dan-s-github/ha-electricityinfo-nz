"""Support for Electricityinfo NZ price sensors."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import (
    RestoreEntity,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant  # noqa: TC002
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,  # noqa: TC002
)
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ACCOUNTING_RETENTION_HOURS,
    CONF_ENABLE_ACCOUNTING,
    CONF_ENABLE_FORECAST,
    CONF_ENABLE_LIVE_PRICE,
    CONF_EXPORT_METER_ENTITY_ID,
    CONF_FORECAST_HORIZONS,
    CONF_FORECAST_RETENTION_HOURS,
    CONF_IMPORT_METER_ENTITY_ID,
    CONF_NODE,
    CONF_PRICE_UNIT,
    DOMAIN,
    SUBENTRY_TYPE,
    UPDATE_INTERVAL_MINUTES,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry

    from . import ElectricityInfoCoordinator


_LOGGER = logging.getLogger(__name__)
NZ_TZ = ZoneInfo("Pacific/Auckland")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up price sensor entities from config entry."""
    coordinator: ElectricityInfoCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    expected_market_unique_ids: set[str] = set()

    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE:
            continue
        config = dict(subentry.data)
        market_entities: list[MarketNodeSensorBase] = []
        _LOGGER.debug(
            "Setting up market_node sensors for %s: "
            "enable_live_price=%s, enable_forecast=%s, enable_accounting=%s",
            subentry.title,
            config.get(CONF_ENABLE_LIVE_PRICE),
            config.get(CONF_ENABLE_FORECAST),
            config.get(CONF_ENABLE_ACCOUNTING),
        )
        if config.get(CONF_ENABLE_LIVE_PRICE):
            market_entities.append(
                LivePriceSensor(
                    coordinator=coordinator,
                    entry=entry,
                    subentry=subentry,
                )
            )
        if config.get(CONF_ENABLE_FORECAST):
            horizons = set(config.get(CONF_FORECAST_HORIZONS, []))
            _LOGGER.debug(
                "Forecast enabled for %s with horizons: %s",
                subentry.title,
                horizons,
            )
            if "day_ahead" in horizons:
                market_entities.append(
                    DayAheadForecastSensor(
                        coordinator=coordinator,
                        entry=entry,
                        subentry=subentry,
                    )
                )
            if "intraday" in horizons:
                market_entities.append(
                    IntradayForecastSensor(
                        coordinator=coordinator,
                        entry=entry,
                        subentry=subentry,
                    )
                )
        if config.get(CONF_ENABLE_ACCOUNTING):
            market_entities.append(
                SettledPriceSensor(
                    coordinator=coordinator,
                    entry=entry,
                    subentry=subentry,
                )
            )
            import_meter = config.get(CONF_IMPORT_METER_ENTITY_ID)
            export_meter = config.get(CONF_EXPORT_METER_ENTITY_ID) or import_meter
            if import_meter:
                market_entities.append(
                    ImportCostSensor(
                        coordinator=coordinator,
                        entry=entry,
                        subentry=subentry,
                    )
                )
                market_entities.append(
                    DailyImportCostSensor(
                        coordinator=coordinator,
                        entry=entry,
                        subentry=subentry,
                    )
                )
            if export_meter:
                market_entities.append(
                    ExportRevenueSensor(
                        coordinator=coordinator,
                        entry=entry,
                        subentry=subentry,
                    )
                )
                market_entities.append(
                    DailyExportRevenueSensor(
                        coordinator=coordinator,
                        entry=entry,
                        subentry=subentry,
                    )
                )
        if market_entities:
            expected_market_unique_ids.update(
                entity.unique_id
                for entity in market_entities
                if entity.unique_id is not None
            )
            _LOGGER.debug(
                "Adding %s entities for %s",
                len(market_entities),
                subentry.title,
            )
            async_add_entities(market_entities, config_subentry_id=subentry.subentry_id)
        else:
            _LOGGER.debug(
                "No entities to add for %s (all features disabled)",
                subentry.title,
            )

    _remove_stale_market_node_entities(hass, entry.entry_id, expected_market_unique_ids)


def _remove_stale_market_node_entities(
    hass: HomeAssistant,
    entry_id: str,
    expected_unique_ids: set[str],
) -> None:
    """Remove stale market-node entities no longer enabled in config."""
    registry = async_get(hass)
    unique_prefix = f"electricityinfo_{entry_id}_"
    for entity_entry in async_entries_for_config_entry(registry, entry_id):
        unique_id = entity_entry.unique_id
        if not unique_id or not unique_id.startswith(unique_prefix):
            continue
        if unique_id in expected_unique_ids:
            continue
        registry.async_remove(entity_entry.entity_id)


class MarketNodeSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for market node sensors."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class: SensorStateClass | None = None
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ElectricityInfoCoordinator,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        sensor_type: str,
        sensor_name: str,
    ) -> None:
        """Initialize market node base sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._subentry = subentry
        self._subentry_id = subentry.subentry_id
        self._config = dict(subentry.data)
        self._node = self._config.get(CONF_NODE, "unknown")
        self._attr_name = sensor_name
        self._attr_unique_id = (
            f"electricityinfo_{entry.entry_id}_{self._subentry_id}_{sensor_type}"
        )
        self._attr_suggested_object_id = f"{self._node.lower()}_{sensor_type}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._subentry_id)},
            name=subentry.title,
            manufacturer="Electricity Info NZ",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._native_value: float | None = None
        self._attributes: dict[str, Any] = {}

    @property
    def native_unit_of_measurement(self) -> str:
        """Return configured native unit."""
        return str(self._config.get(CONF_PRICE_UNIT, "c/kWh"))

    @property
    def native_value(self) -> float | None:
        """Return native state value."""
        return self._native_value

    @property
    def available(self) -> bool:
        """Return whether entity has usable data."""
        return (
            self.coordinator.last_update_success
            and self._native_value is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return sensor attributes."""
        return dict(self._attributes)


class LivePriceSensor(MarketNodeSensorBase, RestoreEntity):
    """Live price sensor for market node."""

    def __init__(
        self,
        coordinator: ElectricityInfoCoordinator,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize live price sensor."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            subentry=subentry,
            sensor_type="live_price",
            sensor_name="Live Price",
        )

    async def async_added_to_hass(self) -> None:
        """Restore live sensor state with staleness guard."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            timestamp_str = last_state.attributes.get("timestamp")
            if timestamp_str:
                restored_time = dt_util.parse_datetime(timestamp_str)
                if restored_time and dt_util.utcnow() - restored_time > timedelta(
                    minutes=UPDATE_INTERVAL_MINUTES
                ):
                    await self.coordinator.async_request_refresh()
                    return
            if last_state.state not in ("unknown", "unavailable"):
                self._native_value = float(last_state.state)
                self._attributes = dict(last_state.attributes)
        await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update for live price."""
        node_data = (self.coordinator.data or {}).get(self._subentry_id)
        if not node_data or node_data.get("error"):
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        live_current = node_data.get("live_current")
        if live_current:
            self._native_value = live_current.get("price")
            self._attributes = {
                "timestamp": live_current.get("timestamp"),
                "trading_period": live_current.get("trading_period"),
                "node": live_current.get("node"),
                "schedule": live_current.get("schedule"),
            }
            self.async_write_ha_state()
            return

        day_ahead = node_data.get("day_ahead")
        if not day_ahead or not getattr(day_ahead, "prices", None):
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        now = dt_util.utcnow()
        sorted_prices = sorted(day_ahead.prices, key=lambda p: p.trading_datetime)
        current = None
        for price in sorted_prices:
            if (
                price.trading_datetime
                <= now
                < price.trading_datetime + timedelta(minutes=30)
            ):
                current = price
                break
        if current is None:
            past = [p for p in sorted_prices if p.trading_datetime <= now]
            current = past[-1] if past else sorted_prices[0]

        self._native_value = current.price
        self._attributes = {
            "timestamp": current.trading_datetime.isoformat(),
            "trading_period": current.trading_period,
            "node": current.node,
            "schedule": current.schedule,
        }
        self.async_write_ha_state()


class ForecastSensorBase(MarketNodeSensorBase):
    """Base class for forecast sensors."""

    _schedule_key: str = ""

    async def async_added_to_hass(self) -> None:
        """Register coordinator listener when added to hass."""
        _LOGGER.debug(
            "%s: async_added_to_hass called, coordinator.data=%s",
            self._attr_name,
            type(self.coordinator.data),
        )
        await super().async_added_to_hass()
        _LOGGER.debug(
            "%s: super().async_added_to_hass() completed, "
            "calling _handle_coordinator_update manually",
            self._attr_name,
        )
        # Manually call to ensure state is set
        self._handle_coordinator_update()

    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update for forecast sensors."""
        _LOGGER.debug("%s: Handling coordinator update", self._attr_name)
        node_data = (self.coordinator.data or {}).get(self._subentry_id)
        if not node_data or node_data.get("error"):
            _LOGGER.debug(
                "%s: No node data or error in coordinator data", self._attr_name
            )
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        schedule_details = node_data.get(self._schedule_key)
        if not schedule_details or not getattr(schedule_details, "prices", None):
            _LOGGER.debug(
                "%s: No schedule details for %s",
                self._attr_name,
                self._schedule_key,
            )
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        now = dt_util.utcnow()
        sorted_prices = sorted(
            schedule_details.prices,
            key=lambda p: (p.trading_datetime, p.trading_period),
        )
        priced_points = [p for p in sorted_prices if p.price is not None]
        current = next(
            (
                p
                for p in priced_points
                if p.trading_datetime
                <= now
                < p.trading_datetime + timedelta(minutes=30)
            ),
            None,
        )
        future = sorted(
            (
                p
                for p in priced_points
                if p.trading_datetime > now and p.price is not None
            ),
            key=lambda p: (p.trading_datetime, p.trading_period),
        )
        retention_periods = int(self._config.get(CONF_FORECAST_RETENTION_HOURS, 24)) * 2
        # history = all periods that have started (elapsed + currently active)
        history = sorted(
            (p for p in priced_points if p.trading_datetime <= now),
            key=lambda p: (p.trading_datetime, p.trading_period),
        )[-retention_periods:]

        # Count prices by state for debugging
        with_price = [p for p in sorted_prices if p.price is not None]
        no_price = [p for p in sorted_prices if p.price is None]

        _LOGGER.debug(
            "%s: Processed %s total prices: %s with price, %s without price. "
            "Current period found: %s. Future: %s, History: %s. "
            "Now=%s, First price at %s, Last price at %s",
            self._attr_name,
            len(sorted_prices),
            len(with_price),
            len(no_price),
            current is not None,
            len(future),
            len(history),
            now.isoformat(),
            sorted_prices[0].trading_datetime.isoformat() if sorted_prices else "N/A",
            sorted_prices[-1].trading_datetime.isoformat() if sorted_prices else "N/A",
        )

        if current is not None:
            self._native_value = current.price
        else:
            self._native_value = future[0].price if future else None
        self._attributes = {
            "history": [
                {
                    "period_start": p.trading_datetime.isoformat(),
                    "trading_period": p.trading_period,
                    "price": p.price,
                }
                for p in history
            ],
            "forecast": [
                {
                    "period_start": p.trading_datetime.isoformat(),
                    "trading_period": p.trading_period,
                    "price": p.price,
                }
                for p in future
            ],
        }
        self.async_write_ha_state()


class DayAheadForecastSensor(ForecastSensorBase):
    """Day-ahead forecast sensor for market node."""

    _schedule_key = "day_ahead"

    def __init__(
        self,
        coordinator: ElectricityInfoCoordinator,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize day-ahead forecast sensor."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            subentry=subentry,
            sensor_type="day_ahead_forecast",
            sensor_name="Day Ahead Forecast",
        )


class IntradayForecastSensor(ForecastSensorBase):
    """Intraday forecast sensor for market node."""

    _schedule_key = "intraday"

    def __init__(
        self,
        coordinator: ElectricityInfoCoordinator,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize intraday forecast sensor."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            subentry=subentry,
            sensor_type="intraday_forecast",
            sensor_name="Intraday Forecast",
        )


class SettledPriceSensor(MarketNodeSensorBase):
    """Settled accounting price sensor."""

    def __init__(
        self,
        coordinator: ElectricityInfoCoordinator,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize settled price sensor."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            subentry=subentry,
            sensor_type="settled_price",
            sensor_name="Settled Price",
        )

    async def async_added_to_hass(self) -> None:
        """Register with coordinator; starts unavailable until first poll."""
        await super().async_added_to_hass()

    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update for settled price."""
        node_data = (self.coordinator.data or {}).get(self._subentry_id)
        if not node_data or node_data.get("error"):
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        accounting = node_data.get("accounting")
        if not accounting or not getattr(accounting, "prices", None):
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        settled_prices = [p for p in accounting.prices if p.price is not None]
        if not settled_prices:
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
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
            selected = past[-1] if past else sorted_settled[0]
        retention = int(self._config.get(CONF_ACCOUNTING_RETENTION_HOURS, 24)) * 2
        history = [
            p
            for p in sorted_settled
            if p.trading_datetime + timedelta(minutes=30) <= now
        ][-retention:]
        self._native_value = selected.price
        self._attributes = {
            "trading_period": selected.trading_period,
            "timestamp": selected.trading_datetime.isoformat(),
            "node": selected.node,
            "history": [
                {
                    "period_start": price.trading_datetime.isoformat(),
                    "trading_period": price.trading_period,
                    "price": price.price,
                }
                for price in history
            ],
        }
        self.async_write_ha_state()


class AccountingDeltaSensorBase(MarketNodeSensorBase):
    """Base class for per-period accounting delta sensors."""

    _value_key: str = ""
    _energy_key: str = ""
    _meter_key: str = ""

    @property
    def native_unit_of_measurement(self) -> str:
        """Return currency unit based on configured price unit."""
        return "c" if self._config.get(CONF_PRICE_UNIT) == "c/kWh" else "NZD"

    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update for per-period accounting values."""
        node_data = (self.coordinator.data or {}).get(self._subentry_id)
        if not node_data or node_data.get("error"):
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        value = node_data.get(self._value_key)
        energy = node_data.get(self._energy_key)
        settled_price = node_data.get("settled_price")
        settled_timestamp: datetime | None = node_data.get("settled_timestamp")
        settled_period = node_data.get("settled_trading_period")
        meter_entity = self._config.get(self._meter_key)

        if value is None or energy is None or settled_price is None:
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        self._native_value = value
        self._attributes = {
            "settled_price": settled_price,
            "energy_kwh": energy,
            self._meter_key: meter_entity,
            "trading_period": settled_period,
            "timestamp": settled_timestamp.isoformat() if settled_timestamp else None,
        }
        self.async_write_ha_state()


class ImportCostSensor(AccountingDeltaSensorBase):
    """Import cost delta sensor."""

    _value_key = "import_cost_delta"
    _energy_key = "import_energy_delta"
    _meter_key = CONF_IMPORT_METER_ENTITY_ID

    def __init__(
        self,
        coordinator: ElectricityInfoCoordinator,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize import cost sensor."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            subentry=subentry,
            sensor_type="import_cost",
            sensor_name="Import Cost",
        )


class ExportRevenueSensor(AccountingDeltaSensorBase):
    """Export revenue delta sensor."""

    _value_key = "export_revenue_delta"
    _energy_key = "export_energy_delta"
    _meter_key = CONF_EXPORT_METER_ENTITY_ID

    def __init__(
        self,
        coordinator: ElectricityInfoCoordinator,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize export revenue sensor."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            subentry=subentry,
            sensor_type="export_revenue",
            sensor_name="Export Revenue",
        )


class DailyAccountingSensorBase(AccountingDeltaSensorBase, RestoreEntity):
    """Base class for daily accumulated accounting sensors."""

    _attr_state_class = SensorStateClass.TOTAL
    _daily_value_key: str = ""
    _daily_meter_key: str = ""

    def __init__(
        self,
        coordinator: ElectricityInfoCoordinator,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        sensor_type: str,
        sensor_name: str,
    ) -> None:
        """Initialize daily accounting sensor."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            subentry=subentry,
            sensor_type=sensor_type,
            sensor_name=sensor_name,
        )
        self._accumulated_total: float = 0.0
        self._accumulation_date: date | None = None

    async def async_added_to_hass(self) -> None:
        """Restore previously accumulated total and date."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            self._accumulated_total = float(last_state.state)
            date_str = last_state.attributes.get("accumulation_date")
            if isinstance(date_str, str):
                parsed = dt_util.parse_date(date_str)
                self._accumulation_date = parsed

        today_nzt = dt_util.utcnow().astimezone(NZ_TZ).date()
        if self._accumulation_date and self._accumulation_date < today_nzt:
            self._accumulated_total = 0.0
            self._accumulation_date = today_nzt
        elif self._accumulation_date is None:
            self._accumulation_date = today_nzt
        self._native_value = self._accumulated_total
        self._attributes = {
            "accumulation_date": self._accumulation_date.isoformat(),
            self._daily_meter_key: self._config.get(self._daily_meter_key),
        }

    def _handle_coordinator_update(self) -> None:
        """Update running total from coordinator accounting deltas."""
        node_data = (self.coordinator.data or {}).get(self._subentry_id)
        if not node_data or node_data.get("error"):
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        accounting_date: date | None = node_data.get("accounting_date_nzt")
        if accounting_date and accounting_date != self._accumulation_date:
            self._accumulated_total = 0.0
            self._accumulation_date = accounting_date

        delta_value = node_data.get(self._daily_value_key)
        if delta_value is not None:
            self._accumulated_total += delta_value

        if self._accumulation_date is None:
            self._accumulation_date = dt_util.utcnow().astimezone(NZ_TZ).date()

        self._native_value = self._accumulated_total
        self._attributes = {
            "accumulation_date": self._accumulation_date.isoformat(),
            self._daily_meter_key: self._config.get(self._daily_meter_key),
        }
        self.async_write_ha_state()


class DailyImportCostSensor(DailyAccountingSensorBase):
    """Daily accumulated import cost sensor."""

    _daily_value_key = "import_cost_delta"
    _daily_meter_key = CONF_IMPORT_METER_ENTITY_ID

    def __init__(
        self,
        coordinator: ElectricityInfoCoordinator,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize daily import cost sensor."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            subentry=subentry,
            sensor_type="daily_import_cost",
            sensor_name="Daily Import Cost",
        )


class DailyExportRevenueSensor(DailyAccountingSensorBase):
    """Daily accumulated export revenue sensor."""

    _daily_value_key = "export_revenue_delta"
    _daily_meter_key = CONF_EXPORT_METER_ENTITY_ID

    def __init__(
        self,
        coordinator: ElectricityInfoCoordinator,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize daily export revenue sensor."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            subentry=subentry,
            sensor_type="daily_export_revenue",
            sensor_name="Daily Export Revenue",
        )
