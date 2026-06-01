# Tasks: Accounting Sensor Meter Entity Requirements

**Input**: Design documents from `specs/005-accounting-meter-requirements/`
**Branch**: `005-accounting-sensors`
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Data Model**: [data-model.md](data-model.md)

**Tests**: Included — TDD is NON-NEGOTIABLE per Constitution Principle IV.

**Organization**: Tasks grouped by user story. Each story is independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: Which user story this task belongs to
- All test tasks MUST fail before the corresponding implementation tasks are written

---

## Phase 1: Setup

**Purpose**: Verify baseline and shared infrastructure is clean before any changes.

- [ ] T001 Run `pytest tests/ -v` and confirm all 80 existing tests pass; record baseline in a comment
- [ ] T002 Run `ruff check custom_components/ tests/` and `mypy custom_components/` — confirm zero errors before any changes

**Checkpoint**: Baseline confirmed — implementation can proceed

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add translation error strings and verify config-flow test infrastructure. Required before any user-story validation work can be tested.

**⚠️ CRITICAL**: No user story implementation can begin until this phase is complete

- [ ] T003 Add error key `"same_entity_import_export"` to `custom_components/electricityinfo/translations/en.json` under `config_subentries.market_node.error`
- [ ] T004 Add error message `"same_entity_import_export": "Import and export meter must be different entities."` to `custom_components/electricityinfo/translations/en.json`
- [ ] T038 [P] Update the `data_description` for the import meter selector field in `custom_components/electricityinfo/translations/en.json` to read: "Requires a cumulative kWh sensor (e.g. smart meter, energy monitor) or the output of an HA Riemann sum integral helper. Utility meter helpers are not supported." (FR-010)
- [ ] T039 [P] Add the corresponding `data_description` translation in `custom_components/electricityinfo/translations/en.json` for the import meter (and export meter) selector fields to match T038 content (FR-010)

**Checkpoint**: Translation strings in place — config-flow validation changes can now be tested

---

## Phase 3: User Story 1 — Configure Import Meter for Cost Accounting (Priority: P1) 🎯 MVP

**Goal**: Tighten `_validate_meter_entity` to reject utility meter helpers (those with `last_reset` attribute), so a user with a native cumulative energy sensor or an HA Riemann sum integration helper can configure import cost accounting, while a user who accidentally selects a utility meter helper sees a clear validation error.

**Independent Test**: Configure accounting subentry with (a) an integration-helper entity and (b) a utility-meter entity; verify (a) is accepted and (b) shows `entity_not_energy_import`.

### Tests for User Story 1 ⚠️ Write these FIRST — they MUST FAIL before implementation

- [ ] T005 [P] [US1] In `tests/test_config_flow.py`: write `test_validate_meter_rejects_utility_meter_with_last_reset` — mock a sensor state with `device_class=energy`, `unit=kWh`, `last_reset="2026-06-01T00:00:00+12:00"`; assert `_validate_meter_entity(hass, entity_id)` returns `False`
- [ ] T006 [P] [US1] In `tests/test_config_flow.py`: write `test_validate_meter_accepts_riemann_sum_integration_helper` — mock a sensor state with `device_class=energy`, `unit=kWh`, no `last_reset` attribute; assert `_validate_meter_entity` returns `True`
- [ ] T007 [P] [US1] In `tests/test_config_flow.py`: write `test_validate_meter_accepts_native_cumulative_sensor` — mock a state with `device_class=energy`, `unit=kWh`, `state_class=total_increasing`, no `last_reset`; assert returns `True`

### Implementation for User Story 1

- [ ] T008 [US1] In `custom_components/electricityinfo/config_flow.py`: update `_validate_meter_entity` to add `and "last_reset" not in state.attributes` to the return condition (see data-model.md Changed: `config_flow._validate_meter_entity`)

**Checkpoint**: Run `pytest tests/test_config_flow.py -v` — T005/T006/T007 tests now pass; all prior config_flow tests still pass

---

## Phase 4: User Story 2 — Configure Bidirectional (Export/Import) Meter (Priority: P2)

**Goal**: Reject same-entity configurations at config-flow save time with a clear error message, and remove the coordinator's same-entity delta-splitting code path (replacing it with a runtime guard that logs a warning and skips accounting for legacy same-entity configs).

**Independent Test**: Submit a subentry form with import and export meter set to the same entity ID; verify `errors["base"] == "same_entity_import_export"`. Also configure separate import/export entities and verify each produces an independent delta.

### Tests for User Story 2 ⚠️ Write these FIRST — they MUST FAIL before implementation

- [ ] T009 [P] [US2] In `tests/test_config_flow.py`: write `test_same_entity_import_export_shows_base_error` — mock both import and export meter states as valid (same entity ID); submit subentry form with `enable_accounting=True`; assert `errors["base"] == "same_entity_import_export"` and form is not saved
- [ ] T010 [P] [US2] In `tests/test_config_flow.py`: write `test_same_entity_check_skipped_if_individual_validation_fails` — mock import meter with `last_reset` (fails individual check); assert `entity_not_energy_import` error is shown and `same_entity_import_export` is NOT in errors
- [ ] T011 [P] [US2] In `tests/test_coordinator.py`: write `test_coordinator_same_entity_skips_accounting_with_warning` — configure subentry with `import_meter == export_meter`; run coordinator update; assert `node_data` has no `import_cost_delta` or `export_revenue_delta` keys; assert `_LOGGER.warning` was called
- [ ] T012 [P] [US2] In `tests/test_coordinator.py`: write `test_coordinator_independent_import_export_meters_no_cross_contamination` — configure separate import and export meter entities with distinct readings; run coordinator update; assert `import_cost_delta` and `export_revenue_delta` are both present and computed independently

### Implementation for User Story 2

- [ ] T013 [US2] In `custom_components/electricityinfo/config_flow.py`: add same-entity check to `_validate_node_fields` — after individual meter validation, if `import_meter == export_meter` and neither has an individual error, set `errors["base"] = "same_entity_import_export"` (see data-model.md)
- [ ] T014 [US2] In `custom_components/electricityinfo/coordinator.py`: remove `bidirectional` variable and the `if import_meter and bidirectional:` branch from `_populate_accounting_metrics`; remove the `or import_meter` fallback from export meter assignment (see data-model.md Changed: Coordinator)
- [ ] T015 [US2] In `custom_components/electricityinfo/coordinator.py`: add runtime same-entity guard — at top of delta computation block, if `import_meter and export_meter and import_meter == export_meter`, log warning and `return` (see data-model.md Added: runtime guard)

**Checkpoint**: Run `pytest tests/test_config_flow.py tests/test_coordinator.py -v` — T009–T012 pass; existing bidirectional tests updated or removed; all other tests still pass

---

## Phase 5: User Story 4 — View Previous Day's Totals (Priority: P2)

**Goal**: After each NZT daily reset, `PreviousDayImportCostSensor` and `PreviousDayExportRevenueSensor` hold the prior day's accumulated total and persist it across HA restarts, giving users a stable single-value reference for yesterday's electricity cost and export revenue.

**Independent Test**: Simulate a daily rollover (new `accounting_date_nzt`); assert previous-day sensor updates to the prior accumulated total. Simulate HA restart; assert previous-day value is restored without data loss.

### Tests for User Story 4 ⚠️ Write these FIRST — they MUST FAIL before implementation

#### Daily sensor snapshot tests (sensor.py changes)

- [ ] T016 [P] [US4] In `tests/test_accounting.py`: write `test_daily_import_cost_captures_previous_day_total_on_rollover` — set `sensor._accumulated_total = 42.5`; inject coordinator update with a new `accounting_date_nzt`; in the **same** `_handle_coordinator_update` call assert `sensor._previous_day_total == 42.5` AND `sensor._accumulated_total == <new_delta_only>` (covers SC-007 atomicity: no intermediate poll should pass with inconsistent daily/previous-day state)
- [ ] T017 [P] [US4] In `tests/test_accounting.py`: write `test_daily_import_cost_stores_previous_day_total_in_attributes` — after rollover, assert `sensor.extra_state_attributes["previous_day_total"] == 42.5`
- [ ] T018 [P] [US4] In `tests/test_accounting.py`: write `test_daily_import_cost_restores_previous_day_total_on_restart` — simulate HA restart with `last_state.state = "10.0"` and `attributes = {"accumulation_date": today_iso, "previous_day_total": "35.0"}`; assert `sensor._previous_day_total == 35.0` after `async_added_to_hass`

#### Previous-day sensor tests (new sensor classes)

- [ ] T019 [P] [US4] In `tests/test_accounting.py`: write `test_previous_day_import_cost_unavailable_before_first_rollover` — create `PreviousDayImportCostSensor` with a fresh daily sensor (no prior state); assert `native_value is None`
- [ ] T020 [P] [US4] In `tests/test_accounting.py`: write `test_previous_day_import_cost_reflects_daily_sensor_snapshot` — set `daily_sensor._previous_day_total = 99.0`; trigger coordinator update; assert `previous_day_sensor.native_value == 99.0`
- [ ] T021 [P] [US4] In `tests/test_accounting.py`: write `test_previous_day_import_cost_unchanged_between_rollovers` — set value 42.5 via rollover; run 3 further coordinator updates with no date change; assert value stays 42.5; assert `async_write_ha_state` called only when value actually changed
- [ ] T022 [P] [US4] In `tests/test_accounting.py`: write `test_previous_day_import_cost_restores_from_own_last_state_when_daily_has_none` — fresh daily sensor (no attributes); previous-day sensor has `last_state = "88.0"`; after `async_added_to_hass`, assert `daily_sensor._previous_day_total == 88.0` and `previous_day_sensor.native_value == 88.0`
- [ ] T023 [P] [US4] In `tests/test_accounting.py`: write `test_previous_day_sensor_does_not_override_daily_sensor_restore` — daily sensor restores `_previous_day_total = 70.0` from its own attributes; previous-day sensor has `last_state = "55.0"`; assert `daily_sensor._previous_day_total` remains 70.0 (not overwritten)
- [ ] T024 [P] [US4] In `tests/test_sensor.py` or `tests/test_accounting.py`: write `test_previous_day_sensors_created_for_accounting_subentry` — call platform `async_setup_entry` with import+export meters configured; assert entity list contains `PreviousDayImportCostSensor` and `PreviousDayExportRevenueSensor` instances

### Implementation for User Story 4

- [ ] T025 [US4] In `custom_components/electricityinfo/sensor.py`: update `DailyAccountingSensorBase.__init__` to add `self._previous_day_total: float | None = None`
- [ ] T026 [US4] In `custom_components/electricityinfo/sensor.py`: update `DailyAccountingSensorBase.async_added_to_hass` to restore `_previous_day_total` from `last_state.attributes.get("previous_day_total")` using `contextlib.suppress(ValueError, TypeError)` (see data-model.md)
- [ ] T027 [US4] In `custom_components/electricityinfo/sensor.py`: update `DailyAccountingSensorBase._handle_coordinator_update` to snapshot `self._previous_day_total = self._accumulated_total` before resetting at date rollover; add `"previous_day_total": self._previous_day_total` to `self._attributes` (see data-model.md)
- [ ] T028 [US4] In `custom_components/electricityinfo/sensor.py`: implement `PreviousDayAccountingSensorBase(RestoreEntity, MarketNodeSensorBase)` with `_daily_sensor` reference, `async_added_to_hass` with conditional seeding, and value-change-gated `_handle_coordinator_update` (see data-model.md)
- [ ] T029 [US4] In `custom_components/electricityinfo/sensor.py`: implement `PreviousDayImportCostSensor(PreviousDayAccountingSensorBase)` with `sensor_type="previous_day_import_cost"` and `sensor_name="Previous Day Import Cost"` (see data-model.md)
- [ ] T030 [US4] In `custom_components/electricityinfo/sensor.py`: implement `PreviousDayExportRevenueSensor(PreviousDayAccountingSensorBase)` with `sensor_type="previous_day_export_revenue"` and `sensor_name="Previous Day Export Revenue"` (see data-model.md)
- [ ] T031 [US4] In `custom_components/electricityinfo/sensor.py`: update `async_setup_entry` (the accounting sensor creation block) to instantiate `PreviousDayImportCostSensor` paired with `daily_import` and `PreviousDayExportRevenueSensor` paired with `daily_export`; add both to `market_entities` (see data-model.md Sensor creation)

**Checkpoint**: Run `pytest tests/test_accounting.py -v` — T016–T024 all pass; all prior accounting tests still pass

---

## Phase 6: User Story 3 — Interim Price Selection and Period Alignment (Priority: P3)

**Goal**: Verify (and protect with tests) that `SettledPriceSensor` always picks the most recently settled Interim trading period whose `trading_datetime ≤ now`, never a future period. This logic is already implemented; this phase adds explicit regression tests.

**Independent Test**: Populate coordinator data with past, current, and future period prices; assert sensor reports the current (not future) period's price.

### Tests for User Story 3 ⚠️ Write these FIRST — verify they pass against existing code

- [ ] T032 [P] [US3] In `tests/test_accounting.py`: write `test_settled_price_uses_current_period_not_future` — build Interim schedule with periods at `T-30min`, `T+0min`, `T+30min`; freeze time at `T+10min`; assert `SettledPriceSensor` reports the `T+0min` price
- [ ] T033 [P] [US3] In `tests/test_accounting.py`: write `test_settled_price_unavailable_when_only_future_periods_available` — build Interim schedule with only future periods; assert `SettledPriceSensor.native_value is None`
- [ ] T040 [P] [US3] In `tests/test_accounting.py`: write `test_accounting_sensors_unavailable_on_api_error` — mock coordinator fetch to raise an exception or return empty Interim data; run coordinator update; assert `SettledPriceSensor`, `ImportCostSensor`, and `ExportRevenueSensor` all have `native_value is None` or state `STATE_UNAVAILABLE` (SC-005 full coverage)

### Implementation for User Story 3

- [ ] T034 [US3] Review `coordinator._populate_accounting_metrics` price-selection logic against the three new tests (T032, T033, T040); no code change expected if tests pass — mark complete after confirming

**Checkpoint**: Run `pytest tests/test_accounting.py -v` — T032/T033 pass; existing settled-price tests still pass

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T035 [P] **README update** — Update `README.md`: add `PreviousDayImportCostSensor` and `PreviousDayExportRevenueSensor` to sensor entity table; update meter selector description (mention `last_reset` rejection and the two-template-helper bidirectional pattern; state utility meter helpers are not supported; remove any mention of same-entity bidirectional shortcut). *Mandatory per Principle VI — block merge if skipped.*
- [ ] T036 [P] Bump MINOR version in `custom_components/electricityinfo/manifest.json` (e.g. `2.1.0` → `2.2.0`) to reflect new sensors added
- [ ] T037 Run full validation: `pytest tests/ -v` (target ≥ 88 tests passing), `ruff check custom_components/ tests/`, `mypy custom_components/` — all must be clean before merge

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user story phases
- **Phase 3 (US1)**: Depends on Phase 2 — can start after translations added
- **Phase 4 (US2)**: Depends on Phase 2 — can start after Phase 2; independent of Phase 3
- **Phase 5 (US4)**: Depends on Phase 3 — `_previous_day_total` requires daily sensor changes from US1
- **Phase 6 (US3)**: Depends on Phase 2 — independent of US1/US2/US4
- **Phase 7 (Polish)**: Depends on all prior phases complete

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no story dependencies
- **US2 (P2)**: After Phase 2 — no story dependencies (coordinator change independent of US1)
- **US4 (P2)**: After US1 (Phase 3) — depends on daily sensor `_previous_day_total` attribute added in T025–T027
- **US3 (P3)**: After Phase 2 — no story dependencies (verification only)

### Within Each Phase

1. Write ALL test tasks for the phase first
2. Run tests and confirm they **FAIL** (red)
3. Implement tasks in order
4. Run tests — confirm they **PASS** (green)
5. Commit before proceeding to next phase

---

## Parallel Opportunities

### Phase 3 + Phase 4 + Phase 6 can run in parallel after Phase 2

```bash
# These phases are independent — can be worked simultaneously:
Phase 3: T005, T006, T007 (write tests) → T008 (implement)
Phase 4: T009, T010, T011, T012 (write tests) → T013, T014, T015 (implement)
Phase 6: T032, T033 (write tests) → T034 (verify)
```

### Within Phase 5, all test-write tasks are parallel

```bash
# All can be written simultaneously (different test functions, same file):
T016, T017, T018  (daily sensor snapshot tests)
T019, T020, T021, T022, T023, T024  (previous-day sensor tests)
```

### Phase 7 parallel tasks

```bash
T035 (README)  +  T036 (version bump)  — different files, no dependency
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003–T004)
3. Complete Phase 3: US1 — import meter validation (T005–T008)
4. **STOP and VALIDATE**: `pytest tests/test_config_flow.py -v` passes
5. Merge if import-cost-only accounting improvements are sufficient

### Incremental Delivery

1. Phase 1 + Phase 2 → Foundation ready
2. Phase 3 (US1) → Import meter validation improved → testable
3. Phase 4 (US2) → Same-entity rejection + bidirectional removal → testable
4. Phase 5 (US4) → Previous-day sensors → testable
5. Phase 6 (US3) → Interim price regression coverage → testable
6. Phase 7 → README + version bump → merge-ready

---

## Notes

- `[P]` tasks = different files or independent functions — no conflicts
- Constitution Principle IV (TDD) is NON-NEGOTIABLE: tests MUST fail before implementation
- Constitution Principle VI: T035 README update is mandatory before merge
- `_previous_day_total` is stored in HA state attributes — no external storage needed
- Runtime guard (T015) protects users with legacy same-entity configs from silent miscalculation
- Each `PreviousDayXxxSensor` holds a Python reference to its paired `DailyXxxSensor` — set at entity creation time in `async_setup_entry`
- Version bump target: check current version in `manifest.json` and increment MINOR digit
