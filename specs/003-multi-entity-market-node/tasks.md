# Tasks: Multiple Entities for Market Node

**Input**: Design documents from `/specs/003-multi-entity-market-node/`
**Prerequisites**: `plan.md` (required), `spec.md` (required), `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Included (spec has explicit independent test criteria per user story and constitution mandates test-first).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete-task dependency)
- **[Story]**: User story label (`[US1]` ... `[US5]`)
- All task descriptions include concrete file paths.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish 003 constants/config scaffolding and baseline test assets.

- [X] T001 Update 003 constants and option enums in `custom_components/electricityinfo/const.py`
- [X] T002 Align integration metadata/version prerequisites for 003 in `custom_components/electricityinfo/manifest.json`
- [X] T003 [P] Add/refresh shared schedule fixtures for 003 scenarios in `tests/fixtures/market_prices.json`
- [X] T004 [P] Add/refresh shared test helpers for subentry/coordinator fixtures in `tests/helpers.py`
- [X] T005 [P] Add 003 config-flow translation keys and validation errors in `custom_components/electricityinfo/translations/en.json`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core architecture required before any user story implementation.

**⚠️ CRITICAL**: No user story work starts until this phase completes.

- [X] T006 Implement `MarketNodeSubentryFlow` registration and entry points in `custom_components/electricityinfo/config_flow.py`
- [X] T007 Implement shared config normalization/validation helpers (enabled sections, meter validation, node validation) in `custom_components/electricityinfo/config_flow.py`
- [X] T008 Implement 002→003 migration (`async_migrate_entry`) and config version bump in `custom_components/electricityinfo/__init__.py`
- [X] T009 [P] Add migration coverage for schedule mappings, dedupe-by-node, and warning behavior in `tests/test_init.py`
- [X] T010 Refactor coordinator data shape and per-subentry fetch dispatch in `custom_components/electricityinfo/coordinator.py`
- [X] T011 [P] Add coordinator routing/retry/unit-conversion baseline tests in `tests/test_coordinator.py`
- [X] T012 Implement shared sensor entity base/ID/device helpers for market-node subentries in `custom_components/electricityinfo/sensor.py`

**Checkpoint**: Foundation complete; user stories can be implemented/tested independently.

---

## Phase 3: User Story 1 - Live Price Sensor Setup (Priority: P1) 🎯 MVP

**Goal**: Create live price sensor for a configured market node with selected unit and current trade period value.

**Independent Test**: Configure one market node with only live price enabled and verify a single live sensor is created with current value.

### Tests for User Story 1

- [X] T013 [P] [US1] Add config-flow test for live-only market-node creation in `tests/test_config_flow.py`
- [X] T014 [P] [US1] Add live sensor restore/staleness tests in `tests/test_sensor.py`
- [X] T015 [P] [US1] Add live sensor startup availability integration test in `tests/integration/test_sensor_lifecycle.py`

### Implementation for User Story 1

- [X] T016 [US1] Implement current trade period extraction for live state from forecast response in `custom_components/electricityinfo/coordinator.py`
- [X] T017 [US1] Implement `LivePriceSensor` state/attributes/RestoreEntity behavior in `custom_components/electricityinfo/sensor.py`
- [X] T018 [US1] Wire live-only entity creation path for market-node subentries in `custom_components/electricityinfo/sensor.py`

**Checkpoint**: US1 is functional and independently testable (MVP).

---

## Phase 4: User Story 2 - Forecast Price Sensors (Priority: P2)

**Goal**: Create day-ahead and/or intraday forecast sensors with forecast type, horizons, and retention controls.

**Independent Test**: Enable forecasting only, choose one or both horizons, and verify forecast sensor creation/population.

### Tests for User Story 2

- [X] T019 [P] [US2] Add forecast form validation tests (horizons/type/retention) in `tests/test_config_flow.py`
- [X] T020 [P] [US2] Add day-ahead/intraday forecast sensor behavior tests in `tests/test_sensor.py`
- [X] T021 [P] [US2] Add forecast retention history assertions in `tests/test_sensor_multiple.py`

### Implementation for User Story 2

- [X] T022 [US2] Implement forecast schedule mapping and horizon-based fetch logic in `custom_components/electricityinfo/coordinator.py`
- [X] T023 [US2] Implement `DayAheadForecastSensor` and `IntradayForecastSensor` state/attribute models in `custom_components/electricityinfo/sensor.py`
- [X] T024 [US2] Implement forecast section parsing and persistence in `custom_components/electricityinfo/config_flow.py`

**Checkpoint**: US2 works independently with US1 intact.

---

## Phase 5: User Story 4 - Multiple Market Nodes (Priority: P2)

**Goal**: Support multiple independently configured market nodes with isolated data updates and entity sets.

**Independent Test**: Add a second node and verify separate, correctly named sensors update independently.

### Tests for User Story 4

- [X] T025 [P] [US4] Add multi-node setup and independent update integration tests in `tests/integration/test_multi_node.py`
- [X] T026 [P] [US4] Add per-node coordinator error-isolation tests in `tests/test_coordinator.py`

### Implementation for User Story 4

- [X] T027 [US4] Implement per-subentry coordinator update isolation and node-keyed storage in `custom_components/electricityinfo/coordinator.py`
- [X] T028 [US4] Implement per-node device/entity naming and unique-ID prefix rules in `custom_components/electricityinfo/sensor.py`
- [X] T029 [US4] Enforce one configured subentry per market node in flow validation in `custom_components/electricityinfo/config_flow.py`

**Checkpoint**: US4 is independently functional with multi-node behavior.

---

## Phase 6: User Story 5 - Modifying an Existing Market Node Configuration (Priority: P2)

**Goal**: Allow reconfigure flows to add/remove/update node options without deleting and recreating integration.

**Independent Test**: Save initial config, re-open config, modify at least one option, save, and verify sensor set reflects the change.

### Tests for User Story 5

- [X] T030 [P] [US5] Add reconfigure no-op vs changed-save tests in `tests/test_options_flow.py`
- [X] T031 [P] [US5] Add entity add/remove-on-reconfigure integration coverage in `tests/integration/test_sensor_lifecycle.py`

### Implementation for User Story 5

- [X] T032 [US5] Implement reconfigure form population/update-and-abort path in `custom_components/electricityinfo/config_flow.py`
- [X] T033 [US5] Implement sensor delta reconciliation on config changes in `custom_components/electricityinfo/sensor.py`
- [X] T034 [US5] Preserve unaffected nodes during one-node reconfigure updates in `custom_components/electricityinfo/coordinator.py`

**Checkpoint**: US5 reconfigure behavior is independently testable.

---

## Phase 7: User Story 3 - Accounting and Analytics Sensors (Priority: P3)

**Goal**: Deliver settled price, import/export per-period values, and daily totals using Interim pricing plus meter-linked deltas.

**Independent Test**: Enable accounting and verify settled + calculated + daily sensors according to linked meter configuration.

### Tests for User Story 3

- [ ] T035 [P] [US3] Add accounting flow validation tests for meter selectors and fallback rules in `tests/test_config_flow.py`
- [ ] T036 [P] [US3] Add coordinator accounting tests (Interim `back=48`, meter delta, bidirectional, export fallback) in `tests/test_coordinator.py`
- [ ] T037 [P] [US3] Add accounting sensor tests for settled/import/export/daily restore/reset behavior in `tests/test_accounting.py`

### Implementation for User Story 3

- [ ] T038 [US3] Implement accounting fetch, meter delta tracking, and export fallback computation in `custom_components/electricityinfo/coordinator.py`
- [ ] T039 [US3] Implement `SettledPriceSensor`, `ImportCostSensor`, `ExportRevenueSensor`, `DailyImportCostSensor`, and `DailyExportRevenueSensor` in `custom_components/electricityinfo/sensor.py`
- [ ] T040 [US3] Implement accounting section schema (retention + two optional selectors + fallback normalization) in `custom_components/electricityinfo/config_flow.py`

**Checkpoint**: US3 accounting behavior is independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency, docs, and full-suite confidence across all stories.

- [ ] T041 [P] Update feature artifact alignment notes in `specs/003-multi-entity-market-node/quickstart.md`
- [ ] T042 [P] Refresh plan-context summary for implemented behavior in `.github/copilot-instructions.md`
- [ ] T043 Execute and fix full regression suite issues across `tests/` and `custom_components/electricityinfo/`
- [ ] T044 [P] Add/update live-test findings notes for settled-price behavior in `tests/live/FINDINGS.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies.
- **Phase 2 (Foundational)**: Depends on Phase 1 and blocks all user stories.
- **Phases 3–7 (User Stories)**: Depend on Phase 2 completion.
- **Phase 8 (Polish)**: Depends on all selected user stories.

### User Story Dependencies

- **US1 (P1)**: Starts immediately after foundational phase (MVP).
- **US2 (P2)**: Depends on foundational phase; independent of US4/US5/US3.
- **US4 (P2)**: Depends on foundational phase and US1 entity/coordinator baseline.
- **US5 (P2)**: Depends on US1 + US2 configuration/sensor paths.
- **US3 (P3)**: Depends on foundational phase; can proceed independently of US4/US5.

### Suggested Completion Order

1. US1 (MVP)
2. US2 and US4 (parallel-capable)
3. US5
4. US3

---

## Parallel Opportunities

- **Setup**: T003, T004, T005 can run in parallel.
- **Foundational**: T009 and T011 can run in parallel after T008/T010 scaffolding.
- **US1**: T013, T014, T015 parallelizable.
- **US2**: T019, T020, T021 parallelizable.
- **US4**: T025 and T026 parallelizable.
- **US5**: T030 and T031 parallelizable.
- **US3**: T035, T036, T037 parallelizable.
- **Polish**: T041, T042, T044 parallelizable.

## Parallel Example: User Story 1

```bash
Task: "Add config-flow test for live-only market-node creation in tests/test_config_flow.py"
Task: "Add live sensor restore/staleness tests in tests/test_sensor.py"
Task: "Add live sensor startup availability integration test in tests/integration/test_sensor_lifecycle.py"
```

## Parallel Example: User Story 2

```bash
Task: "Add forecast form validation tests in tests/test_config_flow.py"
Task: "Add day-ahead/intraday forecast sensor behavior tests in tests/test_sensor.py"
Task: "Add forecast retention assertions in tests/test_sensor_multiple.py"
```

## Parallel Example: User Story 4

```bash
Task: "Add multi-node setup and independent update integration tests in tests/integration/test_multi_node.py"
Task: "Add per-node coordinator error-isolation tests in tests/test_coordinator.py"
```

## Parallel Example: User Story 5

```bash
Task: "Add reconfigure no-op vs changed-save tests in tests/test_options_flow.py"
Task: "Add entity add/remove-on-reconfigure integration coverage in tests/integration/test_sensor_lifecycle.py"
```

## Parallel Example: User Story 3

```bash
Task: "Add accounting flow validation tests for meter selectors and fallback rules in tests/test_config_flow.py"
Task: "Add coordinator accounting tests in tests/test_coordinator.py"
Task: "Add accounting sensor tests in tests/test_accounting.py"
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1).
3. Validate US1 independently, then demo/release MVP.

### Incremental Delivery

1. Foundation complete (Phases 1–2).
2. Deliver US1.
3. Deliver US2 + US4.
4. Deliver US5.
5. Deliver US3.
6. Execute polish phase.

### Parallel Team Strategy

1. Team aligns on Setup + Foundational.
2. Split into tracks after foundation:
   - Track A: US1 → US5
   - Track B: US2 → US4
   - Track C: US3
3. Integrate in priority order with checkpoint validation per story.
