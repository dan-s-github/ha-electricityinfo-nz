# Implementation Plan: Electricity Price Schedules Sensor Platform

**Branch**: `002-price-schedules-sensor` | **Date**: 2026-05-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-price-schedules-sensor/spec.md`

## Summary

Implement a Home Assistant sensor platform that retrieves electricity price schedules from the Electricityinfo API using OAuth 2.0 Client Credentials authentication. Users configure multiple sensors via Home Assistant config subentries. Each sensor subentry produces two entities (NZD/MWh and c/kWh) sharing one device context and one coordinator update cycle. All sensors share a global 30-minute update schedule with coordinator-driven retry/backoff and unavailable-state behavior.

**Technical Approach**: Single Home Assistant custom integration component using an `async` DataUpdateCoordinator in a dedicated `coordinator.py` module for centralized price schedule fetching. Config flow extends existing OAuth config entry with `ConfigSubentryFlow` support for `sensor` subentries. Sensor platform creates two entities per subentry and associates them with `config_subentry_id`. Price conversion for c/kWh entities is applied from internally stored NZD/MWh values.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**:
- `homeassistant` (Home Assistant core API)
- `electricityinfo-nz` (PyPI library wrapper with OAuth support)
- `pytest-asyncio` (async testing)

**Storage**: Home Assistant state storage (RestoreEntity pattern for current price + forecast array persistence) plus Home Assistant config subentry storage for sensor definitions
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
- `forward_prices_count` is stored in hours; coordinator multiplies × 2 to convert to 30-minute trading period count before calling the API (`forward_prices = forward_hours * 2`)
- Internal canonical value is always stored as NZD/MWh; c/kWh conversion applied at display time via `native_value` property and reversed on state restore
- `SensorDeviceClass.MONETARY` used for all price sensor entities
- Full integration reload is triggered on any subentry change via `add_update_listener` (not a targeted entity update — all sensors briefly reinitialise)
- `async_request_refresh()` is called once per entity in `async_added_to_hass`; with two entities per subentry, two refresh calls fire at startup (benign — the coordinator deduplicates in-flight requests)

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
**Status**: PASS - Design uses Home Assistant config subentries for adding/reconfiguring sensors (FR-002, FR-003). Sensor data is stored per subentry.

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
├── config_flow.py       # MODIFY: Add sensor subentry flow support and reconfigure step
├── const.py             # MODIFY: Add sensor configuration constants
├── coordinator.py       # CREATE: DataUpdateCoordinator implementation
├── sensor.py            # CREATE: Sensor platform (2 entities per subentry)
├── translations/
│   └── en.json          # MODIFY: Add config and subentry flow translations
└── manifest.json        # MODIFY: metadata and field-order compliance

tests/
├── test_config_flow.py                   # MODIFY: OAuth flow and retry tests
├── test_options_flow.py                  # CREATE: Sensor subentry create/reconfigure tests
├── test_sensor.py                        # CREATE: Sensor platform setup tests
├── test_sensor_multiple.py               # CREATE: Multiple subentry behavior tests
├── test_unit_conversion.py               # CREATE: Unit conversion behavior tests
├── test_integration.py                   # CREATE: Integration setup/unload tests
├── fixtures/
│   ├── market_prices.json    # CREATE: Mock price schedule data
│   └── conftest.py           # MODIFY: Add sensor fixtures
└── integration/
    └── __init__.py                         # PRESENT: integration test package scaffold
```

**Structure Decision**: Single custom integration component (electricityinfo) with dedicated coordinator and sensor modules. Config flow logic is built on ConfigSubentryFlow instead of options-list CRUD. No separate packages or sub-projects needed; all scope fits within existing component hierarchy.

## Complexity Tracking

No Constitution violations. All requirements align with established principles:
- Library wrapper usage (electricityinfo-nz) ✅
- OAuth authentication pattern ✅
- Config subentry flow for sensors ✅
- Test-first methodology ✅
- Semantic versioning (incremental feature, no breaking changes) ✅

### Revision: Implementation Sync 2026-05-07
- Reason: Reconciled implementation plan with shipped architecture (config subentries, coordinator module split, dual-entity-per-subentry model, current test topology, and translation/manifest layout).

### Revision: Gap Report Sync 2026-05-09
- Reason: Added six technical constraints discovered during gap analysis: hours×2 trading-period conversion, canonical NZD/MWh internal storage with display-time conversion, SensorDeviceClass.MONETARY choice, full-reload-on-subentry-change mechanism, and async_request_refresh-per-entity-add behavior.
