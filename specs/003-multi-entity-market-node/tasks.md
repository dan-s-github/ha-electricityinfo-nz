# Tasks: Multiple Entities for Market Node (003)

**Branch**: `003-multi-entity-market-node`
**Input**: Design documents from `specs/003-multi-entity-market-node/`
**Tech stack**: Python 3.14+, Home Assistant 2026.3.1, electricityinfo-nz PyPI library, pytest + pytest-homeassistant-custom-component

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared state dependencies)
- **[Story]**: Maps to user story from spec.md (US1–US5)
- **Tests**: Included per TDD approach specified in quickstart.md (write tests first, verify they fail, then implement)

---

## Phase 1: Setup (Constants & Manifest)

**Purpose**: Establish 003 constants and manifest version before any implementation can begin.

- [ ] T001 Update `custom_components/electricityinfo/const.py`: add `SUBENTRY_TYPE="market_node"`, `PRICE_UNITS`, `FORECAST_TYPES`, `FORECAST_HORIZONS`, `FORECAST_SCHEDULE_MAP`, `RETENTION_OPTIONS`, `ACCOUNTING_BACK_PERIODS=48`, `DAY_AHEAD_FORWARD_PERIODS=48`, `INTRADAY_FORWARD_PERIODS=8`, `NZD_MWH_TO_C_KWH=0.1`, `NZD_MWH_TO_NZD_KWH=0.001`, `UPDATE_INTERVAL_MINUTES=30`, `RETRY_INTERVAL_MINUTES=1`, `MAX_RETRIES=2`; remove old 002 constants (`CONF_SCHEDULE_TYPE`, `CONF_MARKET_TYPE`, `CONF_FORWARD_PRICES_COUNT`)
- [ ] T002 [P] Update `custom_components/electricityinfo/manifest.json`: bump `version` to `"2.0.0"`

**Checkpoint**: Constants and manifest ready — all subsequent tasks can reference T001 symbols.

---

## Phase 2: Foundational (Migration — blocks all user stories)

**Purpose**: Migrate existing VERSION 1 config entries to VERSION 2. MUST be complete before any user story can function correctly on an upgraded install.

**⚠️ CRITICAL**: No user story work can be validated end-to-end until migration is complete.

- [ ] T003 Write migration tests in `tests/test_migration.py`: cover `PRSL`→day-ahead, `PRSS`→intraday, `NRSL`/`NRSS`→non-responsive, `RTD`/`WDS`/`Final`/`Interim`→forecast disabled, `enable_live_price=True` always set, `accounting_retention_hours=24`/`import_meter_entity_id=None`/`export_meter_entity_id=None` in migrated data, and entity ID change warnings logged; confirm tests FAIL before implementation
- [ ] T004 Implement `async_migrate_entry` in `custom_components/electricityinfo/__init__.py`: apply VERSION 1→2 mapping rules per `research.md §1`; convert `schedule_type` to `enable_forecast`, `forecast_type`, `forecast_horizons`; set `enable_live_price=True`, `enable_accounting=False`, `accounting_retention_hours=24`, `import_meter_entity_id=None`, `export_meter_entity_id=None`; log one warning per changed entity ID; return `False` on failure
- [ ] T005 Set `ConfigFlow.VERSION = 2` in `custom_components/electricityinfo/config_flow.py` so HA triggers `async_migrate_entry` on existing VERSION 1 entries

**Checkpoint**: Run `pytest tests/test_migration.py -v` — all migration tests must pass before US work begins.

---

## Phase 3: User Story 1 — Live Price Sensor (Priority: P1) 🎯 MVP

**Goal**: User configures a market node, enables live price, and a sensor appears showing the current trade period price sourced from the forecast schedule response.

**Independent Test**: Configure one node with only live price enabled → one sensor created → sensor shows current price in selected unit.

### Tests for US1 (write first — verify FAIL before implementing)

- [ ] T006 [P] [US1] Write `MarketNodeSubentryFlow` tests in `tests/test_config_flow.py`: cover `user` step creation (required fields, node validation, `no_sensor_type_enabled` error), `reconfigure` step pre-fill, `_build_node_data` output shape, `_node_title` format `"{NODE_LABEL} [{unit}]"`, and `async_get_supported_subentry_types` returns `{"market_node": MarketNodeSubentryFlow}`
- [ ] T007 [P] [US1] Write `LivePriceSensor` tests in `tests/test_sensor.py`: cover current trade period detection (largest `trading_datetime ≤ utcnow()`), `RestoreEntity` restore of last known state, staleness guard (age > 30 min → discard + request refresh), forecast attribute populated with remaining future periods, `native_unit_of_measurement` equals configured `price_unit`, unique ID suffix `live_price`

### Implementation for US1

- [ ] T008 [US1] Implement `MarketNodeSubentryFlow` in `custom_components/electricityinfo/config_flow.py`: replace `SensorSubentryFlowHandler`; implement `user` and `reconfigure` steps with schema per `contracts/config-flow.md`; implement `_build_node_data`, `_validate_node_fields` (cross-field validation, `no_sensor_type_enabled`, `forecast_horizons_empty`, `node_invalid`), and `_node_title`; register via `async_get_supported_subentry_types` returning `{"market_node": MarketNodeSubentryFlow}`
- [ ] T009 [US1] Refactor `custom_components/electricityinfo/coordinator.py`: change per-subentry dispatch to filter `subentry_type == "market_node"`; build `NodeData` TypedDict with `day_ahead`, `intraday`, `accounting`, `import_cost_delta`, `export_revenue_delta`, `accounting_date_nzt`, `config`, `error` keys; implement `_convert_price(price_nzd_mwh, price_unit) -> float` and apply to all `PriceDetail.price` values at ingest; dispatch `get_schedule_prices(PRSL/NRSL, forward=48)` when `enable_live_price=True` or day-ahead forecast enabled
- [ ] T010 [US1] Implement `LivePriceSensor` in `custom_components/electricityinfo/sensor.py`: inherit `CoordinatorEntity`, `RestoreEntity`, `SensorEntity`; implement `async_added_to_hass` with restore + staleness guard (30 min threshold → discard + `coordinator.async_request_refresh()`); implement `_handle_coordinator_update` selecting current period (max `trading_datetime ≤ utcnow()`) and populating `forecast` attribute; set `unique_id = f"electricityinfo_{entry.entry_id}_{subentry.subentry_id}_live_price"`
- [ ] T011 [US1] Update `sensor.async_setup_entry` in `custom_components/electricityinfo/sensor.py`: iterate `entry.subentries.values()` filtering `subentry_type == "market_node"`; create `LivePriceSensor` when `config["enable_live_price"]`; call `async_add_entities(entities, config_subentry_id=subentry.subentry_id)`; remove old `PriceSensorEntity` setup logic
- [ ] T012 [US1] Update `custom_components/electricityinfo/translations/en.json`: add strings for `node`, `price_unit`, `enable_live_price` fields; add error keys `no_sensor_type_enabled`, `node_invalid`; remove obsolete 002 string keys

**Checkpoint**: `pytest tests/test_config_flow.py tests/test_sensor.py -v` passes. Configure live price sensor in HA dev — sensor appears with current price value.

---

## Phase 4: User Story 2 — Forecast Sensors (Priority: P2) + US4 + US5

**Goal**: User enables forecasting, selects horizon(s) and forecast type; forecast sensor(s) created with upcoming periods and history retention.

**Independent Test (US2)**: Enable only forecast section, select day-ahead → one `DayAheadForecastSensor` created with next period as value and forecast attribute with up to 48 entries.

**Independent Test (US4)**: Add second different market node → distinct independent entity sets, each prefixed with their node code.

**Independent Test (US5)**: Reconfigure existing node → add/remove sensor types reflected on next save without removing the unmodified sensors.

### Tests for US2/US4/US5 (write first)

- [ ] T013 [P] [US2] Write `DayAheadForecastSensor` and `IntradayForecastSensor` tests in `tests/test_sensor.py`: cover next-period as `native_value`, `forecast` attribute (up to 48 / 8 periods), `history` attribute retained up to `forecast_retention_hours × 2` periods, `RestoreEntity` NOT used (starts unavailable), unit matches config
- [ ] T014 [P] [US4] Write multi-node integration tests in `tests/integration/test_multi_node.py`: 2 nodes configured → separate entity sets with correct unique IDs; prices update independently; error in one node does not affect the other
- [ ] T015 [P] [US5] Write reconfigure tests in `tests/test_config_flow.py`: enable previously disabled sensor type → entity added; disable previously enabled type → entity removed; save with no changes → all entities unchanged

### Implementation for US2/US4/US5

- [ ] T016 [US2] Extend `custom_components/electricityinfo/coordinator.py`: add intraday fetch `get_schedule_prices(PRSS/NRSS, forward=8)` dispatched when `"intraday" in config["forecast_horizons"]`; store result in `node_data["intraday"]`; implement `FORECAST_SCHEDULE_MAP` lookup for `price_responsive`/`non_responsive` × day-ahead/intraday
- [ ] T017 [P] [US2] Implement `DayAheadForecastSensor` in `custom_components/electricityinfo/sensor.py`: `CoordinatorEntity` only (no `RestoreEntity`); `native_value` = first future `PriceDetail` price; `forecast` attribute = all future periods as `list[PeriodPrice]`; `history` attribute = past periods within `forecast_retention_hours × 2` trade periods; unique ID suffix `day_ahead_forecast`
- [ ] T018 [P] [US2] Implement `IntradayForecastSensor` in `custom_components/electricityinfo/sensor.py`: same shape as `DayAheadForecastSensor` but sourced from `node_data["intraday"]` (up to 8 forward periods); unique ID suffix `intraday_forecast`
- [ ] T019 [US2] Update `sensor.async_setup_entry` in `custom_components/electricityinfo/sensor.py`: add `DayAheadForecastSensor` when `"day_ahead" in config["forecast_horizons"]`; add `IntradayForecastSensor` when `"intraday" in config["forecast_horizons"]`
- [ ] T020 [US4] Implement per-node error isolation in `custom_components/electricityinfo/coordinator.py`: wrap each subentry fetch in `try/except`; store `error` in `NodeData` on failure; other nodes continue updating; on `AuthenticationError` raise `ConfigEntryAuthFailed`; implement exponential backoff (`_retry_count`, intervals: 1→2→4 min); after `MAX_RETRIES` mark coordinator failed
- [ ] T021 [US5] Implement `reconfigure` step in `custom_components/electricityinfo/config_flow.py`: pre-fill schema with current subentry data; on success call `async_update_and_abort`; sensor delta (add/remove) is handled automatically by HA on platform reload after subentry data update
- [ ] T022 [US2] Update `custom_components/electricityinfo/translations/en.json`: add strings for `enable_forecast`, `forecast_type`, `forecast_horizons`, `forecast_retention_hours` fields; add error key `forecast_horizons_empty`

**Checkpoint**: `pytest tests/test_sensor.py tests/integration/test_multi_node.py -v` passes. Two-node setup in HA dev shows independent sensor sets.

---

## Phase 5: User Story 3 — Accounting and Analytics Sensors (Priority: P3)

**Goal**: User enables accounting; settled price sensor always created; import cost, export revenue, and daily total sensors created when energy meters are linked.

**Independent Test**: Enable accounting with import + export meter linked → 5 sensors created: `SettledPriceSensor`, `ImportCostSensor`, `ExportRevenueSensor`, `DailyImportCostSensor`, `DailyExportRevenueSensor`. Daily totals survive HA restart and continue accumulating. Midnight NZT resets totals to zero.

### Tests for US3 (write first)

- [ ] T023 [P] [US3] Write `SettledPriceSensor` tests in `tests/test_accounting.py`: most recent `back=48` Interim entry as `native_value`; `history` attribute within `accounting_retention_hours × 2` periods; starts unavailable on restart; unique ID suffix `settled_price`
- [ ] T024 [P] [US3] Write `ImportCostSensor` and `ExportRevenueSensor` tests in `tests/test_accounting.py`: `native_value = import_cost_delta` from `NodeData`; `import_meter_entity_id` in attributes; starts unavailable on restart; not created when meter not linked; separate per-sensor for import vs export; unique ID suffixes `import_cost` and `export_revenue`
- [ ] T025 [P] [US3] Write `DailyImportCostSensor` and `DailyExportRevenueSensor` tests in `tests/test_accounting.py`: accumulation across multiple coordinator polls; midnight NZT reset when `accounting_date_nzt` advances; `RestoreEntity` restores accumulated total + `accumulation_date` on restart; if restored date is prior day → resets to zero immediately; bidirectional meter mode (same entity_id for import and export) computes signed deltas correctly; unique ID suffixes `daily_import_cost` and `daily_export_revenue`
- [ ] T026 [P] [US3] Write coordinator accounting/delta tests in `tests/test_coordinator.py`: Interim `back=48` dispatch when `enable_accounting=True`; energy delta `= current − previous` per poll; first poll skips delta (no previous stored); bidirectional meter (positive delta = import, negative delta abs = export); `accounting_date_nzt` is NZT date of latest settled period; retry/backoff per `MAX_RETRIES`

### Implementation for US3

- [ ] T027 [US3] Extend `custom_components/electricityinfo/config_flow.py`: add `import_meter_entity_id` and `export_meter_entity_id` `EntitySelector` fields; update `accounting_retention_hours` options to 24/48 (default 24); update `_build_node_data` to handle two meter fields; add validation `entity_not_energy_import` and `entity_not_energy_export`; update `async_get_supported_subentry_types` to include updated schema
- [ ] T028 [US3] Extend `custom_components/electricityinfo/coordinator.py`: add Interim `back=48` fetch to `NodeData["accounting"]`; add `_meter_prev_import: dict[str, float | None]` and `_meter_prev_export: dict[str, float | None]` instance dicts; compute energy deltas per subentry (skip first poll); handle bidirectional mode when `import_meter_entity_id == export_meter_entity_id`; populate `import_cost_delta`, `export_revenue_delta`, `accounting_date_nzt` in `NodeData`
- [ ] T029 [P] [US3] Implement `SettledPriceSensor` in `custom_components/electricityinfo/sensor.py`: `CoordinatorEntity` only; `native_value` = most recent settled period price from `node_data["accounting"]`; `history` attribute = up to `accounting_retention_hours × 2` periods; attributes include `trading_period`, `timestamp`, `node`; unique ID suffix `settled_price`
- [ ] T030 [P] [US3] Implement `ImportCostSensor` in `custom_components/electricityinfo/sensor.py`: `CoordinatorEntity` only; `native_value = node_data["import_cost_delta"]`; attributes include `settled_price`, `energy_kwh`, `import_meter_entity_id`, `trading_period`; `native_unit_of_measurement` = `"c"` if `price_unit="c/kWh"` else `"NZD"`; unique ID suffix `import_cost`
- [ ] T031 [P] [US3] Implement `ExportRevenueSensor` in `custom_components/electricityinfo/sensor.py`: same shape as `ImportCostSensor` but uses `export_revenue_delta` and `export_meter_entity_id`; unique ID suffix `export_revenue`
- [ ] T032 [US3] Implement `DailyImportCostSensor` in `custom_components/electricityinfo/sensor.py`: `CoordinatorEntity` + `RestoreEntity`; `async_added_to_hass` restores `_accumulated_total` and `_accumulation_date`; if restored date < today NZT → reset immediately; `_handle_coordinator_update` applies midnight reset logic (compare `accounting_date_nzt` against `_accumulation_date`) then adds `import_cost_delta`; `state_class = SensorStateClass.TOTAL`; attributes include `accumulation_date`, `import_meter_entity_id`; unique ID suffix `daily_import_cost`
- [ ] T033 [US3] Implement `DailyExportRevenueSensor` in `custom_components/electricityinfo/sensor.py`: same shape as `DailyImportCostSensor` but accumulates `export_revenue_delta` and attributes include `export_meter_entity_id`; unique ID suffix `daily_export_revenue`
- [ ] T034 [US3] Update `sensor.async_setup_entry` in `custom_components/electricityinfo/sensor.py`: when `enable_accounting=True`: always add `SettledPriceSensor`; add `ImportCostSensor` + `DailyImportCostSensor` only if `import_meter_entity_id` set; add `ExportRevenueSensor` + `DailyExportRevenueSensor` only if `export_meter_entity_id` set
- [ ] T035 [US3] Update `custom_components/electricityinfo/translations/en.json`: add strings for `enable_accounting`, `accounting_retention_hours`, `import_meter_entity_id`, `export_meter_entity_id` fields; add error keys `entity_not_energy_import`, `entity_not_energy_export`

**Checkpoint**: `pytest tests/test_accounting.py tests/test_coordinator.py -v` passes. Accounting sensors verified in HA dev with linked energy meter — daily totals survive restart and reset at midnight NZT.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup, type safety, and full acceptance checklist verification.

- [ ] T036 [P] Remove `PriceSensorEntity` class and all remaining 002-era code from `custom_components/electricityinfo/sensor.py` and any unused 002 imports from `custom_components/electricityinfo/const.py`; verify no dead code remains
- [ ] T037 [P] Run `ruff check --fix custom_components/ tests/` and resolve any remaining linting issues
- [ ] T038 [P] Run `mypy custom_components/` and resolve all type errors (ensure `NodeData` TypedDict, `PeriodPrice` TypedDict, and all sensor class return types are annotated correctly)
- [ ] T039 Run `pytest tests/ -v` and verify all tests pass (migration, coordinator, sensor, accounting, integration); confirm test count increases from baseline 64

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on T001/T002 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 completion — CRITICAL PATH (MVP)
- **US2/US4/US5 (Phase 4)**: Depends on Phase 3 completion (coordinator base, config flow base, setup_entry base)
- **US3 (Phase 5)**: Depends on Phase 3 + T020 (error isolation) — accounting builds on coordinator NodeData structure
- **Polish (Phase 6)**: Depends on all prior phases

### User Story Dependencies

| Story | Depends On | Notes |
|-------|-----------|-------|
| US1 (P1) | Phase 2 | Critical path — MVP |
| US2 (P2) | US1 | Extends coordinator, adds forecast sensors |
| US4 (P2) | US1 | Per-node error isolation extends coordinator |
| US5 (P2) | US1 | Reconfigure step extends config flow |
| US3 (P3) | US1, T020 | Accounting adds new coordinator keys and 5 sensor classes |

### Within Each Phase

- Test tasks (T003, T006/T007, T013–T015, T023–T026) MUST be written and confirmed to FAIL before paired implementation tasks
- T008 (config flow) and T009 (coordinator) are independent files — can be worked in parallel
- T017 and T018 (DayAheadForecastSensor, IntradayForecastSensor) are independent — can run in parallel
- T029, T030, T031 (SettledPriceSensor, ImportCostSensor, ExportRevenueSensor) are independent — can run in parallel
- T036, T037, T038 (cleanup, ruff, mypy) are independent — can run in parallel

---

## Parallel Execution Examples

### Phase 3 (US1) Implementation Parallelism

```bash
# These two tasks touch different files and can run concurrently:
Task A: "Implement MarketNodeSubentryFlow in config_flow.py" (T008)
Task B: "Refactor coordinator.py for NodeData/day_ahead fetch" (T009)
# Then sequentially:
Task C: "Implement LivePriceSensor in sensor.py" (T010) — needs T009 NodeData
Task D: "Update sensor.async_setup_entry" (T011) — needs T010
```

### Phase 4 (US2) Sensor Parallelism

```bash
# These three tasks touch different sensor classes in the same file but are non-overlapping:
Task A: "Implement DayAheadForecastSensor" (T017)
Task B: "Implement IntradayForecastSensor" (T018)
```

### Phase 5 (US3) Sensor Parallelism

```bash
# Three sensors are independent:
Task A: "Implement SettledPriceSensor" (T029)
Task B: "Implement ImportCostSensor" (T030)
Task C: "Implement ExportRevenueSensor" (T031)
# Then sequentially (daily totals depend on coordinator delta fields being ready):
Task D: "Implement DailyImportCostSensor" (T032) — needs T028
Task E: "Implement DailyExportRevenueSensor" (T033) — needs T028
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Migration (T003–T005) — **CRITICAL**
3. Complete Phase 3: US1 — Live Price Sensor (T006–T012)
4. **STOP and VALIDATE**: `pytest tests/test_config_flow.py tests/test_sensor.py -v`
5. Configure one node in HA dev — live price sensor shows current period price

### Incremental Delivery

1. **MVP**: Setup + Migration + US1 → live price sensor working on upgraded install
2. **+Forecasting**: US2 (T013–T022) → day-ahead and intraday forecast sensors + multi-node support
3. **+Accounting**: US3 (T023–T035) → settled price, import cost, export revenue, daily totals
4. **Polish**: Phase 6 (T036–T039) → lint, types, full test suite

---

## Notes

- Tests must FAIL before implementation — don't skip this verification step
- Each sensor class has a unique ID suffix defined in `data-model.md` — do not deviate
- `_convert_price` in coordinator is the ONLY place NZD/MWh→display unit conversion happens — never in sensor getters
- `RestoreEntity` is used on exactly THREE sensor classes: `LivePriceSensor`, `DailyImportCostSensor`, `DailyExportRevenueSensor`
- Staleness guard (30 min discard) applies ONLY to `LivePriceSensor` — daily totals never discard their restored value
- Bidirectional meter mode is triggered automatically when `import_meter_entity_id == export_meter_entity_id` (both non-None)
- Run `ruff check --fix` after each phase — pre-commit hooks auto-fix formatting and require re-staging
