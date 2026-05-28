<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:

**Active Feature**: Multiple Entities for Market Node (003-multi-entity-market-node)
**Plan Location**: `specs/003-multi-entity-market-node/plan.md`

Key Design Documents:
- **Specification**: `specs/003-multi-entity-market-node/spec.md` — User stories, requirements, success criteria
- **Research**: `specs/003-multi-entity-market-node/research.md` — Technology decisions (migration, coordinator, unit conversion, RestoreEntity, accounting)
- **Data Model**: `specs/003-multi-entity-market-node/data-model.md` — Entity definitions (MarketNodeSubentry, CoordinatorData, 8 sensor classes, PeriodPrice)
- **Config Flow Contract**: `specs/003-multi-entity-market-node/contracts/config-flow.md` — MarketNodeSubentryFlow schema and validation
- **Sensor Platform Contract**: `specs/003-multi-entity-market-node/contracts/sensor-platform.md` — Entity lifecycle, update mechanism, state/attribute contracts
- **Quickstart**: `specs/003-multi-entity-market-node/quickstart.md` — Developer setup, implementation phases, testing strategy

**Constitution**: `.specify/memory/constitution.md` — 5 core principles (OAuth NON-NEGOTIABLE, Library wrapper first, TDD, Configurable sensors, Semantic versioning)

**Technology Stack**:
- Python 3.14+ with Home Assistant 2026.3.1
- electricityinfo-nz==1.0.0rc2 PyPI library (OAuth Client Credentials flow)
- Home Assistant DataUpdateCoordinator (single 30-minute coordinator for all sensor types)
- Home Assistant RestoreEntity (LivePriceSensor + DailyImportCostSensor + DailyExportRevenueSensor; all other sensors start unavailable)
- pytest + pytest-asyncio + pytest-homeassistant-custom-component (mocked API in CI)
- Home Assistant Config Subentry Flow (MarketNodeSubentryFlow replaces SensorSubentryFlow)

**Build Commands**:
```bash
uv sync                           # Install dependencies
pytest tests/                     # Run tests (mocked API)
ruff check --fix                  # Lint and fix
mypy custom_components/           # Type check
pytest tests/integration/ -v      # Integration tests
pytest tests/live/ -v -m live_api # Optional: live API tests (requires .env)
```

**Key Design Decisions**:
- **003 replaces 002 entirely**: `async_migrate_entry` migrates VERSION 1 → 2; for duplicate legacy entries targeting the same `market_node`, keep the first and skip later duplicates with warnings; entity IDs change (log warnings)
- **Single 30-min coordinator**: All sensor types (live, forecast, accounting) share one DataUpdateCoordinator per config entry
- **Live price from forecast**: `LivePriceSensor` state = current trade period price from PRSL/NRSL `forward=48` response
- **Unit conversion at ingest**: Prices stored in user-selected unit (c/kWh or NZD/kWh); no runtime conversion in sensors
- **Forecast history retention**: `forecast_retention_hours` defines forecast API lookback (`back`) and all returned prior trade periods are stored in sensor `history`
- **Selective RestoreEntity**: `LivePriceSensor` (staleness guard 30 min), `DailyImportCostSensor`, `DailyExportRevenueSensor` (restore daily accumulated total + date); all other sensors start unavailable on restart
- **Accounting via Interim back=48**: Settled price sourced from Interim schedule (back=48 = 24h history); supports daily total rebuild after restart
- **Three-tier accounting**: Settled price always; import cost + export revenue (per-period) when an effective import/export source exists; if `export_meter_entity_id` is unset but `import_meter_entity_id` is set, reuse import as signed bidirectional source for export calculations; daily totals follow the same effective-source rule
- **Two energy meter selectors**: `import_meter_entity_id` and `export_meter_entity_id` (both optional); if same entity ID (or export is omitted while import is set) → bidirectional signed delta mode
- **Daily totals (midnight NZT reset)**: `DailyImportCostSensor` + `DailyExportRevenueSensor` accumulate since midnight NZT; coordinator detects date advance via `accounting_date_nzt` field; up to ~30 min delay accepted
- **Energy delta computation**: Coordinator stores previous meter reading; delta = current − previous per poll; first poll after startup skips that period
- **Poll boundary alignment**: Integration cannot enforce :00/:30 alignment; users automate HA reload at :01/:31 if needed
- **Subentry type key**: `"market_node"` (replaced `"sensor"` from 002)
- **Post-migration runtime entities**: Setup path creates `market_node` entities only; legacy `sensor` entities are not created

**Prior Phase Dependency**:
Phase 1 (001-oauth-config-flow) completed: OAuth 2.0 authentication, token management, config flow validation.
Phase 2 (002-price-schedules-sensor) replaced by Phase 3 (003): 002 config entries automatically migrated to 003.

**Implementation Status (Current Branch)**:
- All phases (1–8) fully implemented and verified for `003-multi-entity-market-node`.
- T045–T051 remediation complete: legacy `PriceSensorEntity`/`SensorSubentryFlowHandler` removed; export meter `None` fix; `available` property corrected; forecast/history boundary fixed; startup prime-call restored in `SettledPriceSensor`.
- Startup fetch clarified (2026-05-27): non-RestoreEntity sensors call `_handle_coordinator_update()` in `async_added_to_hass` to prime from coordinator data fetched during `async_config_entry_first_refresh()` — available immediately after entry setup.
- Regression baseline: `pytest tests/` (72 tests), `ruff check custom_components/ tests/`, `mypy custom_components/` — all clean.

**Pre-commit Note**: Repository has pre-commit hooks that auto-fix formatting (trailing whitespace, EOF).
Changes made by hooks require re-staging and re-committing. This is expected behavior.

<!-- SPECKIT END -->
