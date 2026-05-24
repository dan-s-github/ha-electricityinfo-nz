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
    C_PER_KWH_TO_NZD_PER_MWH,
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
    NZD_PER_MWH_TO_C_PER_KWH,
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
            async_add_entities(market_entities, config_subentry_id=subentry.subentry_id)

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
        if not self.coordinator.last_update_success:
            return False
        if self._native_value is not None:
            return True
        node_data = (self.coordinator.data or {}).get(self._subentry_id)
        return bool(node_data and not node_data.get("error"))

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
                "forecast": list(node_data.get("live_forecast", [])),
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
            "forecast": [
                {
                    "period_start": p.trading_datetime.isoformat(),
                    "trading_period": p.trading_period,
                    "price": p.price,
                }
                for p in sorted_prices
                if p.trading_datetime > current.trading_datetime and p.price is not None
            ],
        }
        self.async_write_ha_state()


class ForecastSensorBase(MarketNodeSensorBase):
    """Base class for forecast sensors."""

    _schedule_key: str = ""

    @property
    def available(self) -> bool:
        """Return whether forecast data is available."""
        if not self.coordinator.last_update_success or self._native_value is None:
            return False
        node_data = (self.coordinator.data or {}).get(self._subentry_id)
        return bool(node_data and not node_data.get("error"))

    def _handle_coordinator_update(self) -> None:
        """Handle coordinator update for forecast sensors."""
        node_data = (self.coordinator.data or {}).get(self._subentry_id)
        if not node_data or node_data.get("error"):
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        schedule_details = node_data.get(self._schedule_key)
        if not schedule_details or not getattr(schedule_details, "prices", None):
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        now = dt_util.utcnow()
        sorted_prices = sorted(
            schedule_details.prices, key=lambda p: p.trading_datetime
        )
        future = [
            p for p in sorted_prices if p.trading_datetime > now and p.price is not None
        ]
        retention_periods = int(self._config.get(CONF_FORECAST_RETENTION_HOURS, 24)) * 2
        history = [
            p
            for p in sorted_prices
            if p.trading_datetime <= now and p.price is not None
        ][-retention_periods:]

        self._native_value = future[0].price if future else None
        self._attributes = {
            "forecast": [
                {
                    "period_start": p.trading_datetime.isoformat(),
                    "trading_period": p.trading_period,
                    "price": p.price,
                }
                for p in future
            ],
            "history": [
                {
                    "period_start": p.trading_datetime.isoformat(),
                    "trading_period": p.trading_period,
                    "price": p.price,
                }
                for p in history
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

        latest = max(settled_prices, key=lambda p: p.trading_datetime)
        retention = int(self._config.get(CONF_ACCOUNTING_RETENTION_HOURS, 24)) * 2
        history = sorted(settled_prices, key=lambda p: p.trading_datetime)[-retention:]
        self._native_value = latest.price
        self._attributes = {
            "trading_period": latest.trading_period,
            "timestamp": latest.trading_datetime.isoformat(),
            "node": latest.node,
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


class PriceSensorEntity(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Representation of an electricity price sensor entity."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = None
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
        self._attr_suggested_display_precision = 3 if unit == "c/kWh" else 2

        # Unique ID: one per unit
        unit_suffix = unit.replace("/", "_").lower()
        self._attr_unique_id = (
            f"electricityinfo_nz_{entry.entry_id}_{self._sensor_id}_{unit_suffix}"
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
            return round(self._native_value * NZD_PER_MWH_TO_C_PER_KWH, 3)
        return round(self._native_value, 3)

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
            # Fall back to restored state when coordinator hasn't fetched yet
            return self._native_value is not None

        return (
            self._sensor_id in self.coordinator.data
            and "error" not in self.coordinator.data[self._sensor_id]
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = dict(self._attributes)

        if self._unit == "c/kWh" and "forecast" in attrs:
            attrs["forecast"] = [
                {**p, "price": round(p["price"] * NZD_PER_MWH_TO_C_PER_KWH, 3)}
                for p in attrs["forecast"]
            ]

        return attrs

    async def async_added_to_hass(self) -> None:
        """Restore state when entity is added to Home Assistant."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            # Staleness guard: discard restored state older than one update interval
            timestamp_str = last_state.attributes.get("timestamp")
            if timestamp_str:
                restored_time = dt_util.parse_datetime(timestamp_str)
                if restored_time is not None:
                    age = dt_util.utcnow() - restored_time
                    if age > timedelta(minutes=UPDATE_INTERVAL_MINUTES):
                        _LOGGER.debug(
                            "Restored state for %s is stale (%s old), discarding",
                            self._sensor_id,
                            age,
                        )
                        await self.coordinator.async_request_refresh()
                        return

            raw_value = (
                float(last_state.state)
                if last_state.state not in ("unknown", "unavailable")
                else None
            )
            # Persisted state is in display units; convert back to canonical NZD/MWh
            if raw_value is not None and self._unit == "c/kWh":
                raw_value = raw_value * C_PER_KWH_TO_NZD_PER_MWH
            self._native_value = raw_value

            attrs = dict(last_state.attributes)
            if self._unit == "c/kWh" and "forecast" in attrs:
                attrs["forecast"] = [
                    {**p, "price": p["price"] * C_PER_KWH_TO_NZD_PER_MWH}
                    for p in attrs["forecast"]
                ]
            self._attributes = attrs
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

        sorted_prices = sorted(
            schedule_details.prices, key=lambda p: p.trading_datetime
        )
        if not sorted_prices:
            _LOGGER.warning(
                "No prices in schedule details for sensor %s", self._sensor_id
            )
            self._native_value = None
            self._attributes = {}
            self.async_write_ha_state()
            return

        price_info = sorted_prices[0]
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

        if len(sorted_prices) > 1:
            self._attributes["forecast"] = [
                {
                    "period_start": p.trading_datetime.isoformat(),
                    "price": round(p.price, 3),
                }
                for p in sorted_prices[1:]
                if p.price is not None
            ]
        else:
            self._attributes["forecast"] = []

        _LOGGER.debug(
            "Updated sensor %s: price=%s %s",
            self._sensor_id,
            self.native_value,
            self._unit,
        )

        self.async_write_ha_state()
