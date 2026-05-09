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

- [ ] T011 [P] [US1] Add subentry create path test coverage in `tests/test_options_flow.py`
- [ ] T012 [P] [US1] Add subentry reconfigure path test coverage in `tests/test_options_flow.py`
- [ ] T013 [P] [US1] Add single-subentry platform setup test coverage in `tests/test_sensor.py`
- ~~[ ] T014 [P] [US1] Add restore-state regression coverage in `tests/test_sensor.py`~~ *(superseded by T050)*

### Implementation for User Story 1

- [ ] T015 [US1] Implement sensor title derivation for subentry labels in `custom_components/electricityinfo/config_flow.py`
- [ ] T016 [US1] Implement subentry form schema (name, schedule, market, node, forward hours) in `custom_components/electricityinfo/config_flow.py`
- [ ] T017 [US1] Implement create/reconfigure subentry handlers in `custom_components/electricityinfo/config_flow.py`
- [ ] T018 [US1] Implement sensor entity base properties and IDs in `custom_components/electricityinfo/sensor.py`
- [ ] T019 [US1] Implement entity setup per subentry with `config_subentry_id` linkage in `custom_components/electricityinfo/sensor.py`
- [ ] T020 [US1] Implement restore and coordinator update handling for entity state/attributes in `custom_components/electricityinfo/sensor.py`

**Checkpoint**: User Story 1 is functional and independently testable.

---

## Phase 4: User Story 4 - Handle Update Failures Gracefully (Priority: P1)

**Goal**: Ensure unavailable/recovery behavior is robust under API/auth/network failures.

**Independent Test**: Simulate repeated update failures and verify unavailable transition plus automatic recovery.

### Tests for User Story 4

- ~~[ ] T021 [P] [US4] Add coordinator retry/backoff unit coverage in `tests/test_integration.py`~~ *(superseded by T051)*
- ~~[ ] T022 [P] [US4] Add unavailable-to-recovery lifecycle integration test in `tests/integration/test_sensor_lifecycle.py`~~ *(superseded by T052)*
- [ ] T023 [P] [US4] Add partial/missing payload isolation behavior test in `tests/test_sensor_multiple.py`

### Implementation for User Story 4

- [ ] T024 [US4] Implement per-sensor error capture during API fetch in `custom_components/electricityinfo/coordinator.py`
- [ ] T025 [US4] Implement coordinator-level auth/update failure propagation in `custom_components/electricityinfo/coordinator.py`
- [ ] T026 [US4] Implement entity availability logic from coordinator and sensor-level error state in `custom_components/electricityinfo/sensor.py`

**Checkpoint**: User Story 4 is functional and independently testable.

---

## Phase 5: User Story 2 - Configure Multiple Price Sensors (Priority: P2)

**Goal**: Support multiple sensor subentries with independent updates and isolated failures.

**Independent Test**: Configure at least two subentries with different values and verify unique entities and isolated behavior.

### Tests for User Story 2

- [ ] T027 [P] [US2] Add multi-subentry options-flow behavior tests in `tests/test_options_flow.py`
- [ ] T028 [P] [US2] Add unique entity ID and multi-sensor setup tests in `tests/test_sensor_multiple.py`
- [ ] T029 [P] [US2] Add coordinator multi-subentry update isolation tests in `tests/test_sensor_multiple.py`

### Implementation for User Story 2

- [ ] T030 [US2] Ensure coordinator iterates all sensor subentries and persists per-subentry payloads in `custom_components/electricityinfo/coordinator.py`
- [ ] T031 [US2] Ensure entity identifiers and device identifiers are collision-safe per subentry in `custom_components/electricityinfo/sensor.py`
- [ ] T032 [US2] Ensure subentry UX labels remain distinguishable across multiple configured sensors in `custom_components/electricityinfo/config_flow.py`

**Checkpoint**: User Story 2 is functional and independently testable.

---

## Phase 6: User Story 3 - View Dual Unit Sensors (Priority: P2)

**Goal**: Provide both NZD/MWh and c/kWh entities for each configured subentry.

**Independent Test**: For one subentry, verify both entities exist, use correct units, and remain synchronized on updates.

### Tests for User Story 3

- [ ] T033 [P] [US3] Add dual-unit entity creation and unit metadata tests in `tests/test_unit_conversion.py`
- [ ] T034 [P] [US3] Add NZD-to-c conversion and rounding behavior tests in `tests/test_unit_conversion.py`
- ~~[ ] T035 [P] [US3] Add dual-unit update synchronization tests in `tests/test_sensor.py`~~ *(superseded by T053)*

### Implementation for User Story 3

- [ ] T036 [US3] Ensure dual-entity creation per subentry (NZD/MWh and c/kWh) in `custom_components/electricityinfo/sensor.py`
- [ ] T037 [US3] Ensure c/kWh state and prices_array conversion logic is applied consistently in `custom_components/electricityinfo/sensor.py`
- [ ] T038 [US3] Ensure entity naming and device presentation match subentry/unit model in `custom_components/electricityinfo/sensor.py`

**Checkpoint**: User Story 3 is functional and independently testable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Complete artifact reconciliation, quality gates, and release readiness.

- [x] T039 Reconcile subentry-based UX contract in `specs/002-price-schedules-sensor/contracts/config-flow.md`
- [x] T040 Reconcile dual-entity lifecycle contract in `specs/002-price-schedules-sensor/contracts/sensor-platform.md`
- [ ] T041 Reconcile subentry storage/entity definitions in `specs/002-price-schedules-sensor/data-model.md`
- [ ] T042 Reconcile quickstart paths and workflows in `specs/002-price-schedules-sensor/quickstart.md`
- [ ] T043 Reconcile task completion claims and stale references in `specs/002-price-schedules-sensor/tasks.md`
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

## Dependencies & Execution Order

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

- Parallel tests: T021, T022, T023
- Parallel-safe implementation split: T024 and T026 can run concurrently once retry policy in T025 is established

### User Story 2

- Parallel tests: T027, T028, T029
- Parallel-safe implementation split: T031 and T032 can run concurrently after T030 baseline

### User Story 3

- Parallel tests: T033, T034, T035
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
