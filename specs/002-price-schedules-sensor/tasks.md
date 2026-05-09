# Implementation Tasks: Electricity Price Schedules Sensor Platform

**Feature**: Electricity Price Schedules Sensor Platform (002-price-schedules-sensor)
**Branch**: `002-price-schedules-sensor`
**Date**: 2026-05-05
**Total Tasks**: 28
**Status**: Ready for Implementation

## Overview

This document provides an actionable, dependency-ordered task breakdown for implementing the price schedules sensor platform. Tasks are organized by implementation phase and user story priority. Each task is independently testable and executable.

**Implementation Strategy**:
- **Phase 1 (Setup)**: Project initialization and test infrastructure
- **Phase 2 (Foundational)**: DataUpdateCoordinator and config flow scaffold
- **Phase 3 (MVP - User Story 1 & 4)**: Single sensor + error handling (P1 features)
- **Phase 4 (Phase 2)**: Multiple sensors support (P2 feature)
- **Phase 5 (Phase 3)**: Unit conversion (P2 feature)
- **Phase 6 (Polish)**: Documentation, integration testing, refinement

---

## Implementation Timeline

### Parallel Execution Opportunities

**Within Phase 1 (Setup)**: All tasks can run in parallel (different files, no dependencies)
**Within Phase 2 (Foundational)**: Config flow steps can be parallelized after fixtures created
**Within Phase 3 (US1+US4)**:
- Config flow options steps (T009-T011) run in parallel
- Sensor platform creation (T012-T019) runs in parallel after coordinator setup
- Tests (T020-T022) can run in parallel with implementation

**Within Phase 4-5**: User story phases are mostly independent after foundational phase

---

## Phase 1: Setup & Project Initialization

### Goal
Establish test infrastructure, add constants, and prepare for sensor platform implementation.

### Phase 1 Tasks

- [x] T001 Create constants for allowed schedule types, market types, nodes in `custom_components/electricityinfo/const.py`
- [x] T002 Add sensor-related string translations to `custom_components/electricityinfo/strings.json` (config flow steps, field labels, validation errors)
- [x] T003 Create mock market prices fixture in `tests/fixtures/market_prices.json` for all test scenarios
- [x] T004 [P] Update `tests/conftest.py` with mock_market_prices, mock_coordinator fixtures
- [x] T005 [P] Create `tests/integration/` directory structure for E2E tests
- [x] T006 [P] Create test helper module `tests/helpers.py` for sensor setup, coordinator mocking utilities

### Independent Test Criteria
- Constants file loads without errors; allowed values match API documentation
- Translations file is valid JSON with required keys
- Mock fixtures return valid price schedule data matching API response schema
- Conftest fixtures initialize without errors

---

## Phase 2: Foundational Components

### Goal
Build core DataUpdateCoordinator and scaffold for config flow options.

### Phase 2 Tasks

- [x] T007 Create DataUpdateCoordinator in `custom_components/electricityinfo/__init__.py` with `_async_update_data()` method
- [x] T008 Implement exponential backoff retry logic (1-minute first retry, mark unavailable after 2nd failure) in coordinator
- [x] T009 Add `OptionsFlowHandler` class to `custom_components/electricityinfo/config_flow.py`
- [x] T010 [P] Implement `async_step_init()` → `async_step_configure_sensors()` flow in OptionsFlowHandler
- [x] T011 [P] Implement sensor list display and action button routing in config flow

### Independent Test Criteria
- Coordinator fetches prices without errors (mocked API)
- Retry logic triggers after first failure; unavailable after second
- Options flow renders without errors
- Sensor list displays existing sensors (if any)
- User can navigate between config flow steps

---

## Phase 3: User Story 1 & 4 (MVP - Single Sensor + Error Handling)

### Goal
Implement core MVP: users can add a single sensor and see it update every 30 minutes with graceful error recovery.

### User Story 1: Configure Single Price Sensor (P1)

**Independent Test**: Add sensor via config flow → verify entity created → verify data updates every 30 minutes

#### US1 Config Flow Tasks

- [x] T012 [US1] Implement `async_step_add_sensor()` form in OptionsFlowHandler with fields: id, schedule_type, market_type, node, forward_prices_count, unit_preference
- [x] T013 [US1] Add sensor validation in `async_step_add_sensor()`: unique ID, allowed schedule_type/market_type/node, valid forward_prices_count, unit_preference in ["NZD/MWh", "c/kWh"]
- [x] T014 [US1] Save sensor config to `config_entry.options["sensors"]` list after validation
- [x] T015 [P] [US1] Implement `async_step_edit_sensor()` for editing existing sensor config
- [x] T016 [P] [US1] Implement sensor deletion with confirmation dialog in `async_step_configure_sensors()`

#### US1 Sensor Platform Tasks

- [x] T017 [US1] Create PriceSensorEntity class in `custom_components/electricityinfo/sensor.py` inheriting from SensorEntity, RestoreEntity, CoordinatorEntity
- [x] T018 [US1] Implement PriceSensorEntity properties: entity_id, unique_id, name, icon, device_class, native_value (current price)
- [x] T019 [US1] Implement PriceSensorEntity attributes: timestamp, confidence_level, forecast_period, market_type, node, schedule_type, prices_array
- [x] T020 [US1] Implement `async_setup_entry()` sensor platform function to create PriceSensorEntity for each SensorConfiguration
- [x] T021 [US1] Implement RestoreEntity `async_added_to_hass()` to restore previous state after Home Assistant restart
- [x] T022 [US1] Implement unit conversion in entity state property: apply NZD/MWh ↔ c/kWh conversion based on unit_preference

#### US1 Tests

- [x] T023 [US1] Write unit tests for config flow validation in `tests/test_config_flow_sensor_options.py`: test valid/invalid IDs, schedule types, nodes, units
- [x] T024 [US1] Write integration test for single sensor add/display in `tests/integration/test_sensor_end_to_end.py`
- [x] T025 [US1] Write test for state persistence: verify state restored after Home Assistant restart

### User Story 4: Handle Update Failures Gracefully (P1)

**Independent Test**: Simulate API failures → verify sensor marks unavailable → verify recovery when API returns

#### US4 Error Handling Tasks

- [x] T026 [US4] Implement error handling in coordinator `_async_update_data()`: catch TokenExpiredError, ConnectionError, TimeoutError
- [x] T027 [US4] Implement automatic entity unavailable state transition when coordinator fails (after 2 failures)
- [x] T028 [US4] Implement automatic recovery: transition entity from unavailable to available when coordinator succeeds
- [x] T029 [US4] Handle partial API responses: if prices missing for sensor's node/schedule_type, mark that sensor unavailable only (not others)

#### US4 Tests

- [x] T030 [US4] Write test for API failure → unavailable transition in `tests/test_sensor_platform.py`
- [x] T031 [US4] Write test for recovery on API success
- [x] T032 [US4] Write test for partial data handling (one sensor fails while others update)

---

## Phase 4: User Story 2 (Multiple Sensors)

### Goal
Support multiple price sensors with independent updates and failure handling.

### User Story 2: Configure Multiple Price Sensors (P2)

**Independent Test**: Add 2 sensors → verify both update independently → verify isolation (one failing doesn't affect others)

#### US2 Tasks

- [x] T033 [US2] Verify config flow CRUD operations support multiple sensors (T012-T016 already support this; verify in tests)
- [x] T034 [US2] Write integration test for adding multiple sensors with different configs in `tests/integration/test_sensor_end_to_end.py`
- [x] T035 [US2] Write test for coordinator handling multiple sensor updates without interference
- [x] T036 [US2] Write test for isolated failure: one sensor fails to fetch, others update normally
- [x] T037 [US2] Verify unique entity_id generation per sensor (no collisions with multiple sensors)

---

## Phase 5: User Story 3 (Unit Conversion)

### Goal
Support price display in both NZD/MWh and c/kWh with accurate conversion.

### User Story 3: Switch Price Units (P2)

**Independent Test**: Create sensors with different units → verify prices display correctly in each unit

#### US3 Tasks

- [x] T038 [US3] Add price unit conversion helper function in `custom_components/electricityinfo/sensor.py`: NZD/MWh ↔ c/kWh
- [x] T039 [US3] Verify entity `unit_of_measurement` property returns correct display unit based on SensorConfiguration
- [x] T040 [US3] Write test for unit conversion accuracy (within ±0.01 c/kWh)
- [x] T041 [US3] Write test for dynamic unit reconfiguration: change unit → verify display updates

---

## Phase 6: Polish & Cross-Cutting Concerns

### Goal
Comprehensive testing, documentation, and final refinement.

### Testing & Documentation Tasks

- [x] T042 Run full test suite: `pytest tests/ -v` → verify all tests pass
- [x] T043 Run linting: `ruff check --fix custom_components/ tests/` → verify no linting errors
- [x] T044 Run type checking: `mypy custom_components/` → verify no type errors
- [x] T045 Create manual testing guide documenting live API tests (optional, with credentials)
- [x] T046 Update CHANGELOG.md with Phase 2 feature summary and user-facing changes
- [x] T047 Verify all entity IDs follow naming convention: `sensor.electricityinfo_nz_{node}_{schedule_type}_{market_type}_{unit}`
- [x] T048 Add PR description template with reference to spec, plan, research docs
- [x] T049 Verify no sensitive data (tokens, credentials) in logs or error messages
- [x] T050 Final integration test: add sensor, verify full 30-minute update cycle, check state persistence

### Final Verification

- [x] T051 Verify Constitution compliance: OAuth security, library wrapper usage, TDD methodology, configurable architecture
- [x] T052 Verify success criteria met (SC-001 through SC-008 from spec)
- [x] T053 Create GitHub PR with all commits and reference to planning documents

---

## Task Dependencies & Execution Order

### Critical Path (Must Complete In Order)
```
T001-T006 (Setup)
  ↓
T007-T011 (Foundational)
  ↓
T012-T031 (User Story 1 + 4 - MVP)
  ↓
T033-T037 (User Story 2 - Multiple Sensors)
  ↓
T038-T041 (User Story 3 - Unit Conversion)
  ↓
T042-T053 (Polish & Final Verification)
```

### Parallelizable Within Phases
- **Phase 1**: T001-T006 all run in parallel
- **Phase 2**: T009-T011 can run in parallel after T007-T008
- **Phase 3 (US1)**:
  - T012-T016 (config flow) in parallel with T017-T022 (sensor platform) after coordinator setup
  - T023-T025 (tests) in parallel with implementation
- **Phase 4**: T033-T037 independent (can start after phase 3 complete)
- **Phase 5**: T038-T041 independent (can start after phase 4 complete)

### Suggested MVP Scope (Week 1)
Complete only **User Story 1 + User Story 4** (P1 features):
- T001-T031: Setup through US1 + US4 complete
- Result: Users can add single sensor, see updates, graceful error recovery
- Estimated effort: 3-4 days with focused implementation and testing

### Full Scope (Weeks 2-3)
- Add User Story 2 (T033-T037): Multiple sensors support
- Add User Story 3 (T038-T041): Unit conversion
- Polish & testing (T042-T053)

---

## Task Checklist Format

All tasks follow strict format: `- [ ] [ID] [Parallelizable?] [Story?] Description with file path`

**Components**:
- **Checkbox**: `- [ ]` (unchecked) or `- [x]` (completed)
- **Task ID**: T001, T002, ... (sequential, execution order)
- **[P]**: Optional parallelizable marker (can run in parallel with others in same phase)
- **[USN]**: User Story marker (T012+ have story labels; setup/foundational/polish do not)
- **Description**: Clear action with specific file paths for implementation

---

## Implementation Notes

### File Structure to Create/Modify
```
custom_components/electricityinfo/
├── __init__.py              # MODIFY: Add DataUpdateCoordinator
├── config_flow.py           # MODIFY: Add OptionsFlowHandler
├── const.py                 # MODIFY: Add sensor constants (T001)
├── sensor.py                # CREATE: New sensor platform (T017-T022)
├── strings.json             # MODIFY: Add translations (T002)
└── manifest.json            # No changes

tests/
├── conftest.py              # MODIFY: Add fixtures (T004)
├── fixtures/
│   └── market_prices.json   # CREATE: Mock data (T003)
├── helpers.py               # CREATE: Test helpers (T006)
├── test_config_flow_sensor_options.py  # CREATE (T023-T024)
├── test_sensor_platform.py  # CREATE (T025, T030-T032, T040-T041)
└── integration/
    └── test_sensor_end_to_end.py   # CREATE (T034-T035)
```

### Testing Strategy
- **Mocked API** (CI): All tasks T023-T041 use mocked Electricityinfo API responses
- **Live API** (Optional): T045 documents manual tests with real credentials
- **Coverage Target**: >80% of sensor platform code

### Constitution Compliance
- ✅ **Library wrapper first**: All API calls via electricityinfo-nz library (T001-T008, T026-T029)
- ✅ **OAuth security**: Token refresh delegated to library; no token logging (T007, T026)
- ✅ **Configurable architecture**: Options Flow for sensor management (T012-T016)
- ✅ **Test-first methodology**: Comprehensive tests for all user stories (T023-T041)
- ✅ **Semantic versioning**: Incremental feature; no breaking changes (T053)

---

## Success Metrics

**MVP Complete (After T031)**:
- [ ] Users can add 1+ sensors via Options Flow
- [ ] Sensors display current price updated every 30 minutes
- [ ] Sensors gracefully handle API failures (mark unavailable, auto-recover)
- [ ] State persists across Home Assistant restarts
- [ ] All P1 tests passing (T023, T025, T030-T032)

**Full Feature Complete (After T041)**:
- [ ] Users can add 5+ sensors simultaneously
- [ ] Multiple sensors update independently without interference
- [ ] Prices display in NZD/MWh or c/kWh per user preference
- [ ] All tests passing (T023-T041)
- [ ] No linting or type errors (T042-T044)

**Production Ready (After T053)**:
- [ ] Full test coverage >80%
- [ ] All success criteria (SC-001 through SC-008) verified
- [ ] Constitution compliance confirmed
- [ ] PR approved with design docs referenced

---

## Next Steps

1. **Review this tasks.md** with team to confirm scope and dependencies
2. **Start Phase 1 (T001-T006)**: Setup tasks can be parallelized
3. **Execute Phase 2 (T007-T011)**: Foundational components
4. **Implement MVP (Phase 3, T012-T031)**: Single sensor + error handling
5. **Extend to full feature (Phases 4-5, T033-T041)**: Multiple sensors + unit conversion
6. **Polish & release (Phase 6, T042-T053)**: Testing, documentation, verification

---

## References

- **Specification**: `specs/002-price-schedules-sensor/spec.md` (user stories, requirements)
- **Plan**: `specs/002-price-schedules-sensor/plan.md` (technical approach)
- **Research**: `specs/002-price-schedules-sensor/research.md` (design decisions)
- **Data Model**: `specs/002-price-schedules-sensor/data-model.md` (entity definitions)
- **Contracts**: `specs/002-price-schedules-sensor/contracts/` (UI/UX, entity lifecycle)
- **Quickstart**: `specs/002-price-schedules-sensor/quickstart.md` (developer setup)
