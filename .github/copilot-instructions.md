<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:

**Active Feature**: RTD-Based Live Price Sensor (004-rtd-live-price)
**Plan Location**: `specs/004-rtd-live-price/plan.md`

Key Design Documents:
- **Specification**: `specs/004-rtd-live-price/spec.md` — User stories, requirements, success criteria
- **Research**: `specs/004-rtd-live-price/research.md` — RTD API parameters, fetch decoupling, interval strategy, test coverage
- **Data Model**: `specs/004-rtd-live-price/data-model.md` — Coordinator data changes (`live_current` source, `rtd` key, constants)
- **Sensor Platform Contract**: `specs/004-rtd-live-price/contracts/sensor-platform.md` — Changed: coordinator cycle, poll interval, LivePriceSensor state contract
- **Quickstart**: `specs/004-rtd-live-price/quickstart.md` — Developer setup, 3 implementation phases, key design invariants

**Constitution**: `.specify/memory/constitution.md` — 5 core principles (OAuth NON-NEGOTIABLE, Library wrapper first, TDD, Configurable sensors, Semantic versioning)

**Technology Stack**:
- Python 3.14+ with Home Assistant 2026.3.1
- electricityinfo-nz==1.0.0rc2 PyPI library (OAuth Client Credentials flow)
- Home Assistant DataUpdateCoordinator (single **5-minute** coordinator per config entry for all sensor types)
- Home Assistant RestoreEntity (LivePriceSensor + DailyImportCostSensor + DailyExportRevenueSensor; all other sensors start unavailable)
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
- **004 is a surgical change**: only `const.py`, `coordinator.py`, and `manifest.json` are modified; no config schema change
- **Single 5-min coordinator**: `UPDATE_INTERVAL_MINUTES = 5` (was 30); applies unconditionally to all config entries with any active subentry
- **Live price from RTD**: `LivePriceSensor` state = current trade period price from RTD `schedule="RTD"`, `back=3` response; `forward` omitted
- **RTD decoupled from day-ahead**: RTD call fires only when `enable_live_price=True`; day-ahead PRSL/NRSL call fires only when `enable_forecast=True` with day-ahead horizon (no longer shared)
- **RTD price field**: `PriceDetail.price` (not `price6s` or `price60s`)
- **`RTD_BACK_PERIODS = 3`**: new constant; covers ~90 min of history; never inline the literal
- **`live_current` shape unchanged**: same dict structure (`timestamp`, `trading_period`, `node`, `schedule`, `price`); `schedule` value changes from `"PRSL"/"NRSL"` to `"RTD"`
- **MINOR version bump**: e.g. `2.0.0` → `2.1.0`; no breaking schema changes
- **Unit conversion at ingest**: unchanged from 003
- **Selective RestoreEntity**: unchanged from 003 (30-min staleness guard on LivePriceSensor still appropriate)
- **Accounting, forecast sensors**: unchanged beyond accommodating 5-min poll cadence

**Prior Phase Dependency**:
Phase 1 (001-oauth-config-flow) completed: OAuth 2.0 authentication, token management, config flow validation.
Phase 2 (002-price-schedules-sensor) replaced by Phase 3 (003): 002 config entries automatically migrated to 003.
Phase 3 (003-multi-entity-market-node) completed: all 72 tests passing; clean ruff + mypy baseline.

**Implementation Status (Current Branch)**:
- Planning complete (research.md, data-model.md, contracts/, quickstart.md generated).
- Implementation not yet started.
- Baseline from 003: `pytest tests/` (72 tests), `ruff check custom_components/ tests/`, `mypy custom_components/` — all clean.

**Pre-commit Note**: Repository has pre-commit hooks that auto-fix formatting (trailing whitespace, EOF).
Changes made by hooks require re-staging and re-committing. This is expected behavior.

<!-- SPECKIT END -->
