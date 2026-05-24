# Research: Multiple Entities for Market Node

**Branch**: `003-multi-entity-market-node` | **Date**: 2026-05-24

## 1. HA Config Entry Migration (002 → 003)

**Decision**: Implement `async_migrate_entry(hass, entry)` in `__init__.py`; keep `ConfigFlow.VERSION = 2`; migrate legacy `sensor` subentries into `market_node` subentries and dedupe by node.

**Rationale**:
- Home Assistant invokes `async_migrate_entry` for lower-version stored entries.
- Migration preserves user configuration intent while moving to the new schema.
- Dedupe-by-node enforces one 003 subentry per market node.

**Clarified migration/runtime rule**:
- Historical prices are not migrated from storage; pricing is fetched normally after migration.
- After migration, runtime setup creates `market_node` entities only; legacy `sensor` entities are not created.

**Alternatives considered**:
- Force manual reconfiguration (rejected: poor UX)
- Coexist legacy/new runtime entity paths indefinitely (rejected: complexity and drift)

---

## 2. Config Subentry Flow Shape

**Decision**: Keep a single market-node config/reconfigure step with section toggles and validation in Python.

**Rationale**:
- Matches HA config-flow patterns.
- Keeps cross-field validation centralized (sensor enablement, meter validation, dedupe).

**Alternatives considered**:
- Multi-step flow (rejected: extra UI complexity without stronger safety)

---

## 3. Coordinator Topology

**Decision**: One `DataUpdateCoordinator` per config entry, polling every 30 minutes for all subentries and sensor types.

**Rationale**:
- Shared fetch/update cycle reduces redundant calls.
- Enables per-node error isolation while preserving update consistency.

**Alternatives considered**:
- Per-sensor-type coordinators (rejected: unnecessary complexity and duplicate calls)

---

## 4. Forecast and Live Price Fetch Strategy

**Decision**:
- Live price uses day-ahead forecast response (`PRSL`/`NRSL`, `forward=48`) by selecting current trade period.
- Forecast sensors:
  - Day-ahead: `forward=48`
  - Intraday: `forward=8`

**Rationale**:
- Single source for current + forecast data reduces API churn and state divergence.

**Alternatives considered**:
- Separate dedicated live endpoint/fetch path (rejected: duplicate semantics)

---

## 5. Forecast History Retention Semantics

**Decision**: Forecast retention setting defines the API history lookback (`back`) window, and all prior trade periods returned in that window are stored in the forecast sensor `history` attribute.

**Rationale**:
- Makes retention behavior explicit and testable.
- Aligns user expectation (“retention defines kept history”) with fetch behavior.

**Alternatives considered**:
- Derived multiplier history windows (e.g., `2× retention`) (rejected: less intuitive and now superseded by clarified requirement)

---

## 6. Accounting Data Source and Meter Delta Rules

**Decision**:
- Settled pricing source: `Interim`, `back=48`.
- Per-period cost/revenue uses meter deltas (current − previous).
- Export fallback: if export meter missing and import set, import acts as signed bidirectional source.

**Rationale**:
- Interim provides practical near-real-time settled behavior.
- Delta-based accounting is compatible with cumulative HA energy meters.

**Alternatives considered**:
- `Final` for near-real-time settled values (rejected: publication lag)

---

## 7. RestoreEntity Scope

**Decision**:
- `RestoreEntity`: `LivePriceSensor`, `DailyImportCostSensor`, `DailyExportRevenueSensor`
- Others start unavailable until coordinator refresh.

**Rationale**:
- Preserves useful startup continuity where stale risk is acceptable.
- Avoids presenting stale structured forecast/per-period accounting data.

---

## 8. Midnight NZT Daily Reset

**Decision**: Daily totals reset based on NZT date rollover detected from coordinator accounting payload (`accounting_date_nzt`).

**Rationale**:
- Works naturally with 30-minute trade period cadence.
- Keeps reset behavior deterministic and testable.

---

## 9. Unit Conversion

**Decision**: Convert NZD/MWh at ingest and store in selected native unit (`c/kWh` or `NZD/kWh`); no runtime conversion in sensor property getters.

**Rationale**:
- Eliminates repeated conversion logic in entities.
- Keeps sensor state/attributes internally consistent.
