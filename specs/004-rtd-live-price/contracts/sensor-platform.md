# Contract: Sensor Platform

**Branch**: `004-rtd-live-price` | **Date**: 2026-05-31
**Supersedes**: `specs/003-multi-entity-market-node/contracts/sensor-platform.md` (coordinator update cycle and LivePriceSensor sections only)

---

## Overview

This contract documents the **changes** introduced by feature 004. All sections not listed here remain as specified in the 003 sensor-platform contract.

---

## Changed: Coordinator Poll Interval

The `ElectricityInfoCoordinator` poll interval changes from **30 minutes** to **5 minutes**.

```python
# const.py
UPDATE_INTERVAL_MINUTES = 5  # was 30

# coordinator.py __init__
super().__init__(
    hass,
    _LOGGER,
    name="Electricityinfo NZ Price Coordinator",
    update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),  # now 5 min
)
```

On successful update: `self.update_interval = timedelta(minutes=UPDATE_INTERVAL_MINUTES)` (restored to 5 min).
On API error: existing exponential backoff unchanged (`RETRY_INTERVAL_MINUTES`, `MAX_RETRIES`).

---

## Changed: Coordinator Update Cycle

`ElectricityInfoCoordinator._async_update_data()` fetches all market node data in a single async pass. The fetch order per subentry is:

1. **If `enable_live_price=True`** → `get_schedule_prices(schedule="RTD", market_type="E", nodes=[node], back=RTD_BACK_PERIODS)` *(no `forward` parameter)*
   - Stores raw response in `node_data["rtd"]`
   - Extracts current-period payload into `node_data["live_current"]` via `_extract_live_price_payload()`
2. **If `enable_forecast=True` and `"day_ahead" in forecast_horizons`** → `get_schedule_prices(schedule=PRSL/NRSL, forward=48, back=forecast_retention_hours×2)`
   - Stores in `node_data["day_ahead"]`
   - *(No longer used for live price extraction)*
3. **If `enable_forecast=True` and `"intraday" in forecast_horizons`** → `get_schedule_prices(schedule=PRSS/NRSS, forward=8, back=forecast_retention_hours×2)`
   - Stores in `node_data["intraday"]`
4. **If `enable_accounting=True`** → `get_schedule_prices(schedule="Interim", back=accounting_retention_hours×2)`
   - Stores in `node_data["accounting"]`; populates settled/meter-derived fields

Key change from 003: step 1 (RTD) and step 2 (day-ahead forecast) are now **fully independent**. In 003, the day-ahead call fired when *either* `enable_live_price` or `enable_forecast/day_ahead` was true. In 004, each fires on its own condition only.

**Updated schedule mapping table**:

| Sensor type | Config condition | Schedule | `back` | `forward` |
|-------------|-----------------|----------|--------|-----------|
| Live price  | `enable_live_price=True` | `"RTD"` | `3` | _(omitted)_ |
| Day-ahead forecast | `enable_forecast=True AND "day_ahead" in horizons` | PRSL / NRSL | `retention × 2` | `48` |
| Intraday forecast | `enable_forecast=True AND "intraday" in horizons` | PRSS / NRSS | `retention × 2` | `8` |
| Settled / accounting | `enable_accounting=True` | `"Interim"` | `retention × 2` | _(omitted)_ |

---

## Changed: `LivePriceSensor` State Contract

| Property | 003 Value | 004 Value |
|----------|-----------|-----------|
| `extra_state_attributes.schedule` | `"PRSL"` or `"NRSL"` | `"RTD"` |
| All other properties | unchanged | unchanged |

Full `LivePriceSensor` state contract (004):

| Property | Type | Description |
|----------|------|-------------|
| `native_value` | `float \| None` | Current trade period RTD price in `price_unit` |
| `native_unit_of_measurement` | `str` | `"c/kWh"` or `"NZD/kWh"` |
| `extra_state_attributes.timestamp` | `str` | ISO 8601 UTC of current RTD trade period start |
| `extra_state_attributes.trading_period` | `int` | Period number (1–48) |
| `extra_state_attributes.node` | `str` | Market node code |
| `extra_state_attributes.schedule` | `str` | Always `"RTD"` (SC-002) |
| `extra_state_attributes.history` | `list[dict]` | All RTD periods from `back=3` call, sorted chronologically. Each entry: `{timestamp, trading_period, price, node, schedule}`. Present only when `live_current` is populated. |

> **Note**: The `forecast` attribute (list of future periods) present in 003 is no longer populated by the live price sensor in 004, as the RTD call has no forward window. Forecast data is available via the `DayAheadForecastSensor` and `IntradayForecastSensor` entities.

---

## Unchanged

The following contracts from 003 are **unchanged** in 004:

- Entity creation per subentry (`async_setup_entry`)
- Entity lifecycle (`async_added_to_hass`, `_handle_coordinator_update`, `available` property)
- All sensor state/attribute contracts except `LivePriceSensor.schedule` (noted above)
- Config flow schema (no new fields)
- Error handling and retry behaviour
