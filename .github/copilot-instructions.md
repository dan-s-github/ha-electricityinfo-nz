<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:

**Active Feature**: Accounting Sensor Meter Entity Requirements (005-accounting-meter-requirements)
**Plan Location**: `specs/005-accounting-meter-requirements/plan.md`

Key Design Documents:
- **Specification**: `specs/005-accounting-meter-requirements/spec.md` — User stories, requirements, success criteria
- **Research**: `specs/005-accounting-meter-requirements/research.md` — Clarification decisions: W→kWh helper, bidirectional two-helper pattern, utility meter detection, same-entity rejection, previous-day sensors
- **Data Model**: `specs/005-accounting-meter-requirements/data-model.md` — Coordinator accumulation refactor, new node_data keys, new sensor classes, validation changes
- **Sensor Platform Contract**: `specs/005-accounting-meter-requirements/contracts/sensor-platform.md` — New sensor state contracts, updated validation contract, removed bidirectional code path
- **Quickstart**: `specs/005-accounting-meter-requirements/quickstart.md` — Developer setup, 5 implementation phases, key design invariants

**Constitution**: `.specify/memory/constitution.md` — 6 core principles (OAuth NON-NEGOTIABLE, Library wrapper first, TDD, Configurable sensors, Semantic versioning, Documentation Synchronization)

**Technology Stack**:
- Python 3.14+ with Home Assistant 2026.3.1
- electricityinfo-nz==1.0.0rc2 PyPI library (OAuth Client Credentials flow)
- Home Assistant DataUpdateCoordinator (single **5-minute** coordinator per config entry for all sensor types)
- Home Assistant RestoreEntity (LivePriceSensor + DailyImportCostSensor + DailyExportRevenueSensor + PreviousDayImportCostSensor + PreviousDayExportRevenueSensor)
- pytest + pytest-asyncio + pytest-homeassistant-custom-component (mocked API in CI)
- Home Assistant Config Subentry Flow (MarketNodeSubentryFlow — unchanged from 003)

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
- **005 is a surgical change**: only `config_flow.py`, `coordinator.py`, `sensor.py`, `strings.json`, `translations/en.json` modified; no config schema change
- **Daily sensors still own accumulation**: `_accumulated_total` stays on sensor; at day rollover `_previous_day_total = _accumulated_total` captured before reset; stored in HA state attributes for RestoreEntity persistence
- **Previous-day sensors use cross-sensor reference**: `PreviousDayImportCostSensor` holds a ref to `DailyImportCostSensor` and reads `daily_sensor._previous_day_total`; no coordinator data needed; no startup-ordering issues
- **Utility meter rejection**: `_validate_meter_entity` adds `"last_reset" not in state.attributes`; rejects HA utility meter helpers; accepts Riemann sum integration helpers and native cumulative sensors
- **Same-entity hard error in config flow**: `errors["base"] = "same_entity_import_export"` when import and export meter IDs are identical
- **Runtime guard for legacy same-entity configs**: coordinator logs warning and skips accounting if `import_meter == export_meter`; protects existing saved configs that predate this feature
- **Bidirectional coordinator code path removed**: `bidirectional` variable and `if bidirectional:` branch deleted; `or import_meter` export fallback also removed
- **MINOR version bump**: new sensors added, no breaking config schema changes

**Prior Phase Dependency**:
Phase 1 (001-oauth-config-flow) completed: OAuth 2.0 authentication, token management, config flow validation.
Phase 2 (002-price-schedules-sensor) replaced by Phase 3 (003): 002 config entries automatically migrated to 003.
Phase 3 (003-multi-entity-market-node) completed: all 72 tests passing; clean ruff + mypy baseline.
Phase 4 (004-rtd-live-price) completed: RTD live price sensor, 5-min coordinator interval; all 80 tests passing.

**Implementation Status (Current Branch)**:
- Planning complete: spec, research, data-model, contracts, quickstart all written.
- Baseline: all 80 tests green; clean ruff + mypy.
- Implementation not yet started (use `/speckit-tasks` to generate task list).

**Pre-commit Note**: Repository has pre-commit hooks that auto-fix formatting (trailing whitespace, EOF).
Changes made by hooks require re-staging and re-committing. This is expected behavior.

<!-- SPECKIT END -->
