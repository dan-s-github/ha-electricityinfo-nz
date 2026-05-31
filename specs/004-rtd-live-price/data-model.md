# Data Model: RTD-Based Live Price Sensor

**Branch**: `004-rtd-live-price` | **Date**: 2026-05-31

---

## Overview

Feature 004 introduces **no config schema changes**. The `MarketNodeSubentry` data shape (defined in 003) is unchanged. The changes are internal to the coordinator: the `live_current` coordinator data key is now populated from an RTD API response instead of the day-ahead forecast response.

---

## Changed: Coordinator Constants (`const.py`)

| Constant | 003 Value | 004 Value | Notes |
|----------|-----------|-----------|-------|
| `UPDATE_INTERVAL_MINUTES` | `30` | `5` | Poll interval reduced to match RTD publication cadence |
| `RTD_BACK_PERIODS` | _(not present)_ | `3` | New constant; `back` parameter for RTD API call |

No other constants are added or removed.

---

## Changed: Coordinator Node Data (`node_data` dict)

The in-memory `node_data` dict returned by `_fetch_market_node_data` has the following key behaviour changes:

| Key | 003 Source | 004 Source | Notes |
|-----|-----------|-----------|-------|
| `live_current` | Extracted from `day_ahead` (PRSL/NRSL, `forward=48`) | Extracted from new `rtd` response (`schedule="RTD"`, `back=3`) | Source schedule changes from forecast to RTD |
| `day_ahead` | Populated when `enable_live_price OR (enable_forecast AND day_ahead in horizons)` | Populated **only** when `enable_forecast AND day_ahead in horizons` | Decoupled from live price |
| `rtd` | _(not present)_ | New key; `ScheduleDetails \| None`; populated when `enable_live_price=True` | Raw RTD response; used to extract `live_current`; not exposed to sensors directly |

All other keys (`intraday`, `accounting`, `settled_price`, `settled_timestamp`, etc.) are **unchanged**.

---

## `live_current` Payload (unchanged shape, new source)

The dict stored in `node_data["live_current"]` retains the same shape as in 003 — only the `schedule` value changes:

| Field | Type | 003 Example | 004 Example |
|-------|------|-------------|-------------|
| `timestamp` | `str` | `"2026-05-31T01:00:00+00:00"` | `"2026-05-31T01:00:00+00:00"` |
| `trading_period` | `int` | `3` | `3` |
| `node` | `str` | `"HAY2201"` | `"HAY2201"` |
| `schedule` | `str` | `"PRSL"` | `"RTD"` |
| `price` | `float \| None` | `12.3456` | `12.3456` (from `PriceDetail.price`) |

**Extraction logic** (`_extract_live_price_payload`): unchanged — finds the `PriceDetail` whose `trading_datetime` window contains `utcnow()`; falls back to most recent past period. Now receives RTD data instead of day-ahead data.

---

## `LivePriceSensor` State Attributes (changed: `schedule` value)

| Attribute | 003 Value | 004 Value |
|-----------|-----------|-----------|
| `schedule` | `"PRSL"` or `"NRSL"` | `"RTD"` |
| All others | unchanged | unchanged |

This change is the data-source transition described in SC-002. HA entity history will reflect the transition naturally; no migration handler is needed.

---

## Config Entry & Subentry Schema (unchanged)

`ConfigFlow.VERSION` remains `2`. No subentry fields are added or removed. The `enable_live_price` flag already exists and continues to gate the new RTD fetch.

---

## API Call Summary (004 coordinator per-subentry)

| Condition | Schedule | `back` | `forward` | Populates |
|-----------|----------|--------|-----------|-----------|
| `enable_live_price=True` | `"RTD"` | `3` | _(omitted)_ | `node_data["live_current"]`, `node_data["rtd"]` |
| `enable_forecast=True AND "day_ahead" in horizons` | PRSL or NRSL | `forecast_retention_hours × 2` | `48` | `node_data["day_ahead"]` |
| `enable_forecast=True AND "intraday" in horizons` | PRSS or NRSS | `forecast_retention_hours × 2` | `8` | `node_data["intraday"]` |
| `enable_accounting=True` | `"Interim"` | `accounting_retention_hours × 2` | _(omitted)_ | `node_data["accounting"]` |
