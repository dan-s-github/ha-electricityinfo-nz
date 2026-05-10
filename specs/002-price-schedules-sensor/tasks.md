# Tasks: Electricity Price Schedules Sensor Platform

**Input**: Design documents from `/specs/002-price-schedules-sensor/`
**Prerequisites**: `plan.md` (required), `spec.md` (required), `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Included. The feature specification explicitly requires mocked CI tests plus integration/manual verification.

**Organization**: Tasks are grouped by user story to support independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Task can run in parallel (different files, no unmet dependencies)
- **[Story]**: User story label (`[US1]`, `[US2]`, `[US3]`, `[US4]`) for story phases only
- Every task includes an exact file path

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare constants, fixtures, helpers, and localization scaffolding.

- [ ] T001 Add or align schedule/market/node constants and conversion constants in `custom_components/electricityinfo/const.py`
- [ ] T002 Add or align subentry flow translation keys in `custom_components/electricityinfo/translations/en.json`
- [ ] T003 [P] Add or refresh mocked market price fixture data in `tests/fixtures/market_prices.json`
- [ ] T004 [P] Add or refresh shared pytest fixtures in `tests/conftest.py`
- [ ] T005 [P] Add or refresh subentry/coordinator helper utilities in `tests/helpers.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core architecture that must exist before user story implementation.

**CRITICAL**: User story work begins only after this phase is complete.

- [ ] T006 Implement coordinator class skeleton and update interval setup in `custom_components/electricityinfo/coordinator.py`
- [ ] T007 Implement coordinator fetch loop for sensor subentries in `custom_components/electricityinfo/coordinator.py`
- [ ] T008 Implement retry/backoff and update failure handling in `custom_components/electricityinfo/coordinator.py`
- [ ] T009 Wire coordinator lifecycle and reload listener in `custom_components/electricityinfo/__init__.py`
- [ ] T010 Add supported sensor subentry type registration in `custom_components/electricityinfo/config_flow.py`

**Checkpoint**: Foundation complete; user stories can be implemented and tested.

---

## Phase 3: User Story 1 - Configure Single Price Sensor (Priority: P1)

**Goal**: Allow users to create and reconfigure one sensor subentry and get working entities.

**Independent Test**: Create one sensor subentry from integration options and verify two entities appear and update.

### Tests for User Story 1

- [x] T011 [P] [US1] Add subentry create path test coverage in `tests/test_options_flow.py`
- [x] T012 [P] [US1] Add subentry reconfigure path test coverage in `tests/test_options_flow.py`
- [x] T013 [P] [US1] Add single-subentry platform setup test coverage in `tests/test_sensor.py`
- ~~[ ] T014 [P] [US1] Add restore-state regression coverage in `tests/test_sensor.py`~~ *(superseded by T050)*

### Implementation for User Story 1

- [x] T015 [US1] Implement sensor title derivation for subentry labels in `custom_components/electricityinfo/config_flow.py`
- [x] T016 [US1] Implement subentry form schema (name, schedule, market, node, forward hours) in `custom_components/electricityinfo/config_flow.py`
- [x] T017 [US1] Implement create/reconfigure subentry handlers in `custom_components/electricityinfo/config_flow.py`
- [x] T018 [US1] Implement sensor entity base properties and IDs in `custom_components/electricityinfo/sensor.py`
- [x] T019 [US1] Implement entity setup per subentry with `config_subentry_id` linkage in `custom_components/electricityinfo/sensor.py`
- [x] T020 [US1] Implement restore and coordinator update handling for entity state/attributes in `custom_components/electricityinfo/sensor.py`

**Checkpoint**: User Story 1 is functional and independently testable.

---

## Phase 4: User Story 4 - Handle Update Failures Gracefully (Priority: P1)

**Goal**: Ensure unavailable/recovery behavior is robust under API/auth/network failures.

**Independent Test**: Simulate repeated update failures and verify unavailable transition plus automatic recovery.

### Tests for User Story 4

- ~~[ ] T021 [P] [US4] Add coordinator retry/backoff unit coverage in `tests/test_integration.py`~~ *(superseded by T051)*
- ~~[ ] T022 [P] [US4] Add unavailable-to-recovery lifecycle integration test in `tests/integration/test_sensor_lifecycle.py`~~ *(superseded by T052)*
- [x] T023 [P] [US4] Add partial/missing payload isolation behavior test in `tests/test_sensor_multiple.py`

### Implementation for User Story 4

- [x] T024 [US4] Implement per-sensor error capture during API fetch in `custom_components/electricityinfo/coordinator.py`
- [x] T025 [US4] Implement coordinator-level auth/update failure propagation in `custom_components/electricityinfo/coordinator.py`
- [x] T026 [US4] Implement entity availability logic from coordinator and sensor-level error state in `custom_components/electricityinfo/sensor.py`

**Checkpoint**: User Story 4 is functional and independently testable.

---

## Phase 5: User Story 2 - Configure Multiple Price Sensors (Priority: P2)

**Goal**: Support multiple sensor subentries with independent updates and isolated failures.

**Independent Test**: Configure at least two subentries with different values and verify unique entities and isolated behavior.

### Tests for User Story 2

- [x] T027 [P] [US2] Add multi-subentry options-flow behavior tests in `tests/test_options_flow.py`
- [x] T028 [P] [US2] Add unique entity ID and multi-sensor setup tests in `tests/test_sensor_multiple.py`
- [x] T029 [P] [US2] Add coordinator multi-subentry update isolation tests in `tests/test_sensor_multiple.py`

### Implementation for User Story 2

- [x] T030 [US2] Ensure coordinator iterates all sensor subentries and persists per-subentry payloads in `custom_components/electricityinfo/coordinator.py`
- [x] T031 [US2] Ensure entity identifiers and device identifiers are collision-safe per subentry in `custom_components/electricityinfo/sensor.py`
- [x] T032 [US2] Ensure subentry UX labels remain distinguishable across multiple configured sensors in `custom_components/electricityinfo/config_flow.py`

**Checkpoint**: User Story 2 is functional and independently testable.

---

## Phase 6: User Story 3 - View Dual Unit Sensors (Priority: P2)

**Goal**: Provide both NZD/MWh and c/kWh entities for each configured subentry.

**Independent Test**: For one subentry, verify both entities exist, use correct units, and remain synchronized on updates.

### Tests for User Story 3

- [x] T033 [P] [US3] Add dual-unit entity creation and unit metadata tests in `tests/test_unit_conversion.py`
- [x] T034 [P] [US3] Add NZD-to-c conversion and rounding behavior tests in `tests/test_unit_conversion.py`
- ~~[ ] T035 [P] [US3] Add dual-unit update synchronization tests in `tests/test_sensor.py`~~ *(superseded by T053)*

### Implementation for User Story 3

- [x] T036 [US3] Ensure dual-entity creation per subentry (NZD/MWh and c/kWh) in `custom_components/electricityinfo/sensor.py`
- [x] T037 [US3] Ensure c/kWh state and forecast attribute conversion logic is applied consistently in `custom_components/electricityinfo/sensor.py`
- [x] T038 [US3] Ensure entity naming and device presentation match subentry/unit model in `custom_components/electricityinfo/sensor.py`

**Checkpoint**: User Story 3 is functional and independently testable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Complete artifact reconciliation, quality gates, and release readiness.

- [x] T039 Reconcile subentry-based UX contract in `specs/002-price-schedules-sensor/contracts/config-flow.md`
- [x] T040 Reconcile dual-entity lifecycle contract in `specs/002-price-schedules-sensor/contracts/sensor-platform.md`
- [x] T041 Reconcile subentry storage/entity definitions in `specs/002-price-schedules-sensor/data-model.md`
- [x] T042 Reconcile quickstart paths and workflows in `specs/002-price-schedules-sensor/quickstart.md`
- [x] T043 Reconcile task completion claims and stale references in `specs/002-price-schedules-sensor/tasks.md`
- [ ] T044 [P] Run linting in `custom_components/electricityinfo/` and `tests/` using `ruff check --fix`
- [ ] T045 [P] Run type checking for integration modules in `custom_components/electricityinfo/` using `mypy custom_components/`
- [ ] T046 [P] Run full test suite in `tests/` using `pytest tests/ -v`
- [ ] T047 Update release notes for reconciled behavior in `CHANGELOG.md`
- [x] T048 Run cross-artifact consistency check and capture outcomes in `specs/002-price-schedules-sensor/`

---

## Remediation: Gaps

**Source**: Gap report 2026-05-09 — implementation vs spec-kit artifact audit.

- [x] T050 [P] [US1] Write restore-state regression test: verify `_native_value` populated and `native_value` returns restored value post-`async_added_to_hass`; verify c/kWh back-conversion; verify SC-008 availability behavior in `tests/test_sensor.py` [Sync: Gap Report]
- [x] T049 [P] Fix `available` property to return `True` when `_native_value` is set but `coordinator.data` is `None` (pre-fetch restored state) in `custom_components/electricityinfo/sensor.py` [Sync: Gap Report] *(depends-on: T050 — write failing test first)*
- [x] T051 [P] [US4] Write coordinator retry/backoff unit tests: assert `_retry_count` increments and `update_interval` grows after each `UpdateFailed`; assert `last_update_success` False after `MAX_RETRIES` in `tests/test_integration.py` [Sync: Gap Report]
- [x] T052 [US4] Create unavailable-to-recovery lifecycle integration test: coordinator fails twice → entities unavailable → coordinator succeeds → entities available in `tests/integration/test_sensor_lifecycle.py` [Sync: Gap Report]
- [x] T053 [P] [US3] Write dual-unit update synchronisation test: assert NZD/MWh and c/kWh entities reflect same underlying data after `_handle_coordinator_update` in `tests/test_sensor.py` [Sync: Gap Report]
- [x] T054 [P] [US1] Write `prices_array` dict structure shape test: assert each element contains keys `trading_date`, `trading_period`, `price`; assert c/kWh entity converts `price` × 0.1 in `tests/test_sensor.py` [Sync: Gap Report]
- [x] T055 [P] [US3] Write c/kWh `prices_array` conversion test: assert `extra_state_attributes["prices_array"]` prices are multiplied by `NZD_PER_MWH_TO_C_PER_KWH` for c/kWh entity in `tests/test_unit_conversion.py` [Sync: Gap Report]

---

## Migration: Forecast Format (forecast_solar convention)

**Source**: Spec revision 2026-05-09 — FR-006 updated to replace `prices_array` with `forecast` attribute using `{period_start: ISO8601+tz, price: float}` element shape, compatible with the `forecast_solar` integration.

**TDD ordering**: T056–T057 (write RED tests) → T058–T060 (implement, makes T056/T057 GREEN and T054/T055 RED) → T061–T062 (update old tests) → T063 (contract update).

- [x] T056 [P] [US1] Write failing `forecast` attribute shape test: assert `extra_state_attributes["forecast"]` is a list of `{period_start, price}` dicts for a NZD/MWh entity; assert `period_start` is an ISO 8601 string with timezone; assert no `prices_array` key present in `tests/test_sensor.py` [Migration: forecast-solar format]
- [x] T057 [P] [US3] Write failing `forecast` c/kWh conversion test: assert `extra_state_attributes["forecast"][0]["price"]` equals NZD/MWh price × 0.1 for a c/kWh entity; assert no `prices_array` key in `tests/test_unit_conversion.py` [Migration: forecast-solar format]
- [x] T058 [US1] Rename `prices_array` → `forecast` in `_handle_coordinator_update`; change element shape from `{trading_date, trading_period, price}` to `{period_start: p.trading_datetime.isoformat(), price: round(p.price, 3)}` in `custom_components/electricityinfo/sensor.py` [Migration: forecast-solar format] *(depends-on: T056, T057)*
- [x] T059 [US3] Update `extra_state_attributes` to apply c/kWh conversion on `forecast` key (not `prices_array`): convert each element's `price` by `* NZD_PER_MWH_TO_C_PER_KWH` in `custom_components/electricityinfo/sensor.py` [Migration: forecast-solar format] *(depends-on: T058)*
- [x] T060 [US1] Update `async_added_to_hass` restore logic to reverse-convert `forecast` (not `prices_array`) for c/kWh entities: multiply `price` by `C_PER_KWH_TO_NZD_PER_MWH` in `custom_components/electricityinfo/sensor.py` [Migration: forecast-solar format] *(depends-on: T059)*
- [x] T061 [P] [US1] Update existing T054 tests to assert `forecast` attribute shape (not `prices_array`): update mock assertions to use `period_start`/`price` keys and verify ISO8601 timezone format in `tests/test_sensor.py` [Migration: forecast-solar format] *(depends-on: T058)*
- [x] T062 [P] [US3] Update existing T055 test to assert `forecast` c/kWh conversion (not `prices_array`): rename attribute reference and verify price conversion in `tests/test_unit_conversion.py` [Migration: forecast-solar format] *(depends-on: T059)*
- [x] T063 [P] Update `contracts/sensor-platform.md` to replace `prices_array` attribute definition with `forecast` attribute: element shape `{period_start: ISO8601+tz, price: float in entity unit}`, include example JSON in `specs/002-price-schedules-sensor/contracts/sensor-platform.md` [Migration: forecast-solar format] *(depends-on: T060)*

---

## Spec Revision: Forecast Excludes Current Period

**Source**: Spec revision 2026-05-09 — FR-006 updated: the `forecast` attribute must contain **future periods only**. The current trading period price is the sensor state; it must not appear in `forecast`. This mirrors `forecast_solar` convention exactly.

**TDD ordering**: T068 (RED test) → T069 (implement slice) → T070 (update existing forecast tests).

- [x] T068 [P] [US1] Write failing test: assert `extra_state_attributes["forecast"][0]["period_start"]` is strictly after the current period's `timestamp`; assert `forecast` does not contain an entry matching the current state's price/period in `tests/test_sensor.py` [Forecast: exclude-current]
- [x] T069 [US1] Update `_handle_coordinator_update` to slice the API price list from index 1 onwards when building `forecast` (index 0 = current period = sensor state, not included in forecast list) in `custom_components/electricityinfo/sensor.py` [Forecast: exclude-current] *(depends-on: T068)*
- [x] T070 [P] Update existing forecast shape tests (T056/T061) to assert `forecast[0]` is the **second** API price period, not the first; verify `len(forecast) == forward_prices_count - 1` in `tests/test_sensor.py` [Forecast: exclude-current] *(depends-on: T069)*

---

## Staleness Guard: SC-008 Restore Threshold

**Source**: Spec clarification 2026-05-09 — FR-007 and SC-008 updated to discard restored state older than one update interval (30 minutes). If the restored `timestamp` attribute is older than 30 minutes, `async_added_to_hass` must NOT populate `_native_value`; entity remains unavailable until the first coordinator fetch succeeds.

**TDD ordering**: T064–T065 (write RED tests) → T066 (implement staleness check, makes T064 GREEN) → T067 (boundary regression).

- [x] T064 [P] [US1] Write failing test: assert entity `available` is `False` and `native_value` is `None` when restored `timestamp` attribute is >30 minutes old; mock `dt_util.utcnow()` to simulate stale state in `tests/test_sensor.py` [Staleness: SC-008]
- [x] T065 [P] [US1] Write passing test: assert entity `available` is `True` and `native_value` is restored when `timestamp` is within 30 minutes and `coordinator.data` is `None` (fresh-restore, pre-fetch window) in `tests/test_sensor.py` [Staleness: SC-008]
- [x] T066 [US1] Implement staleness check in `async_added_to_hass`: parse `last_state.attributes["timestamp"]` as ISO 8601 datetime via `dt_util.parse_datetime`, compare age to `UPDATE_INTERVAL` (30 min) via `dt_util.utcnow()`; skip restore (leave `_native_value = None`) when stale in `custom_components/electricityinfo/sensor.py` [Staleness: SC-008] *(depends-on: T064, T065)*
- [x] T067 [P] [US1] Add boundary regression: assert entity restores at exactly 30 min old (boundary is available) and discards at 30 min + 1 second old (boundary is unavailable) in `tests/test_sensor.py` [Staleness: SC-008] *(depends-on: T066)*

---

## Dependencies & Execution Order (updated)

### Forecast Exclude-Current Phase Dependencies

- T068: No dependencies — write RED test first
- T069: Depends on T068 written
- T070: Depends on T069 (update tests after implementation)
- T068 is [P] with T064/T065 — different test functions, non-overlapping

### Staleness Guard Phase Dependencies

- T064, T065: No dependencies — write RED tests first
- T066: Depends on T064, T065 written (TDD: implement after tests)
- T067: Depends on T066 (boundary regression after implementation)
- T064 and T065 are [P] — same file but non-overlapping test functions

### Migration Phase Dependencies

- T056, T057: No dependencies — write these first (RED tests)
- T058: Depends on T056, T057 being written
- T059: Depends on T058 (same file, sequential)
- T060: Depends on T059 (same file, sequential)
- T061, T062: Depend on T058–T060 (fix tests broken by implementation change)
- T063: Depends on T060 (document final behaviour)

### Parallel Opportunities (Migration)

- T056 and T057 are [P] — different test files, write concurrently
- T061 and T062 are [P] — different test files, update concurrently after T058–T060
- T063 is [P] with T061/T062 — spec doc, no code dependency

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Foundational)**: Depends on Phase 1; blocks all user stories
- **Phase 3 (US1)**: Depends on Phase 2
- **Phase 4 (US4)**: Depends on Phase 2; can run parallel with US1 once foundations are complete
- **Phase 5 (US2)**: Depends on Phase 2
- **Phase 6 (US3)**: Depends on Phase 2
- **Phase 7 (Polish)**: Depends on completion of selected user stories

### User Story Completion Order

1. **US1 (P1)** Configure single sensor subentry
2. **US4 (P1)** Failure handling and recovery
3. **US2 (P2)** Multiple subentries
4. **US3 (P2)** Dual unit entity behavior

### Story Dependency Graph

- US1 and US4 both require Phase 2 foundations.
- US2 depends on the same foundations and benefits from US1 entity flow completion.
- US3 depends on US1 entity setup and conversion constants.

---

## Parallel Execution Examples

### User Story 1

- Parallel tests: T011, T012, T013, T014
- Parallel-safe implementation split: T016 and T018 can proceed concurrently after T015 decisions are fixed

### User Story 4

- Parallel tests: T023 (T021 and T022 superseded by T051, T052)
- Parallel-safe implementation split: T024 and T026 can run concurrently once retry policy in T025 is established

### User Story 2

- Parallel tests: T027, T028, T029
- Parallel-safe implementation split: T031 and T032 can run concurrently after T030 baseline

### User Story 3

- Parallel tests: T033, T034 (T035 superseded by T053)
- Parallel-safe implementation split: T037 and T038 can run concurrently after T036

---

## Implementation Strategy

### MVP First (Recommended)

1. Complete Phase 1 and Phase 2
2. Complete Phase 3 (US1)
3. Complete Phase 4 (US4)
4. Validate with targeted tests before expanding scope

### Incremental Delivery

1. Deliver US1 + US4 first (core value and reliability)
2. Add US2 for scale and isolation
3. Add US3 for dual-unit UX completeness
4. Finish with Phase 7 reconciliation and quality gates

---

## Notes

- Tasks use strict checklist format with IDs, labels, and exact file paths.
- Tests are included because the feature specification explicitly requires test coverage.
- Story phases are independently testable increments.
- Run lint/type/test checks before claiming completion.
