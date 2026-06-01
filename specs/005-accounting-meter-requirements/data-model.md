# Data Model: Accounting Sensor Meter Entity Requirements

**Branch**: `005-accounting-sensors` | **Date**: 2026-06-01

---

## Overview

Feature 005 introduces no config schema changes. The `MarketNodeSubentry` data shape is unchanged. Changes are confined to:
1. `_validate_meter_entity` in `config_flow.py` — tightened criteria + same-entity check
2. `coordinator.py` — remove bidirectional same-entity code path; add runtime guard for existing same-entity configs
3. `sensor.py` — add `_previous_day_total` to `DailyAccountingSensorBase`; add two new sensor classes with cross-sensor reference
4. `strings.json` / `en.json` — new error key

---

## Changed: `config_flow._validate_meter_entity`

### Before (003/004)

```python
def _validate_meter_entity(hass: HomeAssistant, entity_id: str | None) -> bool:
    if not entity_id:
        return True
    state = hass.states.get(entity_id)
    if state is None:
        return False
    return (
        state.attributes.get("device_class") == "energy"
        and state.attributes.get("unit_of_measurement") == "kWh"
    )
```

### After (005)

```python
def _validate_meter_entity(hass: HomeAssistant, entity_id: str | None) -> bool:
    if not entity_id:
        return True
    state = hass.states.get(entity_id)
    if state is None:
        return False
    return (
        state.attributes.get("device_class") == "energy"
        and state.attributes.get("unit_of_measurement") == "kWh"
        and "last_reset" not in state.attributes          # NEW: reject utility meters
    )
```

### New: same-entity validation in `_validate_node_fields`

After the individual meter checks, add:

```python
if (
    import_meter
    and export_meter
    and import_meter == export_meter
    and not errors.get(CONF_IMPORT_METER_ENTITY_ID)
    and not errors.get(CONF_EXPORT_METER_ENTITY_ID)
):
    errors["base"] = "same_entity_import_export"
```

> **Note**: The same-entity check only fires if both meters individually pass `_validate_meter_entity`. This prevents confusing double-error messages.

---

## Changed: Coordinator (`coordinator.py`)

### Removed: bidirectional same-entity code path in `_populate_accounting_metrics`

The following block is removed:

```python
# REMOVED:
bidirectional = bool(import_meter and export_meter and import_meter == export_meter)
...
if import_meter and bidirectional:
    delta = self._compute_delta(import_previous, import_current)
    if delta is None:
        return
    import_delta = max(delta, 0.0)
    export_delta = abs(min(delta, 0.0))
else:
    ...
```

Also removed: `export_meter = config.get(CONF_EXPORT_METER_ENTITY_ID) or import_meter`
(the `or import_meter` fallback that silently enabled bidirectional mode).

### Added: runtime guard for existing same-entity configs

Existing saved configs may still have `import_meter == export_meter` (from before this feature).
Since config-flow validation only applies on save, a runtime guard is needed:

```python
import_meter = config.get(CONF_IMPORT_METER_ENTITY_ID)
export_meter = config.get(CONF_EXPORT_METER_ENTITY_ID)

if import_meter and export_meter and import_meter == export_meter:
    _LOGGER.warning(
        "Subentry %s: import and export meter are the same entity (%s). "
        "Accounting skipped until configuration is corrected.",
        subentry_id,
        import_meter,
    )
    return  # Skip accounting metrics for this subentry
```

This guard fires before the delta computation. The subentry continues to function for live price
and forecast sensors; only accounting is suspended until the user corrects the config.

---

## Changed: `DailyAccountingSensorBase` (`sensor.py`)

### New instance variable

```python
self._previous_day_total: float | None = None
```

Added in `__init__` alongside the existing `self._accumulated_total`.

### Updated `async_added_to_hass`

Restore `_previous_day_total` from last state attributes:

```python
async def async_added_to_hass(self) -> None:
    """Restore accumulated total, date, and previous-day snapshot."""
    await super().async_added_to_hass()
    last_state = await self.async_get_last_state()
    if last_state and last_state.state not in ("unknown", "unavailable"):
        self._accumulated_total = float(last_state.state)
        date_str = last_state.attributes.get("accumulation_date")
        if isinstance(date_str, str):
            parsed = dt_util.parse_date(date_str)
            self._accumulation_date = parsed
        prev_str = last_state.attributes.get("previous_day_total")
        if prev_str is not None:
            with contextlib.suppress(ValueError, TypeError):
                self._previous_day_total = float(prev_str)

    today_nzt = dt_util.utcnow().astimezone(NZ_TZ).date()
    if self._accumulation_date and self._accumulation_date < today_nzt:
        self._accumulated_total = 0.0
        self._accumulation_date = today_nzt
    elif self._accumulation_date is None:
        self._accumulation_date = today_nzt
    self._native_value = self._accumulated_total
    self._attributes = {
        "accumulation_date": self._accumulation_date.isoformat(),
        "previous_day_total": self._previous_day_total,
        self._daily_meter_key: self._config.get(self._daily_meter_key),
    }
```

### Updated `_handle_coordinator_update`

Capture `_previous_day_total` snapshot before daily reset:

```python
def _handle_coordinator_update(self) -> None:
    node_data = (self.coordinator.data or {}).get(self._subentry_id)
    if not node_data or node_data.get("error"):
        self._native_value = None
        self._attributes = {}
        self.async_write_ha_state()
        return

    accounting_date: date | None = node_data.get("accounting_date_nzt")
    if accounting_date and accounting_date != self._accumulation_date:
        # Day rolled over — snapshot current total before reset
        self._previous_day_total = self._accumulated_total
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
        "previous_day_total": self._previous_day_total,
        self._daily_meter_key: self._config.get(self._daily_meter_key),
    }
    self.async_write_ha_state()
```

> **Note**: `_previous_day_total` is stored as an attribute of the daily sensor's HA state,
> so it also survives HA restarts via RestoreEntity — no separate storage mechanism needed.

---

## New: `PreviousDayImportCostSensor` and `PreviousDayExportRevenueSensor`

Both sensors use a **cross-sensor reference** to read `_previous_day_total` from their paired
daily sensor. This avoids all startup-ordering issues: the previous-day sensor reads from the
already-restored daily sensor object, not from coordinator data.

### Class structure

```python
class PreviousDayAccountingSensorBase(RestoreEntity, MarketNodeSensorBase):
    """Base for previous-day sensors that mirror a daily sensor's prior-day snapshot."""

    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: ElectricityInfoCoordinator,
        entry: ConfigEntry,
        subentry: ConfigSubentry,
        sensor_type: str,
        sensor_name: str,
        daily_sensor: DailyAccountingSensorBase,
    ) -> None:
        super().__init__(coordinator, entry, subentry, sensor_type, sensor_name)
        self._daily_sensor = daily_sensor

    async def async_added_to_hass(self) -> None:
        """Restore previous-day total; seed daily sensor if it has no prior value."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            restored = float(last_state.state)
            # Only seed daily sensor's field if it was not already restored
            if self._daily_sensor._previous_day_total is None:
                self._daily_sensor._previous_day_total = restored
        self._native_value = self._daily_sensor._previous_day_total

    def _handle_coordinator_update(self) -> None:
        prev = self._daily_sensor._previous_day_total
        if prev != self._native_value:
            self._native_value = prev
            self.async_write_ha_state()
```

> **Startup ordering note**: Both sensors are created and added in `async_setup_entry`.
> `async_added_to_hass` is called in the order entities are added. The daily sensor is
> added first; the previous-day sensor seeds back into `_daily_sensor._previous_day_total`
> only if the daily sensor didn't already restore a value from its own attributes
> (`previous_day_total` attribute persisted in 005+).

### Concrete classes

```python
class PreviousDayImportCostSensor(PreviousDayAccountingSensorBase):
    def __init__(self, coordinator, entry, subentry, daily_sensor) -> None:
        super().__init__(
            coordinator, entry, subentry,
            sensor_type="previous_day_import_cost",
            sensor_name="Previous Day Import Cost",
            daily_sensor=daily_sensor,
        )

class PreviousDayExportRevenueSensor(PreviousDayAccountingSensorBase):
    def __init__(self, coordinator, entry, subentry, daily_sensor) -> None:
        super().__init__(
            coordinator, entry, subentry,
            sensor_type="previous_day_export_revenue",
            sensor_name="Previous Day Export Revenue",
            daily_sensor=daily_sensor,
        )
```

### Sensor creation in `async_setup_entry` (platform)

```python
daily_import = DailyImportCostSensor(coordinator, entry, subentry)
prev_day_import = PreviousDayImportCostSensor(coordinator, entry, subentry, daily_import)

daily_export = DailyExportRevenueSensor(coordinator, entry, subentry)
prev_day_export = PreviousDayExportRevenueSensor(coordinator, entry, subentry, daily_export)

market_entities.extend([
    ..., daily_import, prev_day_import, daily_export, prev_day_export, ...
])
```

### `unique_id` format

Follows existing pattern: `electricityinfo_{entry_id}_{subentry_id}_{sensor_type}`

| Sensor | `sensor_type` |
|--------|--------------|
| `PreviousDayImportCostSensor` | `"previous_day_import_cost"` |
| `PreviousDayExportRevenueSensor` | `"previous_day_export_revenue"` |

---

## New: Translation Strings

### `custom_components/electricityinfo/strings.json`

Add to the flow error section:

```json
"same_entity_import_export": "Import and export meter must be different entities."
```

### `custom_components/electricityinfo/translations/en.json`

Same key and message.

---

## Sensor Platform Changes Summary

| Sensor | Status | Notes |
|--------|--------|-------|
| `SettledPriceSensor` | Unchanged | |
| `ImportCostSensor` | Unchanged | |
| `ExportRevenueSensor` | Unchanged | |
| `DailyImportCostSensor` | Changed | Adds `_previous_day_total`; stores it in HA state attributes; captures snapshot at rollover |
| `DailyExportRevenueSensor` | Changed | Same as above |
| `PreviousDayImportCostSensor` | **New** | Cross-sensor reference to `DailyImportCostSensor`; unavailable until first rollover or restore |
| `PreviousDayExportRevenueSensor` | **New** | Cross-sensor reference to `DailyExportRevenueSensor`; same behaviour |
| `LivePriceSensor` | Unchanged | |
| `ForecastSensor` variants | Unchanged | |
