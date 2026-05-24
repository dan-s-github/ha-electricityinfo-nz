# Implementation Plan: Multiple Entities for Market Node

**Branch**: `003-multi-entity-market-node` | **Date**: 2026-05-24 | **Spec**: `specs/003-multi-entity-market-node/spec.md`
**Input**: Feature specification from `specs/003-multi-entity-market-node/spec.md`

## Summary

Replace 002 single-sensor subentries with 003 `market_node` subentries that can create live, forecast, and accounting sensors per node under one 30-minute coordinator. Preserve OAuth wrapper-first architecture, migrate 002 entries automatically (dedupe by node), create only `market_node` entities at runtime post-migration, and use forecast retention as API lookback (`back`) where all returned prior periods populate forecast history.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: Home Assistant 2026.3.1, `electricityinfo-nz==1.0.0rc2`, voluptuous selectors, DataUpdateCoordinator, RestoreEntity
**Storage**: Home Assistant config entries/subentries + entity registry/state restoration (no standalone DB)
**Testing**: `pytest`, `pytest-asyncio`, `pytest-homeassistant-custom-component`
**Target Platform**: Home Assistant custom integration runtime (async Python)
**Project Type**: Integration/library-wrapper client (single project)
**Performance Goals**: Within 5 configured market nodes, saving a node config completes <10s in 95% of attempts; selected sensors become available within 3 minutes
**Constraints**: OAuth-only auth; no direct HTTP in integration; single 30-minute coordinator per config entry; ingest-time unit conversion only; one migrated subentry per market node; runtime entity setup uses `market_node` only (no legacy `sensor` entity creation); forecast retention drives forecast history API lookback (`back`) and all returned prior periods are stored in history
**Scale/Scope**: Up to 5 market node subentries per config entry; up to 8 sensors per node; accounting history 24h/48h; day-ahead forward 48 periods; intraday forward 8 periods

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Library API Wrapper First**: PASS — all external price access remains through `electricityinfo-nz`.
- **II. OAuth Token-Based Authentication**: PASS — no auth model change; credentials remain in HA config entry storage.
- **III. Configurable Sensor Architecture**: PASS — all behavior remains config-subentry driven (`market_node` flow).
- **IV. Test-First Methodology**: PASS — tests exist and remain the primary verification surface for migration/coordinator/sensor behavior.
- **V. Semantic Versioning & Breaking Changes**: PASS — 003 remains a breaking schema shift with migration and warning semantics documented.

Post-design constitution check: **PASS** (no justified violations).

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
├── test_accounting.py
├── test_coordinator.py
├── test_init.py
├── test_options_flow.py
└── integration/
    ├── test_sensor_lifecycle.py
    └── test_multi_node.py
```

**Structure Decision**: Single-project Home Assistant integration layout (`custom_components/electricityinfo` + `tests`) is retained; feature artifacts remain under `specs/003-multi-entity-market-node`.

## Phase 0: Outline & Research

Research outputs are captured in `research.md` and cover:
1. 002 → 003 migration semantics (dedupe + runtime legacy-entity prohibition)
2. Coordinator topology and fetch dispatch
3. Ingest-time unit conversion
4. RestoreEntity strategy
5. Accounting computation and meter-link/fallback rules
6. Forecast history retention semantics (`retention` => API `back`, all returned prior periods go to `history`)
7. Midnight NZT daily reset behavior

## Phase 1: Design & Contracts

Design outputs are captured in:
- `data-model.md`
- `contracts/config-flow.md`
- `contracts/sensor-platform.md`
- `quickstart.md`

Design clarifications captured:
- Migration keeps first legacy subentry per node, skips duplicates with warnings.
- Runtime entity creation path post-migration uses only `market_node` subentries.
- Forecast history retention setting drives API lookback (`back`) and all returned prior periods are stored in history.
- Export fallback: when export meter is unset and import meter is set, import is used as signed bidirectional source.

## Agent Context Update

Plan reference between `<!-- SPECKIT START -->` and `<!-- SPECKIT END -->` in `.github/copilot-instructions.md` points to this plan path: `specs/003-multi-entity-market-node/plan.md`.

## Complexity Tracking

No constitution violations requiring justification.
