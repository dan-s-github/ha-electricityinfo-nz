# Data Model: Multiple Entities for Market Node

**Branch**: `003-multi-entity-market-node` | **Date**: 2026-05-20

---

## Config Entry (Root — unchanged from 002)

Stored in `config_entry.data`. OAuth credentials only. Shared by all market node subentries.

| Field | Type | Constraints |
|-------|------|-------------|
| `client_id` | `str` | Required; non-empty |
| `client_secret` | `str` | Required; non-empty; stored encrypted by HA |

**Version**: `ConfigFlow.VERSION = 2` (incremented from 1 for breaking schema change)

---

## MarketNodeSubentry (Config Subentry — `subentry_type = "market_node"`)

Stored in `config_subentry.data`. One subentry per configured market node.

### Core Fields

| Field | Type | Allowed Values | Default | Required |
|-------|------|----------------|---------|----------|
| `node` | `str` | See MARKET_NODES constant | — | ✅ |
| `price_unit` | `str` | `"c/kWh"`, `"NZD/kWh"` | — | ✅ |

### Live Price Section

| Field | Type | Allowed Values | Default | Required |
|-------|------|----------------|---------|----------|
| `enable_live_price` | `bool` | `True`, `False` | `False` | ✅ |

### Forecast Section

| Field | Type | Allowed Values | Default | Required |
|-------|------|----------------|---------|----------|
| `enable_forecast` | `bool` | `True`, `False` | `False` | ✅ |
| `forecast_type` | `str` | `"price_responsive"`, `"non_responsive"` | `"price_responsive"` | if `enable_forecast` |
| `forecast_horizons` | `list[str]` | `["day_ahead"]`, `["intraday"]`, `["day_ahead","intraday"]` | `["day_ahead"]` | if `enable_forecast` |
| `forecast_retention_hours` | `int` | `6`, `12`, `24` | `24` | if `enable_forecast` |

### Accounting Section

| Field | Type | Allowed Values | Default | Required |
|-------|------|----------------|---------|----------|
| `enable_accounting` | `bool` | `True`, `False` | `False` | ✅ |
| `accounting_retention_hours` | `int` | `24`, `48` | `24` | if `enable_accounting` |
| `import_meter_entity_id` | `str \| None` | Valid HA entity_id with `device_class: energy` | `None` | ❌ (optional) |
| `export_meter_entity_id` | `str \| None` | Valid HA entity_id with `device_class: energy` | `None` | ❌ (optional) |

### Validation Rules

1. At least one of `enable_live_price`, `enable_forecast`, `enable_accounting` must be `True` (FR-016)
2. If `enable_forecast = True`, `forecast_horizons` must be non-empty
3. If `import_meter_entity_id` is provided, the referenced entity must have `device_class: energy` and unit `kWh` (FR-018)
4. If `export_meter_entity_id` is provided, the referenced entity must have `device_class: energy` and unit `kWh` (FR-018)
5. If `export_meter_entity_id` is unset and `import_meter_entity_id` is set, export calculations use the import meter in signed bidirectional mode (FR-018 clarification)
6. If `import_meter_entity_id == export_meter_entity_id` (both set, same entity), bidirectional mode applies (positive delta = import, negative delta absolute value = export)
7. `node` must be a member of the `MARKET_NODES` constant list

### Lifecycle / State Transitions

```
┌─────────────────────────────────────────────────────────────────────┐
│  Subentry lifecycle                                                 │
│                                                                     │
│  add subentry → data validated → subentry created → sensors loaded  │
│       ↓                                                             │
│  reconfigure → re-validate → update data → sensors reloaded         │
│       ↓                                                             │
│  delete subentry → sensors removed                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## CoordinatorData

Returned by `ElectricityInfoCoordinator._async_update_data()`. Dict keyed by `subentry_id`.

```python
CoordinatorData = dict[str, NodeData]

class NodeData(TypedDict):
    day_ahead: ScheduleDetails | None       # PRSL or NRSL, forward=48; None if not fetched
    intraday: ScheduleDetails | None        # PRSS or NRSS, forward=8;  None if not fetched
    accounting: ScheduleDetails | None      # Interim, back=48;          None if not fetched
    import_cost_delta: float | None         # current period: settled_price × import_kwh_delta
    export_revenue_delta: float | None      # current period: settled_price × export_kwh_delta
    accounting_date_nzt: date | None        # NZT date of latest settled period (for midnight reset)
    config: dict                            # snapshot of subentry.data at fetch time
    error: str | None                       # last fetch error message; None on success
```

`ScheduleDetails` (from `electricityinfo_nz.models`):
- `.schedule: str` — schedule code (e.g., "PRSL")
- `.schedule_name: str` — human-readable name
- `.prices: list[PriceDetail]`

`PriceDetail` (from `electricityinfo_nz.models`):
- `.trading_datetime: datetime` — UTC datetime of trade period start
- `.trading_period: int` — period number (1–48)
- `.node: str` — market node code
- `.price: float | None` — NZD/MWh
- `.price6s: float | None` — 6-second price (not used by 003)
- `.price60s: float | None` — 60-second price (not used by 003)
- `.schedule: str | None`
- `.run_type: str | None`

---

## Sensor Entities

All sensors share the same `device_info` keyed by `subentry_id` (one HA device per market node subentry).

### Unique ID Convention

```
electricityinfo_<entry_id>_<subentry_id>_<sensor_type>
```

Sensor type suffixes:
| Sensor Class | Suffix |
|---|---|
| `LivePriceSensor` | `live_price` |
| `DayAheadForecastSensor` | `day_ahead_forecast` |
| `IntradayForecastSensor` | `intraday_forecast` |
| `SettledPriceSensor` | `settled_price` |
| `ImportCostSensor` | `import_cost` |
| `ExportRevenueSensor` | `export_revenue` |
| `DailyImportCostSensor` | `daily_import_cost` |
| `DailyExportRevenueSensor` | `daily_export_revenue` |

### LivePriceSensor

Inherits: `CoordinatorEntity`, `RestoreEntity`, `SensorEntity`

| Attribute | Value |
|-----------|-------|
| `native_unit_of_measurement` | `price_unit` from subentry config |
| `device_class` | `SensorDeviceClass.MONETARY` |
| `state_class` | `None` |
| `native_value` | Current trade period price (converted from NZD/MWh at ingest) |
| `extra_state_attributes` | `timestamp`, `trading_period`, `node`, `schedule`, `forecast: list[PeriodPrice]` |
| RestoreEntity | ✅ Yes — single float + minimal attrs, safe to restore on restart |

**Current period detection**: From `day_ahead` data, select the `PriceDetail` with the largest `trading_datetime ≤ utcnow()`. Remaining entries (future periods) populate `forecast`.

### DayAheadForecastSensor

Inherits: `CoordinatorEntity`, `SensorEntity`

| Attribute | Value |
|-----------|-------|
| `native_unit_of_measurement` | `price_unit` from subentry config |
| `device_class` | `SensorDeviceClass.MONETARY` |
| `native_value` | Price of the next upcoming trade period |
| `extra_state_attributes` | `forecast: list[PeriodPrice]` (up to 48 future periods), `history: list[PeriodPrice]` (all prior periods returned by retention-defined API `back` window; typically `forecast_retention_hours × 2` periods) |
| RestoreEntity | ❌ No — start unavailable on restart |

### IntradayForecastSensor

Inherits: `CoordinatorEntity`, `SensorEntity`

Same shape as `DayAheadForecastSensor` but sourced from `intraday` (PRSS/NRSS, up to 8 forward periods).

### SettledPriceSensor

Inherits: `CoordinatorEntity`, `SensorEntity`

| Attribute | Value |
|-----------|-------|
| `native_unit_of_measurement` | `price_unit` from subentry config |
| `device_class` | `SensorDeviceClass.MONETARY` |
| `native_value` | Most recent settled price (latest entry in `back=48` result) |
| `extra_state_attributes` | `history: list[PeriodPrice]` (up to `accounting_retention_hours × 2` periods), `trading_period`, `timestamp`, `node` |
| RestoreEntity | ❌ No — start unavailable on restart |

### ImportCostSensor

Inherits: `CoordinatorEntity`, `SensorEntity`

Only created when `import_meter_entity_id` is set.

| Attribute | Value |
|-----------|-------|
| `native_unit_of_measurement` | `"c"` (if `price_unit = "c/kWh"`) or `"NZD"` (if `price_unit = "NZD/kWh"`) |
| `device_class` | `SensorDeviceClass.MONETARY` |
| `native_value` | `import_cost_delta` from `NodeData` (settled_price × import_kwh_delta for current period) |
| `extra_state_attributes` | `settled_price`, `energy_kwh`, `import_meter_entity_id`, `trading_period`, `timestamp` |
| RestoreEntity | ❌ No — start unavailable on restart |

### ExportRevenueSensor

Created when an effective export meter exists. Effective export meter is `export_meter_entity_id` if set; otherwise `import_meter_entity_id` (signed bidirectional fallback). Same shape as `ImportCostSensor` but uses `export_revenue_delta`. Sensor name: "Export Revenue".

---

### DailyImportCostSensor

Inherits: `CoordinatorEntity`, `RestoreEntity`, `SensorEntity`

Only created when `import_meter_entity_id` is set.

| Attribute | Value |
|-----------|-------|
| `native_unit_of_measurement` | `"c"` (if `price_unit = "c/kWh"`) or `"NZD"` (if `price_unit = "NZD/kWh"`) |
| `device_class` | `SensorDeviceClass.MONETARY` |
| `state_class` | `SensorStateClass.TOTAL` |
| `native_value` | Accumulated import cost since midnight NZT |
| `extra_state_attributes` | `accumulation_date` (NZT date string), `import_meter_entity_id` |
| RestoreEntity | ✅ Yes — persists accumulated daily total; continues accumulating on restart. If restored date is prior day, resets to zero immediately. |

**Midnight reset logic** (in `_handle_coordinator_update`):
```python
accounting_date = node_data.get("accounting_date_nzt")
if accounting_date and accounting_date != self._accumulation_date:
    self._accumulated_total = 0.0
    self._accumulation_date = accounting_date
if node_data.get("import_cost_delta") is not None:
    self._accumulated_total += node_data["import_cost_delta"]
```

### DailyExportRevenueSensor

Created when an effective export meter exists (`export_meter_entity_id` or fallback to `import_meter_entity_id`). Same shape as `DailyImportCostSensor` but accumulates `export_revenue_delta`. Sensor name: "Daily Export Revenue".

---

## PeriodPrice (Attribute Object)

Used in `forecast` and `history` attributes of all sensor types.

```python
class PeriodPrice(TypedDict):
    period_start: str    # ISO 8601 UTC datetime string
    trading_period: int  # 1–48
    price: float         # in node's price_unit (already converted at ingest)
```

---

## Migration Model (VERSION 1 → 2)

See `research.md §1` for full mapping rules. Summary:

| 002 `schedule_type` | 003 `enable_forecast` | 003 `forecast_type` | 003 `forecast_horizons` |
|---|---|---|---|
| `PRSL` | `True` | `price_responsive` | `["day_ahead"]` |
| `PRSS` | `True` | `price_responsive` | `["intraday"]` |
| `NRSL` | `True` | `non_responsive` | `["day_ahead"]` |
| `NRSS` | `True` | `non_responsive` | `["intraday"]` |
| `RTD`, `WDS`, `Final`, `Interim` | `False` | — | `[]` |

All migrated subentries: `enable_live_price=True`, `enable_accounting=False`, `price_unit="NZD/kWh"`, `forecast_retention_hours=24`, `accounting_retention_hours=24`, `import_meter_entity_id=None`, `export_meter_entity_id=None`.

If multiple legacy 002 entries resolve to the same `node`, migration keeps the first and skips later duplicates with warnings (one 003 subentry per market node).

Post-migration runtime setup creates only `market_node` entities; legacy `sensor` entities are not created.

Entity IDs **will change** for all sensors (002 suffix `_nzd_mwh`/`_c_kwh` → 003 suffix `_live_price` etc.). Log one warning per changed entity ID during migration.
