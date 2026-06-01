# Quickstart: Accounting Sensor Meter Entity Requirements

**Branch**: `005-accounting-sensors` | **Date**: 2026-06-01

---

## Developer Setup

```bash
# Install all dependencies (including dev group)
uv sync

# Run full test suite (mocked API — no credentials needed)
pytest tests/ -v

# Run linter + auto-fix
ruff check --fix custom_components/ tests/

# Run type checker
mypy custom_components/

# Run live API tests (requires .env with ELECTRICITY_CLIENT_ID + ELECTRICITY_CLIENT_SECRET)
pytest tests/live/ -v -m live_api
```

**Prerequisites**: Python 3.14+, `uv` installed. Baseline: 80 tests passing.

---

## Key Design Invariants

- **Daily sensors still own accumulation**: `_accumulated_total` and `_accumulation_date` remain on the sensor; no coordinator seeding needed. At day rollover, `_previous_day_total = _accumulated_total` is captured before reset.
- **Previous-day sensors use cross-sensor reference**: `PreviousDayImportCostSensor` holds a reference to its paired `DailyImportCostSensor` and reads `daily_sensor._previous_day_total`. No coordinator data needed; no startup ordering issues.
- **`_previous_day_total` is persisted via daily sensor attributes**: stored as `"previous_day_total"` in HA state attributes, so it survives restarts without a separate storage mechanism.
- **Restore ordering**: `DailyImportCostSensor.async_added_to_hass` restores `_previous_day_total` from its own attributes. `PreviousDayImportCostSensor.async_added_to_hass` seeds `daily_sensor._previous_day_total` only if it is still None.
- **Runtime guard for legacy same-entity configs**: coordinator logs a warning and skips accounting for subentries where `import_meter == export_meter`. Config-flow validation prevents new same-entity saves; runtime guard protects existing saved configs.
- **Previous-day sensor state writes are value-change-gated**: `_handle_coordinator_update` calls `async_write_ha_state()` only when value changes. No unnecessary churn between rollovers.
- **Same-entity check fires after individual validation**: only raises `same_entity_import_export` if both meters individually pass `_validate_meter_entity`.

---

## Implementation Phases

### Phase 1 — Config Flow Validation (test-first)

Write tests in `tests/test_config_flow.py` **before** modifying `config_flow.py`:

- `test_validate_meter_rejects_utility_meter_with_last_reset`: mock entity state with `device_class=energy`, `unit=kWh`, `last_reset=...`; assert `_validate_meter_entity` returns `False`.
- `test_validate_meter_accepts_integration_helper`: mock entity state with `device_class=energy`, `unit=kWh`, no `last_reset`; assert returns `True`.
- `test_same_entity_import_export_shows_error`: mock valid import + export entity states (same entity ID); submit subentry form; assert `errors["base"] == "same_entity_import_export"`.
- `test_same_entity_check_skipped_if_individual_validation_fails`: mock entity with `last_reset`; assert individual error shown, `same_entity_import_export` NOT raised.

Then update `config_flow.py`:
1. In `_validate_meter_entity`: add `and "last_reset" not in state.attributes`.
2. In `_validate_node_fields`: add same-entity check after individual meter checks (see data-model.md).

Then add `"same_entity_import_export"` to `strings.json` and `translations/en.json`.

---

### Phase 2 — Coordinator Runtime Guard (test-first)

Write tests in `tests/test_coordinator.py` **before** modifying `coordinator.py`:

- `test_coordinator_same_entity_skips_accounting`: configure subentry with `import_meter == export_meter`; run coordinator update; assert `node_data` has no `import_cost_delta`, `export_revenue_delta` keys; assert warning logged.
- `test_coordinator_independent_meters_produce_independent_deltas`: configure separate import and export meter entities; run coordinator update; assert both produce independent deltas without cross-contamination.

Update existing tests that relied on the bidirectional same-entity branch (remove or update any tests that set `import_meter == export_meter` and expected bidirectional delta splitting).

Then update `coordinator.py`:
1. Remove `bidirectional` variable and the `if bidirectional:` branch.
2. Remove `or import_meter` fallback from export meter assignment.
3. Add runtime same-entity guard at top of delta computation (log warning, return early; see data-model.md).

---

### Phase 3 — Daily Sensor `_previous_day_total` (test-first)

Write tests in `tests/test_accounting.py` **before** modifying `sensor.py`:

- `test_daily_import_cost_captures_previous_day_total_on_rollover`: set `_accumulated_total = 42.5`; inject coordinator update with new `accounting_date_nzt`; assert `_previous_day_total == 42.5` and `_accumulated_total == <new_delta>`.
- `test_daily_import_cost_previous_day_total_stored_in_attributes`: after rollover, assert `sensor.extra_state_attributes["previous_day_total"] == 42.5`.
- `test_daily_import_cost_restores_previous_day_total_on_restart`: simulate HA restart with last_state having `state=10.0` and `attributes={"accumulation_date": today, "previous_day_total": 35.0}`; assert `sensor._previous_day_total == 35.0`.

Then update `sensor.py`:
1. Add `self._previous_day_total: float | None = None` to `DailyAccountingSensorBase.__init__`.
2. Update `async_added_to_hass` to restore `_previous_day_total` from `last_state.attributes["previous_day_total"]`.
3. Update `_handle_coordinator_update` to snapshot `_previous_day_total = _accumulated_total` before date reset (see data-model.md).
4. Add `"previous_day_total": self._previous_day_total` to `self._attributes`.

---

### Phase 4 — Previous-Day Sensor Classes (test-first)

Write tests in `tests/test_accounting.py` **before** adding sensor classes:

- `test_previous_day_import_cost_unavailable_before_first_rollover`: create sensor with fresh daily sensor (no prior state); assert `native_value is None`.
- `test_previous_day_import_cost_reflects_daily_sensor_previous_day_total`: set `daily_sensor._previous_day_total = 99.0`; trigger coordinator update; assert `previous_day_sensor.native_value == 99.0`.
- `test_previous_day_import_cost_unchanged_between_rollovers`: set value 42.5 via rollover; run 3 more coordinator updates with no date change; assert value stays 42.5; assert `async_write_ha_state` called only when value changed.
- `test_previous_day_import_cost_restores_from_own_last_state`: simulate HA restart, fresh daily sensor (no attributes), previous-day sensor has last_state `88.0`; assert `daily_sensor._previous_day_total == 88.0` (seeded); assert `previous_day_sensor.native_value == 88.0`.
- `test_previous_day_import_cost_does_not_override_daily_sensor_restore`: daily sensor restores `_previous_day_total = 70.0` from its own attributes; previous-day sensor has last_state `55.0`; assert daily sensor's field stays 70.0 (previous-day sensor does not overwrite).
- `test_previous_day_and_daily_sensors_created_for_accounting_subentry`: call `async_setup_entry`; assert both `PreviousDayImportCostSensor` and `PreviousDayExportRevenueSensor` are present in entity list.

Then add to `sensor.py`:
1. `PreviousDayAccountingSensorBase(RestoreEntity, MarketNodeSensorBase)` (see data-model.md).
2. `PreviousDayImportCostSensor(PreviousDayAccountingSensorBase)`.
3. `PreviousDayExportRevenueSensor(PreviousDayAccountingSensorBase)`.
4. Update `async_setup_entry` to create previous-day sensor instances paired with their daily counterparts (see data-model.md).

---

### Phase 5 — README Update (Principle VI — mandatory before merge)

Update `README.md`:
- Add `PreviousDayImportCostSensor` and `PreviousDayExportRevenueSensor` to the sensor entity list with descriptions.
- Update meter entity selector description: mention `last_reset` rejection and the two-helper bidirectional pattern.
- Add note that utility meter helpers are not supported.
- Remove any mention of the same-entity bidirectional shortcut.

---

### Phase 6 — Final Validation

```bash
# All tests must pass (target: ≥ 88 tests, up from 80)
pytest tests/ -v

# Zero ruff errors
ruff check custom_components/ tests/

# Zero mypy errors
mypy custom_components/
```

Verify:
- [ ] All 80 existing tests still pass
- [ ] New tests for validation, coordinator guard, sensor rollover, previous-day sensors all green
- [ ] `ruff` clean
- [ ] `mypy` clean
- [ ] README updated with new sensor entities and revised meter guidance
