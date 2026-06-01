# Implementation Plan: Accounting Sensor Meter Entity Requirements

**Branch**: `005-accounting-sensors` | **Date**: 2026-06-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/005-accounting-meter-requirements/spec.md`

## Summary

Surgical changes to `config_flow.py`, `coordinator.py`, and `sensor.py` to:
1. Tighten meter entity validation (reject utility meters via `last_reset` attribute check; reject same-entity import/export pairs)
2. Extend DailyAccountingSensorBase to capture _previous_day_total at day rollover, persisted via HA state attributes
3. Add `PreviousDayImportCostSensor` and `PreviousDayExportRevenueSensor` as new RestoreEntity sensors, each holding a cross-sensor reference to their paired daily sensor
4. Remove the bidirectional same-entity delta-splitting code path from the coordinator

No config schema changes. No new constants. MINOR version bump (new sensors added).

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: homeassistant 2026.3.1, electricityinfo-nz==1.0.0rc2, pytest-homeassistant-custom-component
**Storage**: HA state machine (RestoreEntity for daily + previous-day sensors)
**Testing**: pytest + pytest-asyncio + pytest-homeassistant-custom-component (mocked API)
**Target Platform**: Home Assistant custom component (async event loop)
**Project Type**: HA custom integration (library wrapper)
**Performance Goals**: No change — single 5-min coordinator per config entry
**Constraints**: Must not break existing 80 tests; all changes confined to 4 source files + translations
**Scale/Scope**: Per-subentry sensor set (2–4 new sensor instances per accounting-enabled subentry)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Principle I — Library API Wrapper First**: No new HTTP code. All API calls remain through `AsyncMarketPricesClient`.
- [x] **Principle II — OAuth (NON-NEGOTIABLE)**: No auth changes. OAuth flow unchanged.
- [x] **Principle III — Configurable Sensor Architecture**: New sensors follow existing config subentry pattern. No hard-coded sensors.
- [x] **Principle IV — TDD (NON-NEGOTIABLE)**: New tests written before implementation per quickstart.md phases.
- [x] **Principle V — Semantic Versioning**: New sensors = MINOR bump. No breaking config schema changes.
- [x] **Principle VI — Documentation Synchronization**: New sensors + updated validation messages are user-facing. README update is an explicit task in quickstart.md Phase 4.

All gates pass. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/005-accounting-meter-requirements/
├── plan.md              ← this file
├── research.md          ← Phase 0 output (all unknowns resolved via clarification session)
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── sensor-platform.md   ← Phase 1 output
└── tasks.md             ← Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code

```text
custom_components/electricityinfo/
├── config_flow.py         # _validate_meter_entity: add last_reset check; add same-entity check
├── coordinator.py         # Remove bidirectional same-entity code path; add runtime same-entity guard
├── sensor.py              # Extend DailyAccountingSensorBase with _previous_day_total snapshot;
│                          # add PreviousDayImportCostSensor + PreviousDayExportRevenueSensor
└── strings.json           # New error key: same_entity_import_export

custom_components/electricityinfo/translations/
└── en.json                # Error message for same_entity_import_export

tests/
├── test_accounting.py     # New test cases: previous-day sensors, validation, rollover atomicity
└── test_config_flow.py    # New test cases: last_reset rejection, same-entity rejection
```

**Structure Decision**: Single-project, surgical-change pattern (same as 004). Only 4 source files modified. No new config schema, no new constants, no manifest changes.

## Complexity Tracking

> No constitution violations. No complexity justification required.
