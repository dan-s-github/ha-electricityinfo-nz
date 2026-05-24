# Research: Multiple Entities for Market Node

**Branch**: `003-multi-entity-market-node` | **Date**: 2026-05-20

## 1. HA Config Entry Migration (002 → 003)

**Decision**: Implement `async_migrate_entry(hass, entry)` in `__init__.py`; increment `ConfigFlow.VERSION` from `1` to `2`.

**Rationale**: HA automatically calls `async_migrate_entry` when a stored config entry's version is lower than the current `ConfigFlow.VERSION`. The function receives the old entry, applies data transformations, then calls `hass.config_entries.async_update_entry(entry, data=..., version=2)` to write the migrated entry. On failure it must return `False` to trigger a HA error notification.

**Migration mapping (VERSION 1 → 2)**:

002 subentry data shape:
```python
{
    "schedule_type": "PRSL",   # one of: PRSL, PRSS, NRSL, NRSS, RTD, WDS, Final, Interim
    "market_type": "E",        # "E" or "R"
    "node": "BRB0331",
    "forward_prices_count": 24,  # hours
    "name": "My Sensor",       # optional
}
```

003 subentry data shape (see data-model.md for canonical definition):
```python
{
    "node": "BRB0331",
    "price_unit": "NZD/kWh",   # default for migration
    "enable_live_price": True,
    "enable_forecast": True,
    "forecast_type": "price_responsive",  # or "non_responsive"
    "forecast_horizons": ["day_ahead"],   # ["day_ahead"], ["intraday"], or both
    "forecast_retention_hours": 24,
    "enable_accounting": False,
    "accounting_retention_hours": 24,
    "import_meter_entity_id": None,
    "export_meter_entity_id": None,
}
```

Mapping rules:
- `PRSL` → `forecast_type="price_responsive"`, `forecast_horizons=["day_ahead"]`
- `PRSS` → `forecast_type="price_responsive"`, `forecast_horizons=["intraday"]`
- `NRSL` → `forecast_type="non_responsive"`, `forecast_horizons=["day_ahead"]`
- `NRSS` → `forecast_type="non_responsive"`, `forecast_horizons=["intraday"]`
- `RTD`, `WDS`, `Interim`, `Final` → `enable_forecast=False`; `enable_accounting=False`; `enable_live_price=True` only
- Multiple 002 subentries for the same node: only one 003 subentry is created per `market_node`; keep the first encountered entry and skip later duplicates with a warning
- `forward_prices_count` is dropped (003 uses fixed forecast horizons)
- Entity IDs change (002 had `_nzd_mwh` and `_c_kwh` suffixes; 003 uses sensor-type suffixes); log a warning listing all changed entity IDs

**Alternatives considered**:
- Clean removal (require users to reconfigure): simpler code but poor UX for existing users
- Coexistence (both 002 and 003 simultaneously): complex; entity ID conflicts likely

---

## 2. Config Subentry Flow — Multi-Section Market Node Form

**Decision**: Single `user` step with a flat voluptuous schema. HA's UI renders boolean fields as toggles; dependent fields are always included in the schema but ignored during processing when the parent toggle is `False`. Validation runs in Python, not voluptuous, to check cross-field dependencies (e.g., at least one sensor type must be enabled).

**Rationale**: HA's config flow has no native "conditional section reveal" in 2026.3.1. Showing all fields and ignoring disabled sections during validation is the standard pattern used by core integrations. It avoids multi-step flows for a single entity.

**Energy meter entity linking**: Use `EntitySelector(EntitySelectorConfig(domain="sensor", device_class="energy"))` — HA's entity selector with `device_class` filter automatically presents only matching entities in the UI. Python validation confirms the resolved entity still has `device_class: energy` at save time (FR-018).

**Alternatives considered**:
- Multi-step subentry flow (one step per section): adds navigation complexity; no clear benefit for ≤6 fields per section

---

## 3. Selective RestoreEntity

**Decision**: `LivePriceSensor`, `DailyImportCostSensor`, and `DailyExportRevenueSensor` inherit from `RestoreEntity`. All other sensor classes (`DayAheadForecastSensor`, `IntradayForecastSensor`, `SettledPriceSensor`, `ImportCostSensor`, `ExportRevenueSensor`) inherit from `CoordinatorEntity` + `SensorEntity` only.

**Rationale**:
- The live price sensor state is a single float (current trade period price) — meaningful even if slightly stale (within one trade period, ~30 min).
- Daily total sensors accumulate cost/revenue through the day — losing the accumulated total on restart would mean starting from zero mid-day, which is incorrect. Restoring and continuing from the last persisted total is the correct behaviour (stale-if-meter-changed during outage is an accepted limitation).
- Forecast sensors carry a 48-period array in attributes — stale arrays could drive automations incorrectly.
- Per-period accounting sensors (SettledPrice, ImportCost, ExportRevenue) accumulate history — stale totals after a restart could produce wrong cost calculations.
- HA's `RestoreEntity.async_get_last_state()` restores the full `State` object including attributes; acceptable for single float + minimal attrs.

**Staleness guard**: Restored live price state older than `UPDATE_INTERVAL_MINUTES` (30 min) triggers `coordinator.async_request_refresh()` immediately and discards the restored value. Daily total sensors do NOT apply a staleness guard — they always continue accumulating from the restored value regardless of age (the daily reset logic will reset them at midnight NZT if the day has advanced).

---

## 4. Coordinator Data Structure for Multi-Sensor-Type Nodes

**Decision**: Coordinator `_async_update_data` returns a nested dict keyed by `subentry_id`, each containing named fetch results:

```python
{
    "<subentry_id>": {
        "day_ahead": ScheduleDetails | None,       # PRSL or NRSL, forward=48
        "intraday": ScheduleDetails | None,        # PRSS or NRSS, forward=8
        "accounting": ScheduleDetails | None,      # Interim, back=48
        "import_cost_delta": float | None,         # current period: settled_price × import_kwh_delta
        "export_revenue_delta": float | None,      # current period: settled_price × export_kwh_delta
        "accounting_date_nzt": date | None,        # NZT date of latest settled period (for midnight reset)
        "config": dict,                            # subentry data snapshot
        "error": str | None,                       # per-node fetch error
    },
    ...
}
```

Live price data comes from `day_ahead` (first current-period entry). If both day-ahead and live price are enabled, a single fetch serves both — no duplicate API call.

**Coordinator instance variables** (not in `CoordinatorData` — updated in-place between polls):
```python
self._meter_prev_import: dict[str, float | None] = {}  # subentry_id → previous import meter reading
self._meter_prev_export: dict[str, float | None] = {}  # subentry_id → previous export meter reading
```

**API call dispatch per subentry** (conditional on enabled sensor types):
1. If `enable_live_price` or (`enable_forecast` and `"day_ahead"` in horizons): fetch `PRSL`/`NRSL` with `forward=48`
2. If `enable_forecast` and `"intraday"` in horizons: fetch `PRSS`/`NRSS` with `forward=8`
3. If `enable_accounting`: fetch `Interim` with `back=48`

**Rationale**: Merging live price and day-ahead forecast into one API call satisfies FR-003 (same coordinator fetch for both). Per-node error isolation prevents one node's API failure from marking other nodes' data stale.

**Alternatives considered**:
- Flat dict keyed by `(subentry_id, data_type)` tuples: harder to iterate; more error-prone
- Separate coordinators per sensor type: violates the "single 30-min coordinator" decision

---

## 5. Price Unit Conversion at Ingest

**Decision**: Convert from API's NZD/MWh at coordinator fetch time. Store the converted value in `coordinator.data`. Sensors read the pre-converted value directly — no conversion in property getters.

Conversion factors:
- `c/kWh` = `NZD/MWh × 0.1`  (1 NZD/MWh = 0.1 c/kWh)
- `NZD/kWh` = `NZD/MWh ÷ 1000`

The user-selected `price_unit` is available as `subentry.data["price_unit"]`.

**Rationale**: Eliminates runtime conversion branching in every sensor property. Simplifies test assertions (all values in one known unit). Removes the need for `C_PER_KWH_TO_NZD_PER_MWH` reverse conversion constant from 002.

**Migration note**: 002 persisted state in display units and stored internally in NZD/MWh. During migration, no conversion is needed on the config data itself (it contains no price values). The first coordinator poll after upgrade will fetch fresh prices in the correct unit.

**Alternatives considered**:
- Store NZD/MWh internally + convert in property getter (002 approach): inconsistent with 003 design decision; retained for reference only

---

## 6. Accounting Sensors — Interim `back=48`, Energy Delta, and Daily Totals

**Decision**: Use `get_schedule_prices(schedule="Interim", market_type="E", nodes=[node], back=48)` for accounting. `back=48` = 48 trade periods = 24 hours of settled prices (full trading day).

**Confirmed by live testing**:
- Interim prices are identical to Final settled prices within ~30 min of each trading period closing
- `from_datetime`-only queries for Final have ~1-day publication lag (unreliable for recent periods)
- `back=48` reliably returns up to the last 24 hours of settled prices

**Energy volume delta computation**:
- On each coordinator poll, read current import/export meter states via `hass.states.get(import_meter_entity_id)` and `hass.states.get(export_meter_entity_id)`
- Compute delta: `delta_kwh = current_reading - self._meter_prev_import[subentry_id]`
- Store current reading as the new previous for next poll
- On first poll after startup (no previous stored): set previous reading, skip delta for that period (delta treated as `None`; ImportCostSensor/ExportRevenueSensor report `None`; daily totals do not update for that period)

**Bidirectional meter mode** (FR-018):
- If `import_meter_entity_id == export_meter_entity_id`, treat as signed bidirectional meter
- `import_delta = max(delta, 0)` (positive = import)
- `export_delta = abs(min(delta, 0))` (negative = export)

**Import cost / export revenue calculation**:
- `import_cost_delta` = `latest_settled_price (in price_unit) × import_delta_kwh`
- `export_revenue_delta` = `latest_settled_price (in price_unit) × export_delta_kwh`
- Coordinator stores these computed values in `NodeData["import_cost_delta"]` and `NodeData["export_revenue_delta"]`

**Energy meter entity validation** (FR-018):
- Config flow uses `EntitySelector(EntitySelectorConfig(domain="sensor", device_class="energy"))` for each picker
- On form submission, Python validation confirms each provided entity: `hass.states.get(entity_id).attributes.get("device_class") == "energy"`
- Entities not meeting this contract produce `"entity_not_energy_import"` or `"entity_not_energy_export"` form errors

**Accounting retention**: Minimum 24h (48 trade periods); options 24h or 48h; default 24h (FR-011).

---

## 7. Live Price Current Trade Period Detection

**Decision**: In `_handle_coordinator_update`, extract the current trade period from the day-ahead forecast data:
1. Sort `ScheduleDetails.prices` by `trading_datetime` ascending
2. Find the entry where `trading_datetime <= utcnow() < trading_datetime + timedelta(minutes=30)`
3. If found, use that entry's `price` as the live price sensor state
4. If not found (data gap), fall back to the most recent past entry (largest `trading_datetime <= utcnow()`)
5. All remaining entries (future periods) populate the `forecast` attribute

**Rationale**: The API's `forward` parameter returns upcoming periods starting from the next unstarted period; the current period may be the first entry or may be identified by timestamp comparison. Timestamp comparison is unambiguous.

**Alternatives considered**:
- Always use `sorted_prices[0]` (first entry): risks using a future period if the API returns data starting from the next period boundary

---

## 8. Daily Total Sensors — Midnight NZT Reset and Accumulation

**Decision**: `DailyImportCostSensor` and `DailyExportRevenueSensor` detect the midnight NZT day boundary coordinator-side. On each coordinator poll:
1. Extract the NZT date of the latest settled trade period from the Interim `back=48` response
2. Compare against the stored `accumulation_date` in `NodeData["accounting_date_nzt"]`
3. If the date has advanced, include `"reset_daily_totals": True` in `NodeData` (or simply propagate the new date); sensors detect the date change and reset their running total to zero before adding the current period's cost/revenue
4. If no date change, sensors add `import_cost_delta` / `export_revenue_delta` to their running total

Reset delay: up to ~30 minutes after midnight NZT (one coordinator interval). Accepted given 30-min trade period granularity.

**RestoreEntity behaviour**: Both daily total sensors call `async_get_last_state()` on startup; restore `_accumulated_total` and `_accumulation_date` from persisted state. If the restored date is earlier than today's NZT date, sensors reset to zero immediately (stale day detected on restore). Continue accumulating from the coordinator's next poll.

**Alternatives considered**:
- `async_track_point_in_time` HA scheduler at midnight NZT: adds HA scheduler dependency; coordinator-side date check is simpler and fully tested via mocked coordinator data
- Trade period number check (period == 1): ambiguous if coordinator misses the boundary poll

---

## 9. Two Independent Energy Meter Entity Selectors

**Decision**: Config flow exposes two independently optional energy meter entity selectors:
- `import_meter_entity_id` — grid import kWh meter (optional)
- `export_meter_entity_id` — grid export kWh meter (optional)

Each selector independently controls creation of the corresponding sensor tier:
- `import_meter_entity_id` set → `ImportCostSensor` + `DailyImportCostSensor` created
- `export_meter_entity_id` set → `ExportRevenueSensor` + `DailyExportRevenueSensor` created
- `export_meter_entity_id` unset and `import_meter_entity_id` set → export sensors also created using import meter as signed bidirectional source
- Neither set → only `SettledPriceSensor` created

**Bidirectional mode**: If both fields contain the same entity ID, or export is unset while import is set, the coordinator applies signed delta logic (positive = import, negative = export absolute value). This allows users with a single bidirectional grid meter to get both import cost and export revenue sensors.

**Rationale**: Most prosumers in HA have separate import and export sensors (HA Energy Dashboard standard). Supporting bidirectional as a special case (same entity in both fields) avoids requiring a third "meter type" toggle in the UI.

**Alternatives considered**:
- Single entity selector + meter type toggle (import/export/bidirectional): adds a UI control for a secondary choice that is implied by the entity selection
- Import only (export out of scope): omits export revenue tracking needed by prosumers
