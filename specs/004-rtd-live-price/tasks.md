# Tasks: RTD-Based Live Price Sensor (004-rtd-live-price)

**Input**: Design documents from `/specs/004-rtd-live-price/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/sensor-platform.md ✓, quickstart.md ✓

**TDD Requirement**: Constitution Principle IV is NON-NEGOTIABLE — write and confirm failing tests before each implementation task.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared in-flight state)
- **[Story]**: User story label — US1 / US2 / US3

---

## Phase 1: Setup

**Purpose**: Confirm clean baseline before any changes.

- [ ] T001 Run full test suite and confirm 72 tests pass, ruff clean, mypy clean — `pytest tests/`, `ruff check custom_components/ tests/`, `mypy custom_components/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add all new constants to `const.py` before any other file references them. Nothing else can proceed until this is done.

**⚠️ CRITICAL**: Both coordinator and sensor changes depend on the new constants. Complete this phase before any US1–US3 work.

- [ ] T002 Update `custom_components/electricityinfo/const.py`: change `UPDATE_INTERVAL_MINUTES = 30` → `5`; add `RTD_BACK_PERIODS = 3` (below `UPDATE_INTERVAL_MINUTES`); add `LIVE_PRICE_RESTORE_STALENESS_MINUTES = 30` (below `RTD_BACK_PERIODS`) — staleness guard must stay at 30 min even though poll interval drops to 5 min (spec Assumption 6)

**Checkpoint**: `const.py` exports three constants: `UPDATE_INTERVAL_MINUTES=5`, `RTD_BACK_PERIODS=3`, `LIVE_PRICE_RESTORE_STALENESS_MINUTES=30`

---

## Phase 3: User Story 1 — Accurate Real-Time Spot Price (Priority: P1) 🎯 MVP

**Goal**: `LivePriceSensor` reads its state exclusively from the RTD schedule, not from a day-ahead forecast.

**Independent Test**: Enable live price for a market node, run the coordinator, verify `live_current["schedule"] == "RTD"` and `native_value` is populated from the RTD response.

### Tests for User Story 1 ⚠️ Write FIRST — confirm they FAIL before T005/T006

- [ ] T003 [P] [US1] Rename `test_live_fetch_routes_day_ahead_and_converts_units` → `test_live_fetch_uses_rtd_schedule`; rewrite to assert `get_schedule_prices` is called with `schedule="RTD"`, `back=3`, no `forward` kwarg; assert `data["market_node_1"]["live_current"]["schedule"] == "RTD"` and price is unit-converted — `tests/test_coordinator.py`
- [ ] T004 [P] [US1] Replace `test_live_sensor_fallback_splits_forecast_and_history_by_now` with `test_live_sensor_unavailable_when_no_rtd_data`: coordinator data has `live_current=None` (no RTD response); assert `entity.native_value is None` and `entity.available is False` — `tests/test_sensor.py`

### Implementation for User Story 1

- [ ] T005 [US1] Update `custom_components/electricityinfo/coordinator.py`: (a) import `RTD_BACK_PERIODS` from `.const`; (b) add RTD fetch block after accounting block — `if config.get(CONF_ENABLE_LIVE_PRICE): rtd = await client.get_schedule_prices(schedule="RTD", back=RTD_BACK_PERIODS, market_type="E", nodes=[node])` → convert prices → `node_data["rtd"] = rtd; node_data["live_current"] = _extract_live_price_payload(rtd)`; (c) change day-ahead guard from `if config.get(CONF_ENABLE_LIVE_PRICE) or (config.get(CONF_ENABLE_FORECAST) and "day_ahead" in horizons)` → `if config.get(CONF_ENABLE_FORECAST) and "day_ahead" in horizons`; (d) remove the `node_data["live_current"] = _extract_live_price_payload(day_ahead)` line from the day-ahead block
- [ ] T006 [US1] Remove dead-code fallback from `LivePriceSensor._handle_coordinator_update` in `custom_components/electricityinfo/sensor.py` (lines ~301–330): the branch that reads from `node_data["day_ahead"]` when `live_current` is `None`; after removal, `live_current=None` must result in `self._attr_native_value = None` and sensor becoming unavailable (FR-004)
- [ ] T007 [US1] Run `pytest tests/test_coordinator.py tests/test_sensor.py` — confirm T003 and T004 now pass; confirm no regressions in those files

**Checkpoint**: US1 fully functional — live price sourced from RTD; fallback path removed; tests green.

---

## Phase 4: User Story 2 — Near Real-Time Price Updates (Priority: P1)

**Goal**: Coordinator polls every 5 minutes; `LivePriceSensor` staleness guard remains at 30 minutes.

**Independent Test**: Inspect `coordinator.update_interval` immediately after construction — must equal `timedelta(minutes=5)`. Inspect staleness guard — must trigger at > 30 minutes (not > 5 minutes) regardless of poll interval.

### Tests for User Story 2 ⚠️ Write FIRST — confirm they FAIL before T010

- [ ] T008 [P] [US2] Add `test_coordinator_default_update_interval`: construct `ElectricityInfoCoordinator` with any valid entry; assert `coordinator.update_interval == timedelta(minutes=5)` — `tests/test_coordinator.py`
- [ ] T009 [P] [US2] Add `test_live_sensor_staleness_guard_threshold_is_30_minutes`: mock utcnow to be exactly 31 minutes after restored timestamp; assert state is discarded (unavailable); mock utcnow to be exactly 29 minutes after; assert state is restored — `tests/test_sensor.py`

### Implementation for User Story 2

- [ ] T010 [US2] Update `custom_components/electricityinfo/sensor.py`: add `LIVE_PRICE_RESTORE_STALENESS_MINUTES` to the `from .const import` block; replace `UPDATE_INTERVAL_MINUTES` with `LIVE_PRICE_RESTORE_STALENESS_MINUTES` in the `timedelta(minutes=...)` call inside `LivePriceSensor.async_added_to_hass` staleness guard (line ~271); remove `UPDATE_INTERVAL_MINUTES` from the import if no longer used
- [ ] T011 [US2] Run `pytest tests/test_coordinator.py tests/test_sensor.py` — confirm T008 and T009 now pass; confirm `test_live_sensor_discards_stale_state` (45 min elapsed) still passes

**Checkpoint**: US2 fully functional — poll at 5 min; staleness guard still at 30 min; tests green.

---

## Phase 5: User Story 3 — Forecast and Accounting Regression (Priority: P2)

**Goal**: All existing forecast and accounting sensors continue working correctly after the coordinator interval change and the RTD decoupling.

**Independent Test**: Enable all sensor types simultaneously; run coordinator; verify each sensor produces valid state data and the correct API calls are made (RTD for live, PRSL/NRSL for day-ahead, neither for accounting-only).

### Tests for User Story 3 ⚠️ Write FIRST — confirm they FAIL before T014

- [ ] T012 [P] [US3] Add `test_live_and_forecast_enabled_makes_two_api_calls`: subentry has `enable_live_price=True, enable_forecast=True, forecast_horizons=["day_ahead"]`; assert `client.get_schedule_prices` is called twice — once with `schedule="RTD"` and once with `schedule="PRSL"` (or "NRSL"); assert both `node_data["live_current"]` and `node_data["day_ahead"]` are populated — `tests/test_coordinator.py`
- [ ] T013 [P] [US3] Add `test_forecast_only_does_not_call_rtd`: subentry has `enable_live_price=False, enable_forecast=True`; assert no call with `schedule="RTD"` is made; assert `node_data["live_current"]` is absent or `None` — `tests/test_coordinator.py`

### Implementation for User Story 3

> **Note**: The coordinator changes in T005 already implement the decoupling needed for US3. If T012/T013 pass after T005, no additional implementation is needed here — only verification.

- [ ] T014 [US3] Run full `pytest tests/` — confirm T012 and T013 pass; confirm all existing forecast, accounting, and multi-node integration tests continue to pass (zero regressions)

**Checkpoint**: US3 verified — forecast/accounting work at 5-minute cadence; RTD not called for non-live subentries; full suite green.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Version bump, final linting, and full validation.

- [ ] T015 Bump minor version in `custom_components/electricityinfo/manifest.json` — e.g. `"2.0.0"` → `"2.1.0"` (MINOR bump: behaviour change, no config schema change, no `async_migrate_entry` needed)
- [ ] T016 [P] Run `ruff check --fix custom_components/ tests/` — resolve any lint issues introduced during implementation
- [ ] T017 [P] Run `mypy custom_components/` — resolve any type errors introduced during implementation (pay attention to `RTD_BACK_PERIODS` int type in `get_schedule_prices` call and `node_data["rtd"]` optional type)
- [ ] T018 Run full `pytest tests/` — confirm ALL tests pass (expected: ≥ 72 tests); if count increased, confirm new tests are included in the passing set

**Checkpoint**: Implementation complete — version bumped, lint/type clean, all tests green. Ready for commit.

---

## Dependencies

```
T001 (baseline)
  └── T002 (const.py)
        ├── T003, T004 (US1 tests — write failing)
        │     └── T005 (coordinator RTD + guard fix)
        │           └── T006 (sensor fallback removal)
        │                 └── T007 (US1 verify)
        ├── T008, T009 (US2 tests — write failing)
        │     └── T010 (sensor staleness guard fix)
        │           └── T011 (US2 verify)
        └── T012, T013 (US3 regression tests — write failing)
              └── T014 (US3 verify — may need no new code if T005 covers it)
                    └── T015 (version bump)
                          └── T016, T017 (ruff, mypy) → T018 (full suite)
```

## Parallel Execution Opportunities

| Parallel group | Tasks | Constraint |
|---|---|---|
| After T002 | T003, T004, T008, T009, T012, T013 | All write tests in different files or different test functions; no implementation dep |
| After T007 + T011 | T016, T017 | Different tools; can lint and type-check simultaneously |

## Implementation Strategy

**MVP**: Phase 1 → Phase 2 → Phase 3 (US1) only — delivers FR-001, FR-003, FR-004, FR-007.

**Full delivery**: All phases — additionally delivers FR-002, FR-005, FR-006, FR-008 (US2 + US3).

**Key invariants to preserve throughout**:
1. `_extract_live_price_payload` is schedule-agnostic — pass RTD data, no changes needed.
2. `node_data["day_ahead"]` remains the key for forecast sensors; only its guard condition changes.
3. `LIVE_PRICE_RESTORE_STALENESS_MINUTES = 30` decouples RestoreEntity staleness from poll interval.
4. The RTD block must be inside `if config.get(CONF_ENABLE_LIVE_PRICE)` to satisfy FR-007 (SC-005).
5. Pre-commit hooks auto-fix trailing whitespace/EOF — re-stage and re-commit if hooks modify files.
