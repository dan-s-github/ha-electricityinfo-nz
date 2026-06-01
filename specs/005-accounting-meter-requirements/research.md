# Research: Accounting Sensor Meter Entity Requirements

**Branch**: `005-accounting-sensors` | **Date**: 2026-06-01

All design questions were resolved in the clarification session on 2026-06-01. No external API research needed (accounting uses existing `schedule="Interim"` call, unchanged).

---

## 1. W→kWh Integration — Coordinator or HA Helper?

**Decision**: HA Riemann sum integral helper required (user-configured). The coordinator does NOT integrate power internally.

**Rationale**:
- The coordinator polls every 5 minutes. Sampling W at 5-min intervals and summing `W × Δt` has significant error on variable loads (up to ±30%).
- HA's built-in `integration` platform (Riemann sum) samples continuously at the source entity's update rate (typically seconds), giving far higher accuracy.
- Requiring users to configure the helper is consistent with HA patterns for energy monitoring (same approach as the Energy Dashboard).

**Alternatives considered**:
- Coordinator-internal integration: rejected — 5-min sampling too coarse; increases coordinator complexity for no net accuracy benefit.

---

## 2. Bidirectional Meter — Single Helper or Two Helpers with Template Clipping?

**Decision**: Two separate HA template sensors + two Riemann sum helpers. Each produces a clean always-increasing kWh sensor for import and export respectively.

**Rationale**:
- Template approach: `sensor.grid_import_power = max(W, 0)` → Riemann sum helper → `sensor.grid_import_energy`. Same for export with `max(-W, 0)`.
- Each kWh output is monotonically non-decreasing, so the coordinator's delta logic (`max(delta, 0.0)`) works correctly.
- Eliminates ambiguity in delta calculation that arises with a single signed-value helper.
- The previous bidirectional same-entity coordinator code path (detecting `import_meter == export_meter`) is removed.

**Alternatives considered**:
- Single signed-value integration helper with delta splitting in coordinator: rejected. Produces negative deltas when net flow reverses mid-period, requiring special-casing. The two-helper approach avoids this entirely.

---

## 3. Utility Meter Detection — `last_reset` Attribute Check

**Decision**: Reject entities where `"last_reset" in state.attributes`. Accept entities where `device_class == "energy"` AND `unit_of_measurement == "kWh"` AND `"last_reset" NOT IN state.attributes`.

**Rationale**:
- HA utility meter helpers (created via the `utility_meter` platform) always set a `last_reset` attribute that updates on each periodic reset.
- Native cumulative smart meter sensors and HA Riemann sum integration helpers do NOT set `last_reset`.
- This is a single, lightweight, attribute-only check — no entity registry lookup required.
- The check is added to `_validate_meter_entity()` in `config_flow.py`.

**Alternatives considered**:
- `state_class == "total_increasing"` check: rejected — HA integration helpers may use `state_class=total` when the source signal can be negative (e.g., bidirectional template sensor). Both `total` and `total_increasing` are valid for energy sensors in this context.
- Entity registry `platform` check (reject `utility_meter` platform): rejected — requires entity registry lookup; more fragile as platform name could change.

---

## 4. Same-Entity Import/Export — Hard Error or Silent Deprecation?

**Decision**: Hard validation error at config-flow save time. Error key: `"same_entity_import_export"`. The coordinator's bidirectional same-entity delta-splitting code path is removed entirely.

**Rationale**:
- Users configuring the same entity for both import and export must be using a signed W→kWh integration helper, which requires the two-template-helper pattern instead.
- Silent acceptance would leave the (now-removed) bidirectional code path active, masking potential misconfiguration.
- Showing a clear error directs users to the correct two-helper setup documented in the UI description (FR-010) and README.

**Alternatives considered**:
- Deprecation warning + continued bidirectional support for one release cycle: rejected — increases coordinator code complexity for a transitional period; the correct two-helper pattern is not significantly harder to set up.

---

## 5. Daily Reset Trigger — API-Driven vs. Time-Driven

**Decision**: API-driven. Daily sensors reset when `accounting_date_nzt` changes (i.e., the Interim schedule returns a settled price for a new NZT calendar date).

**Rationale**:
- The Interim schedule is the authoritative source for settled pricing date. Using it as the reset trigger ensures the daily total is consistent with the settled price data, not wall-clock time.
- NZT midnight is not always a clean reset boundary relative to trading period publication; API-driven avoids edge cases near midnight.
- Already implemented: `accounting_date_nzt` is computed from the selected settled price's `trading_datetime` in `_populate_accounting_metrics`.

**Additional decision**: New `PreviousDayImportCostSensor` and `PreviousDayExportRevenueSensor` sensors capture the accumulated total at the moment of each daily reset.

**Rationale for coordinator-owned daily accumulation** (architectural):
- The previous-day snapshot must be captured atomically at the exact moment the daily sensor resets — before any new delta is applied.
- Moving daily accumulation into the coordinator (instead of each sensor) ensures: (a) the snapshot is computed in `_populate_accounting_metrics` before sensors receive the update, (b) both daily and previous-day values appear in the same `node_data` dict, and (c) sensors become simple display-only entities, easier to test.
- On HA restart: daily sensors restore their accumulated total via RestoreEntity, then call `coordinator.seed_daily_total()` to prime the coordinator's in-memory accumulator.

**Alternatives considered**:
- Cross-sensor reference (daily sensor writes to previous-day sensor on rollover): rejected — creates tight coupling between entity instances; harder to test.
- Daily sensor write-back to `coordinator.data` dict: rejected — `coordinator.data` is overwritten each poll cycle; any write-back is lost.
