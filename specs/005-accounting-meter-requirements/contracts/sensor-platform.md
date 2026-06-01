# Contract: Sensor Platform

**Branch**: `005-accounting-sensors` | **Date**: 2026-06-01
**Supersedes**: `specs/004-rtd-live-price/contracts/sensor-platform.md` (accounting sensor sections only)

---

## Overview

This contract documents **changes** introduced by feature 005. All sections not listed here remain as specified in the 004 sensor-platform contract.

---

## Changed: `_validate_meter_entity` Contract

### Criteria

An entity is a valid meter entity if and only if ALL of the following are true:

```
state.attributes["device_class"] == "energy"
AND state.attributes["unit_of_measurement"] == "kWh"
AND "last_reset" NOT IN state.attributes
```

Any entity failing this check returns `False`. The config flow shows:
- `"entity_not_energy_import"` for the import meter field
- `"entity_not_energy_export"` for the export meter field

### Same-entity check

After both meters pass individual validation, if `import_meter == export_meter` (and both are non-None), the config flow sets `errors["base"] = "same_entity_import_export"` and rejects the save. The same-entity check is **not** raised if either meter already has an individual validation error.

### Accepted entity types

| Entity type | `device_class` | `unit` | `last_reset` present? | Accepted? |
|-------------|---------------|--------|----------------------|-----------|
| Native cumulative smart meter (e.g., Shelly, Emporia) | `energy` | `kWh` | No | ✅ Yes |
| HA Riemann sum integration helper | `energy` | `kWh` | No | ✅ Yes |
| HA utility meter helper | `energy` | `kWh` | **Yes** | ❌ No |

---

## Changed: Coordinator `_populate_accounting_metrics`

### Removed: bidirectional same-entity code path

The check `import_meter == export_meter` as a bidirectional shortcut is removed. Each direction is always computed independently.

Also removed: `export_meter = config.get(CONF_EXPORT_METER_ENTITY_ID) or import_meter` fallback.

### Added: runtime guard for legacy same-entity configs

```python
if import_meter and export_meter and import_meter == export_meter:
    _LOGGER.warning("Subentry %s: same-entity import/export; accounting skipped.", subentry_id)
    return
```

This guard fires before delta computation. Affected subentries skip accounting; live price and forecast sensors are unaffected.

---

## Changed: `DailyImportCostSensor` / `DailyExportRevenueSensor` State Contract

### Accumulation (unchanged pattern)

Still owned by the sensor via `self._accumulated_total` and `self._accumulation_date`. Reset when `accounting_date_nzt` changes.

### New: day-rollover snapshot

When `accounting_date_nzt` changes from the previous value, **before resetting** `_accumulated_total`:

```python
self._previous_day_total = self._accumulated_total
self._accumulated_total = 0.0
```

### State attributes (additions)

| Attribute | Type | Notes |
|-----------|------|-------|
| `accumulation_date` | `str` (ISO date) | Unchanged |
| `previous_day_total` | `float \| None` | **NEW**: prior-day snapshot stored in HA state attributes for RestoreEntity persistence |
| `conf_import_meter_entity_id` / `conf_export_meter_entity_id` | `str \| None` | Unchanged |

### Restore behaviour (unchanged + extension)

On HA restart, `async_added_to_hass` restores:
- `self._accumulated_total` from `last_state.state` (as before)
- `self._accumulation_date` from `last_state.attributes["accumulation_date"]` (as before)
- `self._previous_day_total` from `last_state.attributes["previous_day_total"]` (**new**)

If restored accumulation date is stale (< today NZT): reset `_accumulated_total = 0.0` as before.

---

## New: `PreviousDayImportCostSensor` / `PreviousDayExportRevenueSensor` State Contract

### State value

`self._daily_sensor._previous_day_total` — read directly from the paired daily sensor instance. `None` (unavailable) until the first daily rollover occurs or a prior state is restored.

### State class

`SensorStateClass.TOTAL`

### Update behaviour

`_handle_coordinator_update` only calls `async_write_ha_state()` when the value differs from the last written value (value-change detection). Between rollovers, state is held unchanged. No unnecessary state writes.

### Restore behaviour

`async_added_to_hass` restores last state. The restored value seeds `_daily_sensor._previous_day_total` only if the daily sensor's own restore has not already set it (attribute-present check). This handles both startup orders:
- Daily sensor restores first → its `previous_day_total` attribute is present and used directly
- Previous-day sensor restores first → seeds the daily sensor's field; daily sensor restore then overwrites if it has a value

### `unique_id`

`electricityinfo_{entry_id}_{subentry_id}_previous_day_import_cost`
`electricityinfo_{entry_id}_{subentry_id}_previous_day_export_revenue`

---

## Sensor Creation Conditions (unchanged except additions)

| Sensor | Created when |
|--------|-------------|
| `SettledPriceSensor` | `enable_accounting=True` |
| `ImportCostSensor` | `enable_accounting=True` AND `import_meter` configured |
| `ExportRevenueSensor` | `enable_accounting=True` AND `export_meter` configured |
| `DailyImportCostSensor` | same as `ImportCostSensor` |
| `DailyExportRevenueSensor` | same as `ExportRevenueSensor` |
| `PreviousDayImportCostSensor` | **NEW**: same as `DailyImportCostSensor` |
| `PreviousDayExportRevenueSensor` | **NEW**: same as `DailyExportRevenueSensor` |
