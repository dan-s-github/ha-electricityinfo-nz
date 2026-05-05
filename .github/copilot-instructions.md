<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:

**Active Feature**: Electricity Price Schedules Sensor Platform (002-price-schedules-sensor)
**Plan Location**: `specs/002-price-schedules-sensor/plan.md`

Key Design Documents:
- **Specification**: `specs/002-price-schedules-sensor/spec.md` — User stories, requirements, success criteria
- **Research**: `specs/002-price-schedules-sensor/research.md` — Technology decisions (DataUpdateCoordinator, Options Flow, unit conversion, error handling)
- **Data Model**: `specs/002-price-schedules-sensor/data-model.md` — Entity definitions (SensorConfiguration, PriceSensorEntity, MarketPriceSchedule)
- **Config Flow Contract**: `specs/002-price-schedules-sensor/contracts/config-flow.md` — Options Flow UI/UX for sensor management
- **Sensor Platform Contract**: `specs/002-price-schedules-sensor/contracts/sensor-platform.md` — Entity lifecycle, state persistence, update mechanism
- **Quickstart**: `specs/002-price-schedules-sensor/quickstart.md` — Developer setup, implementation phases, testing strategy

**Constitution**: `.specify/memory/constitution.md` — 5 core principles (OAuth NON-NEGOTIABLE, Library wrapper first, TDD, Configurable sensors, Semantic versioning)

**Technology Stack**:
- Python 3.14+ with Home Assistant 2026.3.1
- electricityinfo-nz PyPI library (OAuth Client Credentials flow)
- Home Assistant DataUpdateCoordinator (30-minute global update cycle)
- Home Assistant RestoreEntity (state persistence across restarts)
- pytest + pytest-asyncio (mocked API responses in CI)
- Home Assistant config flow framework (Options Flow for sensor configuration)

**Build Commands**:
```bash
uv sync                           # Install dependencies
pytest tests/                     # Run tests (mocked API)
ruff check --fix                  # Lint and fix
mypy custom_components/           # Type check
pytest tests/integration/ -v      # Integration tests
# pytest tests/manual_live_api_test.py -v  # Optional: live API tests with credentials
```

**Key Design Decisions**:
- **Global 30-minute update cycle**: All sensors share single DataUpdateCoordinator (not per-sensor configurable in v1)
- **Options Flow**: Users add/edit/remove sensors via Settings > Devices & Services > Options (single list in config entry)
- **State persistence**: RestoreEntity stores current price + forecast array; restored on HA restart
- **Partial data**: Accepted as valid (graceful degradation if API returns incomplete data)
- **Error recovery**: Exponential backoff (1 min first retry); mark unavailable after second failure; auto-recover on success
- **Unit conversion**: Applied at display time (native unit always NZD/MWh internally; convert to c/kWh for UI if needed)
- **Testing**: Mocked API in CI (fast, deterministic); optional manual tests with live API credentials

**Prior Phase Dependency**:
Phase 1 (001-oauth-config-flow) completed: OAuth 2.0 authentication, token management, config flow validation.
Phase 2 (002-price-schedules-sensor) builds on Phase 1: reuses OAuth credentials, extends config flow with Options for sensors.

**Pre-commit Note**: Repository has pre-commit hooks that auto-fix formatting (trailing whitespace, EOF).
Changes made by hooks require re-staging and re-committing. This is expected behavior.

<!-- SPECKIT END -->
