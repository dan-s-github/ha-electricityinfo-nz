# Contract: Sensor Platform

**Branch**: `003-multi-entity-market-node` | **Date**: 2026-05-20

---

## Overview

`sensor.async_setup_entry` creates sensor entities for each `"market_node"` subentry based on its enabled sensor types. Each entity subscribes to `ElectricityInfoCoordinator` updates.

---

## Entity Creation per Subentry

```python
async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    for subentry in entry.subentries.values():
        if subentry.subentry_type != "market_node":
            continue

        config = dict(subentry.data)
        entities = []

        if config.get("enable_live_price"):
            entities.append(LivePriceSensor(coordinator, entry, subentry))

        if config.get("enable_forecast"):
            if "day_ahead" in config.get("forecast_horizons", []):
                entities.append(DayAheadForecastSensor(coordinator, entry, subentry))
            if "intraday" in config.get("forecast_horizons", []):
                entities.append(IntradayForecastSensor(coordinator, entry, subentry))

        if config.get("enable_accounting"):
            entities.append(SettledPriceSensor(coordinator, entry, subentry))
            import_meter = config.get("import_meter_entity_id")
            export_meter = config.get("export_meter_entity_id")
            effective_export_meter = export_meter or import_meter
            if import_meter:
                entities.append(ImportCostSensor(coordinator, entry, subentry))
                entities.append(DailyImportCostSensor(coordinator, entry, subentry))
            if effective_export_meter:
                entities.append(ExportRevenueSensor(coordinator, entry, subentry))
                entities.append(DailyExportRevenueSensor(coordinator, entry, subentry))

        async_add_entities(entities, config_subentry_id=subentry.subentry_id)
```

---

## Coordinator Update Cycle

`ElectricityInfoCoordinator._async_update_data()` fetches all market node data in a single async pass:

1. For each `"market_node"` subentry:
   - If `enable_live_price` or day-ahead forecast enabled → `get_schedule_prices(PRSL/NRSL, forward=48)`
   - If intraday forecast enabled → `get_schedule_prices(PRSS/NRSS, forward=8)`
   - If accounting enabled → `get_schedule_prices("Interim", back=48)`
2. Errors are caught per-node and stored in `NodeData["error"]` — other nodes continue updating
3. On full success: reset `_retry_count`, restore `update_interval = 30 min`
4. On `AuthenticationError`: raise `ConfigEntryAuthFailed` (triggers HA re-auth flow)
5. On other API errors: increment `_retry_count`; exponential backoff (`1, 2, 4... min`); after `MAX_RETRIES` mark coordinator failed

**Schedule mapping for coordinator fetch**:

| Config | `forecast_type` | Day-ahead schedule | Intraday schedule |
|--------|----------------|-------------------|------------------|
| enabled | `price_responsive` | `PRSL` | `PRSS` |
| enabled | `non_responsive` | `NRSL` | `NRSS` |

---

## Entity Lifecycle

### Construction

All sensor classes accept `(coordinator, entry, subentry)`. They call `super().__init__(coordinator)` (CoordinatorEntity) and extract `subentry.data` as `self._config`.

### `async_added_to_hass`

**LivePriceSensor**:
1. Call `await super().async_added_to_hass()` (triggers RestoreEntity restore)
2. Call `await self.async_get_last_state()`
3. If restored state exists and is not stale (age ≤ 30 min): populate `self._native_value` and `self._attributes`
4. If stale: discard; request immediate coordinator refresh
5. Schedule coordinator refresh regardless (ensures fresh data on startup)

**DailyImportCostSensor / DailyExportRevenueSensor**:
1. Call `await super().async_added_to_hass()` (triggers RestoreEntity restore)
2. Call `await self.async_get_last_state()`
3. If restored state exists:
   - Restore `self._accumulated_total` from state value
   - Restore `self._accumulation_date` from `extra_state_attributes["accumulation_date"]`
   - If `self._accumulation_date` is prior to today NZT: reset `_accumulated_total = 0.0` and `_accumulation_date = today_nzt`
4. If no restored state: `_accumulated_total = 0.0`, `_accumulation_date = None`

**All other sensors**: Call `super().async_added_to_hass()` only; start with `self._native_value = None` (unavailable until first coordinator poll).

### `_handle_coordinator_update`

Called by CoordinatorEntity when coordinator data changes.

**Pattern for all sensors**:
```python
def _handle_coordinator_update(self):
    if not self.coordinator.data or self._subentry_id not in self.coordinator.data:
        self._native_value = None
        self._attributes = {}
        self.async_write_ha_state()
        return

    node_data = self.coordinator.data[self._subentry_id]
    if node_data.get("error"):
        self._native_value = None
        self.async_write_ha_state()
        return

    self._update_from_node_data(node_data)
    self.async_write_ha_state()
```

### `available` property

```python
@property
def available(self) -> bool:
    if not self.coordinator.last_update_success:
        return False
    # For LivePriceSensor: also available if restored state exists
    if self._native_value is None:
        return False
    return (
        self._subentry_id in (self.coordinator.data or {})
        and not (self.coordinator.data[self._subentry_id].get("error"))
    )
```

---

## State & Attribute Contracts

### LivePriceSensor

| Property | Type | Description |
|----------|------|-------------|
| `native_value` | `float \| None` | Current trade period price in `price_unit` |
| `native_unit_of_measurement` | `str` | `"c/kWh"` or `"NZD/kWh"` |
| `extra_state_attributes.timestamp` | `str` | ISO 8601 UTC of current trade period start |
| `extra_state_attributes.trading_period` | `int` | Period number (1–48) |
| `extra_state_attributes.node` | `str` | Market node code |
| `extra_state_attributes.schedule` | `str` | e.g., `"PRSL"` |
| `extra_state_attributes.forecast` | `list[PeriodPrice]` | Future trade periods from coordinator data |

### DayAheadForecastSensor

| Property | Type | Description |
|----------|------|-------------|
| `native_value` | `float \| None` | Next trade period price (first future entry) |
| `native_unit_of_measurement` | `str` | `price_unit` |
| `extra_state_attributes.forecast` | `list[PeriodPrice]` | Up to 48 future periods |
| `extra_state_attributes.history` | `list[PeriodPrice]` | Up to `forecast_retention_hours × 2` past periods |

### IntradayForecastSensor

Same shape as DayAheadForecastSensor; up to 8 forecast entries.

### SettledPriceSensor

| Property | Type | Description |
|----------|------|-------------|
| `native_value` | `float \| None` | Most recent settled period price in `price_unit` |
| `native_unit_of_measurement` | `str` | `price_unit` |
| `extra_state_attributes.history` | `list[PeriodPrice]` | Up to `accounting_retention_hours × 2` periods |
| `extra_state_attributes.trading_period` | `int` | Most recent settled period number |
| `extra_state_attributes.timestamp` | `str` | ISO 8601 UTC of most recent settled period start |

### ImportCostSensor

| Property | Type | Description |
|----------|------|-------------|
| `native_value` | `float \| None` | `settled_price × import_kwh_delta` for most recent trade period |
| `native_unit_of_measurement` | `str` | `"c"` if `price_unit="c/kWh"`, else `"NZD"` |
| `extra_state_attributes.settled_price` | `float` | Settled price in `price_unit` |
| `extra_state_attributes.energy_kwh` | `float` | Import energy delta for this period |
| `extra_state_attributes.import_meter_entity_id` | `str` | Linked import meter entity_id |
| `extra_state_attributes.trading_period` | `int` | Matched trade period |

### ExportRevenueSensor

Same shape as ImportCostSensor; uses `export_kwh_delta` and effective export meter (`export_meter_entity_id` if set, else `import_meter_entity_id` fallback).

### DailyImportCostSensor

| Property | Type | Description |
|----------|------|-------------|
| `native_value` | `float \| None` | Accumulated import cost since midnight NZT |
| `native_unit_of_measurement` | `str` | `"c"` if `price_unit="c/kWh"`, else `"NZD"` |
| `state_class` | — | `SensorStateClass.TOTAL` |
| `extra_state_attributes.accumulation_date` | `str` | NZT date string (YYYY-MM-DD) for which total is accumulated |
| `extra_state_attributes.import_meter_entity_id` | `str` | Linked import meter entity_id |

**Midnight reset** (in `_handle_coordinator_update`):
```python
accounting_date = node_data.get("accounting_date_nzt")
if accounting_date and accounting_date != self._accumulation_date:
    self._accumulated_total = 0.0
    self._accumulation_date = accounting_date
if node_data.get("import_cost_delta") is not None:
    self._accumulated_total += node_data["import_cost_delta"]
self._native_value = self._accumulated_total
```

### DailyExportRevenueSensor

Same shape as DailyImportCostSensor; accumulates `export_revenue_delta` and uses effective export meter (`export_meter_entity_id` if set, else `import_meter_entity_id` fallback).

---

## Unit Conversion at Ingest

Performed in coordinator `_async_update_data` before storing in `CoordinatorData`.

```python
def _convert_price(price_nzd_mwh: float, price_unit: str) -> float:
    if price_unit == "c/kWh":
        return round(price_nzd_mwh * 0.1, 4)
    # "NZD/kWh"
    return round(price_nzd_mwh / 1000.0, 6)
```

All `PriceDetail.price` values are converted before being stored; no conversion occurs in sensor entity property getters.

---

## Device Registry

One HA device per market node subentry.

```python
DeviceInfo(
    identifiers={(DOMAIN, subentry.subentry_id)},
    name=subentry.title,                   # e.g., "BRB0331 Bream Bay [c/kWh]"
    manufacturer="Electricity Info NZ",
    entry_type=DeviceEntryType.SERVICE,
)
```

All sensor entities for a given market node subentry share this device.
