# Implementation Plan: RTD-Based Live Price Sensor

**Branch**: `004-rtd-live-price` | **Date**: 2026-05-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/004-rtd-live-price/spec.md`

## Summary

Change the `LivePriceSensor` data source from the PRSL/NRSL day-ahead forecast schedule to the RTD (Real-Time Dispatch) schedule, and reduce the coordinator poll interval from 30 minutes to 5 minutes. A new dedicated RTD API call (`schedule="RTD"`, `back=3`, no `forward`) is added to `coordinator.py` and fires only when `enable_live_price=True`. The existing day-ahead forecast call is decoupled and now fires only for forecast sensors. No config schema changes are required; this is a MINOR version bump.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: electricityinfo-nz==1.0.0rc2, homeassistant 2026.3.1, pytest, pytest-asyncio, pytest-homeassistant-custom-component
**Storage**: N/A — coordinator holds in-memory data only
**Testing**: pytest + pytest-asyncio + pytest-homeassistant-custom-component (mocked API in CI)
**Target Platform**: Home Assistant custom integration (Linux/macOS)
**Project Type**: Home Assistant custom integration
**Performance Goals**: RTD price available within 5 min of publication; coordinator cycle completes in <30 s
**Constraints**: `back=3` (1–48 valid); `forward` omitted (None) for RTD call; MINOR version bump only (no config schema change)
**Scale/Scope**: Single market node per subentry; typical residential HA user

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library API Wrapper First | ✅ Pass | New RTD call uses `AsyncMarketPricesClient.get_schedule_prices`; no direct HTTP |
| II. OAuth Authentication (NON-NEGOTIABLE) | ✅ Pass | No auth changes; existing OAuth credentials unchanged |
| III. Configurable Sensor Architecture | ✅ Pass | RTD call gated on existing `enable_live_price` config flag; no new config options |
| IV. Test-First (NON-NEGOTIABLE) | ✅ Pass | RTD tests written before implementation; existing tests updated |
| V. Semantic Versioning | ✅ Pass | New behavior, no schema change → MINOR bump (e.g. 2.0.0 → 2.1.0) |

**Post-design re-check**: ✅ All principles hold. Data model confirms no schema migration needed. Coordinator refactor stays within library wrapper contract.

## Project Structure

### Documentation (this feature)

```text
specs/004-rtd-live-price/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── sensor-platform.md   # Updated coordinator update cycle + LivePriceSensor state contract
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
custom_components/electricityinfo/
├── const.py             # UPDATE_INTERVAL_MINUTES: 30 → 5; add RTD_BACK_PERIODS = 3; add LIVE_PRICE_RESTORE_STALENESS_MINUTES = 30
├── coordinator.py       # New RTD fetch block; decouple live price from day-ahead fetch; _extract_live_price_payload updated to max() selection
├── sensor.py            # Remove day_ahead fallback; update staleness guard constant; add history attribute to LivePriceSensor
└── manifest.json        # MINOR version bump

tests/
├── test_coordinator.py  # Update interval assertions; add RTD fetch tests
├── conftest.py          # Add RTD mock fixture
└── (existing test files unchanged unless interval assertions present)
```

**Structure Decision**: Single HA custom integration project. Changes are surgical: two source files modified (`const.py`, `coordinator.py`), tests updated to match.

### Revision: Implementation Sync 2026-05-31
- Reason: Project structure updated to include `sensor.py` as a modified file (removed day_ahead fallback, staleness guard constant update, `history` attribute addition). `_extract_live_price_payload` was changed from a 30-minute window lookup to `max(past, key=trading_datetime)` — reflected in tasks.md Invariant 1.
