# Implementation Plan: Multiple Entities for Market Node

**Branch**: `003-multi-entity-market-node` | **Date**: 2026-05-24 | **Spec**: `specs/003-multi-entity-market-node/spec.md`
**Input**: Feature specification from `specs/003-multi-entity-market-node/spec.md`

## Summary

Replace 002 single-sensor subentries with 003 market-node subentries that can create live, forecast, and accounting sensors per node, backed by one 30-minute coordinator. Keep OAuth wrapper-first architecture, migrate 002 entries automatically, enforce one migrated entry per `market_node`, and support accounting export fallback to import meter when export meter is not configured.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: Home Assistant 2026.3.1, `electricityinfo-nz==1.0.0rc2`, voluptuous selectors, DataUpdateCoordinator, RestoreEntity
**Storage**: Home Assistant config entries/subentries + entity registry/state restoration (no standalone DB)
**Testing**: `pytest`, `pytest-asyncio`, `pytest-homeassistant-custom-component`
**Target Platform**: Home Assistant custom integration runtime (async Python)
**Project Type**: Integration/library-wrapper client (single project)
**Performance Goals**: New/updated sensors visible within 3 minutes of config completion (SC-001); support up to 5 configured nodes without observable HA UI degradation (SC-003)
**Constraints**: OAuth-only auth; no direct HTTP in integration; single 30-minute coordinator per config entry; prices converted at ingest to selected unit; one migrated entry per `market_node`; if export meter is unset and import meter is set, treat import meter as signed bidirectional source for export calculations
**Scale/Scope**: Up to 5 market node subentries per config entry; up to 8 sensors per node; 24h/48h accounting history; 48 day-ahead periods and 8 intraday periods

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Library API Wrapper First**: PASS — plan keeps all API access through `electricityinfo-nz` wrapper.
- **II. OAuth Token-Based Authentication**: PASS — no auth model changes; config entry remains OAuth credentials only.
- **III. Configurable Sensor Architecture**: PASS — all behavior driven by config subentries (`market_node`).
- **IV. Test-First Methodology**: PASS — quickstart and tasks sequencing keep migration/coordinator/sensor work test-first.
- **V. Semantic Versioning & Breaking Changes**: PASS — 003 is breaking vs 002 and plan preserves migration + warning behavior.

Post-design constitution check: **PASS** (no justified violations required).

## Project Structure

### Documentation (this feature)

```text
specs/003-multi-entity-market-node/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── config-flow.md
│   └── sensor-platform.md
└── tasks.md
```

### Source Code (repository root)

```text
custom_components/electricityinfo/
├── __init__.py
├── config_flow.py
├── const.py
├── coordinator.py
├── sensor.py
├── manifest.json
└── translations/en.json

tests/
├── test_config_flow.py
├── test_sensor.py
├── test_sensor_multiple.py
├── test_unit_conversion.py
├── test_init.py
├── integration/
│   └── test_sensor_lifecycle.py
└── live/
    └── test_schedule_date_range.py
```

**Structure Decision**: Single-project Home Assistant integration layout (`custom_components/electricityinfo` + `tests`) is retained; feature artifacts stay under `specs/003-multi-entity-market-node`.

## Phase 0: Outline & Research

Research outputs are captured in `research.md` and resolve architecture decisions for:
1. 002 → 003 migration semantics and config versioning
2. Coordinator topology and fetch dispatch
3. Unit conversion at ingest
4. RestoreEntity strategy
5. Accounting computation and meter-link rules
6. Live price extraction from forecast data
7. Midnight NZT daily reset behavior

## Phase 1: Design & Contracts

Design outputs are captured in:
- `data-model.md`
- `contracts/config-flow.md`
- `contracts/sensor-platform.md`
- `quickstart.md`

Design includes these clarified rules:
- Migration keeps the first legacy entry when duplicates resolve to the same `market_node`; later duplicates are skipped with warnings.
- Accounting uses two optional selectors, but if `export_meter_entity_id` is unset and `import_meter_entity_id` is set, export calculations use the import meter in signed bidirectional mode.

## Agent Context Update

Updated `.github/copilot-instructions.md` within `<!-- SPECKIT START -->` and `<!-- SPECKIT END -->` to keep plan/design references aligned with this plan and latest clarifications.

## Complexity Tracking

No constitution violations requiring justification.
