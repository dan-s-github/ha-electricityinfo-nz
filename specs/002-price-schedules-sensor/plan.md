# Implementation Plan: Electricity Price Schedules Sensor Platform

**Branch**: `002-price-schedules-sensor` | **Date**: 2026-05-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-price-schedules-sensor/spec.md`

## Summary

Implement a Home Assistant sensor platform that retrieves electricity price schedules from the Electricityinfo API using OAuth 2.0 Client Credentials authentication. Users can configure multiple price sensors via Home Assistant Options Flow, each displaying current and forecast prices in their preferred unit (NZD/MWh or c/kWh). All sensors share a global 30-minute update cycle with graceful error recovery (exponential backoff, unavailable state, automatic recovery).

**Technical Approach**: Single Home Assistant custom integration component using `async` DataUpdateCoordinator pattern for centralized price schedule fetching. Config flow extends existing OAuth config entry to add sensor list. Sensor platform exposes entities derived from SensorConfiguration list. Price unit conversion applied at display time.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**:
- `homeassistant` (Home Assistant core API)
- `electricityinfo-nz` (PyPI library wrapper with OAuth support)
- `pytest-asyncio` (async testing)

**Storage**: Home Assistant state storage (RestoreEntity pattern for current price + forecast array persistence)
**Testing**: pytest with Home Assistant testing utilities; mocked Electricityinfo API responses in CI; optional manual live API tests
**Target Platform**: Home Assistant 2026.3.1+ (custom integration component)
**Project Type**: Home Assistant custom integration (sensor platform + config flow)
**Performance Goals**: 30-minute update interval; 5-minute visibility window for new sensor configuration
**Constraints**:
- Global update cycle (not per-sensor configurable in v1)
- OAuth token refresh delegated to electricityinfo-nz library
- No direct HTTP code (all API calls via library wrapper)
- Price unit conversion: 1 NZD/MWh = 0.1 c/kWh (simple linear)
- Exponential backoff: 1-minute retry after first failure, unavailable after second failure

**Scale/Scope**:
- Support minimum 5 simultaneous sensors
- 99% uptime when API available
- 90% config changes effective within 2 minutes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Gate 1: Library API Wrapper First ✅ PASS
**Requirement**: Every feature integrating with external APIs MUST use a PyPI library wrapper as the single source of truth.
**Status**: PASS - Design specifies electricityinfo-nz PyPI library wrapper for all Electricityinfo API calls (FR-001). No custom HTTP code.

### Gate 2: OAuth Token-Based Authentication (NON-NEGOTIABLE) ✅ PASS
**Requirement**: All integration connections require OAuth API token authentication with secure handling.
**Status**: PASS - Design specifies OAuth 2.0 Client Credentials via electricityinfo-nz library (FR-001, FR-008). Token refresh delegated to library. No token logging. Config flow validates before save.

### Gate 3: Configurable Sensor Architecture ✅ PASS
**Requirement**: All sensors MUST be configurable via Home Assistant config flow.
**Status**: PASS - Design specifies Options Flow for adding/editing/removing sensors (FR-002, FR-003). Sensor list stored in config entry.

### Gate 4: Test-First Methodology (NON-NEGOTIABLE) ✅ PASS
**Requirement**: TDD mandatory with unit tests covering library wrapper and mocked OAuth tokens.
**Status**: PASS - Design specifies pytest with mocked Electricityinfo API responses in CI (Q5 clarification). Integration tests cover config flow, OAuth validation, sensor platform lifecycle.

### Gate 5: Semantic Versioning & Breaking Changes ✅ PASS
**Requirement**: Version format MAJOR.MINOR.PATCH with clear breaking change policy.
**Status**: PASS - Feature is incremental (new sensor platform); no breaking changes to existing OAuth config entry.

**Constitution Check Result**: ✅ ALL GATES PASS - Proceed to Phase 0 Research

## Project Structure

### Documentation (this feature)

```text
specs/002-price-schedules-sensor/
├── plan.md              # This file (Implementation plan)
├── research.md          # Phase 0: Technology decisions and patterns (TO BE GENERATED)
├── data-model.md        # Phase 1: Entity definitions and relationships (TO BE GENERATED)
├── quickstart.md        # Phase 1: Developer setup and testing guide (TO BE GENERATED)
├── contracts/           # Phase 1: Design contracts (TO BE GENERATED)
│   ├── config-flow.md   # Config flow UI/UX contract
│   ├── sensor-platform.md  # Sensor entity platform contract
│   └── data-model.md    # State/attribute structure contract
└── checklists/
    └── requirements.md  # Quality checklist (COMPLETE)
```

### Source Code (repository root)

```text
custom_components/electricityinfo/
├── config_flow.py       # MODIFY: Add options flow steps for sensor configuration
├── const.py             # MODIFY: Add sensor configuration constants
├── sensor.py            # CREATE: New sensor platform implementation
├── models/              # MODIFY: Add SensorConfiguration, MarketPrices models
└── manifest.json        # No changes (OAuth already configured)

tests/
├── test_config_flow_sensor_options.py    # CREATE: Options flow tests for sensors
├── test_sensor_platform.py               # CREATE: Sensor platform tests
├── fixtures/
│   ├── market_prices.json    # CREATE: Mock price schedule data
│   └── conftest.py           # MODIFY: Add sensor fixtures
└── integration/
    └── test_sensor_end_to_end.py         # CREATE: E2E sensor tests
```

**Structure Decision**: Single custom integration component (electricityinfo) with new sensor platform module. Extends existing config flow with Options flow steps. No separate packages or sub-projects needed—all scope fits within existing component hierarchy. Config flow logic already established (Phase 1: OAuth); sensor platform is logical Phase 2 addition.

## Complexity Tracking

No Constitution violations. All requirements align with established principles:
- Library wrapper usage (electricityinfo-nz) ✅
- OAuth authentication pattern ✅
- Config flow for sensors ✅
- Test-first methodology ✅
- Semantic versioning (incremental feature, no breaking changes) ✅
