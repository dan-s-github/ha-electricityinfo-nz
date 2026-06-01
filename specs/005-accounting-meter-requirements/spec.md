# Feature Specification: Accounting Sensor Meter Entity Requirements

**Feature Branch**: `005-accounting-sensors`
**Created**: 2026-06-01
**Status**: Draft
**Input**: User description: "we need to improve accounting sensors and clarify 'Import energy meter' and 'Export energy meter' entity requirements. Is this an energy meter or a utility meter with fixed period all depends how accounting sensors process the information from the Interim schedule use current branch"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure Import Meter for Cost Accounting (Priority: P1)

A homeowner with solar panels and a smart meter wants to track their electricity import costs at the real-time Interim settled price. If they have only a power sensor (W), they must first create a Home Assistant **Riemann sum integral helper** (the built-in `integration` platform) that converts the W sensor to a cumulative kWh energy sensor. They then configure the accounting integration by pointing it at that resulting kWh sensor. The integration accepts any sensor with `device_class=energy` and `unit_of_measurement=kWh` — whether sourced from a smart meter, an energy monitor, or an HA integration helper. Utility meter helpers that reset at fixed intervals (hourly, daily, etc.) are **not** supported, because their periodic resets cause data loss in the delta-based accounting approach.

**Why this priority**: Import cost accounting is the primary use-case for residential customers. Getting the entity type wrong silently produces incorrect costs.

**Independent Test**: Can be fully tested by configuring a cumulative `sensor.grid_import_energy` entity (total_increasing, kWh) — or an HA integration helper output from a W sensor — and verifying that `ImportCostSensor` produces non-zero values after each coordinator poll, reflecting `Δenergy × Interim_price`.

**Acceptance Scenarios**:

1. **Given** a cumulative energy sensor (device_class=energy, state_class=total_increasing, unit=kWh) is selected, **When** accounting subentry is saved, **Then** the config is accepted without error.
2. **Given** an HA Riemann sum integration helper output sensor (device_class=energy, unit=kWh) is selected, **When** accounting subentry is saved, **Then** the config is accepted without error.
3. **Given** a utility meter sensor that resets daily is selected, **When** accounting subentry is saved, **Then** a validation error is shown explaining that utility meter resets cause data loss.
4. **Given** the import meter entity is unavailable, **When** the coordinator refreshes, **Then** the `ImportCostSensor` state becomes unavailable (not zero).
5. **Given** a valid import meter, **When** the coordinator polls twice and the meter reading has increased by 0.5 kWh at an Interim price of 0.30 c/kWh, **Then** `ImportCostSensor` reports 0.15 c.

---

### User Story 2 - Configure Bidirectional (Export/Import) Meter (Priority: P2)

A prosumer with a solar system may have:
- **Two separate kWh sensors** (one for import, one for export): configure each directly as the respective meter entity.
- **A single signed W sensor** (positive = import, negative = export): they MUST create two HA template sensors — one clipping at `max(W, 0)` for import power, one at `max(-W, 0)` for export power — then feed each into its own Riemann sum integral helper to produce two independent kWh sensors. These two kWh outputs are then configured as the import and export meter entities respectively.

This produces clean, always-increasing kWh sensors for each direction, avoiding any ambiguity in delta calculations.

**Why this priority**: Many modern smart meters and inverters expose a single bidirectional power or energy value. Without clear guidance and a correct two-helper pattern, users end up with incorrect cost/revenue calculations.

**Independent Test**: Can be fully tested by configuring two separate kWh sensors (or integration helper outputs) for import and export, triggering coordinator updates with independent energy increments, and verifying each sensor reports correctly without cross-contamination.

**Acceptance Scenarios**:

1. **Given** separate import and export kWh entities are configured, **When** the coordinator polls and import entity reads +0.3 kWh delta, **Then** `ImportCostSensor` receives 0.3 kWh and `ExportRevenueSensor` receives its own independent delta.
2. **Given** two integration helper outputs derived from clipped template sensors of a single signed W sensor, **When** the coordinator polls during an export event, **Then** the export kWh helper increases and the import kWh helper stays flat.
3. **Given** only an export meter is configured (no import meter), **When** accounting is enabled, **Then** only `ExportRevenueSensor` and `DailyExportRevenueSensor` are created.

---

### User Story 4 - View Previous Day's Totals (Priority: P2)

A user wants to see what their electricity import cost and export revenue were **yesterday** — after the daily sensors have reset at midnight NZT. Two dedicated previous-day sensors retain the accumulated total from the prior NZT day and hold that value unchanged until the next daily reset. This lets users review yesterday's figures without needing to inspect history in the HA energy dashboard.

**Why this priority**: The daily reset clears the running total, permanently losing the prior day's value unless explicitly captured. Previous-day sensors provide a simple single-value reference for billing verification.

**Independent Test**: Can be fully tested by simulating a daily reset event (accounting_date_nzt changes) and asserting that `PreviousDayImportCostSensor` holds the last day's accumulated total while `DailyImportCostSensor` resets to zero.

**Acceptance Scenarios**:

1. **Given** `DailyImportCostSensor` has accumulated 42.5 c during the NZT day, **When** `accounting_date_nzt` changes (day rolls over), **Then** `PreviousDayImportCostSensor` is set to 42.5 c and `DailyImportCostSensor` resets to 0.0.
2. **Given** `PreviousDayImportCostSensor` holds a value, **When** HA restarts, **Then** the previous-day value is restored via RestoreEntity with no data loss.
3. **Given** no daily reset has occurred yet (first day of operation), **When** `PreviousDayImportCostSensor` is read, **Then** its state is unavailable (no prior day to report).

---

### User Story 3 - Interim Price Selection and Period Alignment (Priority: P3)

A user wants to understand how the settled Interim price is selected at each coordinator poll (every 5 minutes), given that Interim trading periods are 30 minutes long. The accounting sensor should always use the most recently **fully settled** Interim trading period price (i.e., the period whose start time is ≤ now). It must not use a future period price even if one is returned by the API.

**Why this priority**: Correct price selection is fundamental to accounting accuracy; using the wrong period's price could silently overstate or understate costs.

**Independent Test**: Can be tested by populating the coordinator data with Interim periods where the "current" period starts 10 minutes ago and a "future" period starts 20 minutes from now, and asserting that `SettledPriceSensor` shows the current period's price.

**Acceptance Scenarios**:

1. **Given** Interim data has periods at T-30min, T-0min, and T+30min and now is T+10min, **When** coordinator updates, **Then** `SettledPriceSensor` reports the price at T-0min.
2. **Given** only future periods are available (API returns future-only data), **When** coordinator updates, **Then** `SettledPriceSensor` becomes unavailable rather than reporting a future price.
3. **Given** no Interim data is available (API error), **When** coordinator updates, **Then** all accounting sensors become unavailable.

---

### Edge Cases

- **Same entity ID for import and export**: Config flow rejects with "Import and export meter must be different entities". Any existing installation with this configuration must update their settings before the next save. The coordinator no longer contains bidirectional delta-splitting logic.
- **Bidirectional signed W sensor**: Users with a single signed W sensor MUST NOT point both import and export meters at the same entity.
- **Meter rollover**: If a meter rolls over (e.g., integer overflow), the delta is negative and clamped to 0.0; energy for that interval is treated as zero rather than producing a huge spike.
- **Meter entity disappears from hass**: If the entity is removed from HA, `_read_energy_meter` returns None and all downstream accounting values become unavailable for that poll.
- **Coordinator restart / HA restart**: The previous meter reading is reset to None on coordinator startup. The first poll after restart produces a None delta (no cost/revenue recorded), preventing a spurious spike from the unknown prior reading.
- **Negative export delta when using separate export meter**: If the export meter unexpectedly decreases (misconfiguration or rollover), the delta is clamped to 0.0 — no negative revenue is recorded.
- **First coordinator poll after entity is configured**: Previous reading is None, so delta is None, and no cost is recorded for the first interval. This is correct and expected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The import meter entity MUST be a sensor with `device_class=energy` and `unit_of_measurement=kWh`, and MUST NOT have a `last_reset` attribute in its state (the presence of `last_reset` indicates a utility meter helper that resets periodically). This accepts native cumulative smart meter sensors, HA Riemann sum integration helper outputs, and rejects utility meter helpers. A descriptive validation error MUST be shown if the entity fails this check.
- **FR-002**: The export meter entity, if configured, MUST satisfy the same constraints as the import meter entity (FR-001).
- **FR-003**: Import and export meters MUST be configured as two separate kWh entities. Using the same entity ID for both is no longer a supported bidirectional shortcut; each direction requires its own independent cumulative kWh sensor or HA integration helper output.
- **FR-012**: The config flow MUST reject a subentry save where the import and export meter entity IDs are identical, displaying the error "Import and export meter must be different entities". The previous same-entity bidirectional delta-splitting code path in the coordinator MUST be removed.
- **FR-004**: At each coordinator update, the energy delta for import MUST be computed as `max(current_reading − previous_reading, 0.0)` kWh. Export energy delta MUST be computed as `max(previous_reading − current_reading, 0.0)` kWh for bidirectional, or `max(export_reading_delta, 0.0)` for separate export meter.
- **FR-005**: If the previous meter reading is unavailable (e.g., first poll, or entity was unavailable last cycle), the delta MUST be treated as None and no cost or revenue MUST be recorded for that interval.
- **FR-006**: The Interim settled price used for accounting MUST be the price of the most recent Interim trading period whose `trading_datetime ≤ now`. Future period prices MUST NOT be used.
- **FR-007**: Per-period sensors (`ImportCostSensor`, `ExportRevenueSensor`) MUST report the cost/revenue for the most recent coordinator interval only. They are not cumulative.
- **FR-008**: Daily sensors (`DailyImportCostSensor`, `DailyExportRevenueSensor`) MUST accumulate per-interval values within the current NZT calendar day. When `accounting_date_nzt` changes (i.e., the Interim API returns a price for a new NZT date), the daily sensor MUST capture its current total into the corresponding previous-day sensor before resetting to zero.
- **FR-009**: Daily sensors MUST restore their accumulated total across HA restarts (using RestoreEntity) and MUST NOT reset on restart unless the accumulation date is stale (i.e., earlier than today NZT).
- **FR-013**: Previous-day sensors (`PreviousDayImportCostSensor`, `PreviousDayExportRevenueSensor`) MUST be created alongside their daily counterparts whenever import or export meter entities are configured. They MUST hold the accumulated total from the most recently completed NZT day and remain unchanged until the next daily reset.
- **FR-014**: Previous-day sensors MUST restore their value across HA restarts (using RestoreEntity). Before the first daily reset has occurred, their state MUST be unavailable.
- **FR-010**: The config flow MUST display a UI label and description for Import/Export meter fields that clearly communicates that the expected entity is either a native cumulative energy sensor (kWh) or the output of an HA Riemann sum integral helper (for users with only a W power sensor). Utility meter helpers are explicitly not supported.
- **FR-011**: The config flow MUST validate selected meter entities at save time using this exact criteria: `device_class == "energy"` AND `unit_of_measurement == "kWh"` AND `"last_reset" NOT IN state.attributes`. Any entity failing this check MUST be rejected with a descriptive error message.

### Key Entities

- **Import Energy Meter**: A Home Assistant sensor entity representing cumulative grid import energy (kWh). This may be a native cumulative sensor from a smart meter or energy monitor (`state_class=total_increasing`), or the output of an HA Riemann sum integral helper configured against a W power sensor. Read-only input to the integration.
- **Export Energy Meter**: A Home Assistant sensor entity representing cumulative grid export energy (kWh). Same acceptable types as Import Energy Meter. May be the same entity as the import meter (bidirectional) or a separate one.
- **ImportCostSensor**: Integration-created sensor reporting the electricity import cost for the most recent coordinator poll interval (c or NZD). Derived from import energy delta × settled Interim price.
- **ExportRevenueSensor**: Integration-created sensor reporting electricity export revenue for the most recent coordinator poll interval. Derived from export energy delta × settled Interim price.
- **DailyImportCostSensor**: Integration-created sensor accumulating `ImportCostSensor` deltas within the current NZT day. Resets when `accounting_date_nzt` changes; captures total into `PreviousDayImportCostSensor` before resetting.
- **DailyExportRevenueSensor**: Integration-created sensor accumulating `ExportRevenueSensor` deltas within the current NZT day. Resets when `accounting_date_nzt` changes; captures total into `PreviousDayExportRevenueSensor` before resetting.
- **PreviousDayImportCostSensor**: Integration-created sensor holding the total import cost from the most recently completed NZT day. Unavailable until the first daily reset occurs. Persists across HA restarts.
- **PreviousDayExportRevenueSensor**: Integration-created sensor holding the total export revenue from the most recently completed NZT day. Unavailable until the first daily reset occurs. Persists across HA restarts.
- **SettledPriceSensor**: Integration-created sensor reporting the most recent Interim settled price for the configured market node.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can configure accounting sensors and, within one coordinator cycle, see non-zero import cost values that match `Δenergy × Interim_price` to within 0.01% rounding tolerance.
- **SC-002**: Selecting a utility meter entity (one with a `last_reset` attribute) in the config flow results in a visible validation error. Selecting the same entity for both import and export meters also results in a distinct validation error. The user is never silently misconfigured in either case.
- **SC-003**: After an HA restart, daily accumulated cost sensors restore their value from the previous state, with zero data loss for the current NZT day. Previous-day sensors also restore their last captured daily total.
- **SC-007**: When a daily reset occurs, `PreviousDayImportCostSensor` and `PreviousDayExportRevenueSensor` are updated atomically in the same coordinator update cycle as the daily sensor reset — no poll cycle passes with an inconsistent state between daily and previous-day sensors.
- **SC-004**: Bidirectional meter configuration correctly separates import and export energy for every coordinator poll — no interval ever records both non-zero import and non-zero export simultaneously.
- **SC-005**: When the Interim API returns no data or only future periods, all accounting sensors transition to unavailable rather than showing stale or incorrect values.
- **SC-006**: The config flow labels and descriptions for meter entity selectors are clear enough that a non-technical user can identify the correct entity type without consulting documentation.

## Assumptions

- The coordinator polling interval (5 minutes) is short enough relative to 30-minute Interim trading periods that the per-interval energy × price approach is acceptable; users do not need sub-period (e.g., 30-second) accuracy.
- When users have only a power sensor (W), they MUST pre-configure an HA Riemann sum integral helper to convert W→kWh before using it as a meter input. The coordinator does **not** perform power integration itself, as 5-minute sampling is too coarse for accurate energy calculation.
- HA's Riemann sum integral helper output sensors have `device_class=energy`, `unit_of_measurement=kWh`, and may have `state_class=total` or `state_class=total_increasing` depending on whether the power source can be negative. Both are accepted by the integration.
- Home Assistant utility meter helpers (created via the `utility_meter` platform) set a `last_reset` state attribute that updates on each period reset. HA Riemann sum integration helpers and native smart meter sensors do not set `last_reset`. The validation check `"last_reset" NOT IN state.attributes` is therefore a reliable and lightweight way to reject utility meters without requiring entity registry lookups.
- The Interim schedule is the correct authoritative source for settled pricing; Final schedule prices are a future consideration and out of scope for this feature.
- A cumulative energy sensor provided by a smart meter, energy monitor (e.g., Shelly EM, Emporia), or inverter integration will always be monotonically increasing except for rare rollover events.
- NZT (Pacific/Auckland timezone) is the correct day boundary for daily accumulation, consistent with the NZ electricity market trading day.
- The export meter entity ID being optional (can be left blank) means export tracking is entirely opt-in. If not configured, no export revenue sensors are created.

## Clarifications

### Session 2026-06-01

- Q: For W→kWh conversion — should the integration compute the integral internally (accept W sensor directly), or require users to configure an HA Riemann sum integral helper first? → A: Option B — HA helper required. Built-in coordinator integration (5-min polls) is not accurate enough; users must create an HA Riemann sum integral helper to convert W→kWh before configuring the meter entity.
- Q: For bidirectional setups (single signed W sensor, positive=import, negative=export) — should the spec support a single HA integration helper with delta-splitting logic, or require two separate helpers with template clipping? → A: Option A — Two separate HA helpers with template clipping. Users create `max(W, 0)` and `max(-W, 0)` template sensors, each fed into its own Riemann sum integration helper, producing two clean always-increasing kWh sensors configured as separate import and export meter entities.
- Q: How should utility meter helpers be distinguished from valid kWh entities in config flow validation? → A: Option A — Check for absence of `last_reset` attribute. Validation criteria: `device_class == "energy"` AND `unit_of_measurement == "kWh"` AND `"last_reset" NOT IN state.attributes`.
- Q: What should happen when a user configures the same entity ID for both import and export meters? → A: Option A — Hard validation error at config-flow save time: "Import and export meter must be different entities". The coordinator's same-entity bidirectional code path is removed entirely.
- Q: Should the daily sensor reset be API-driven (when `accounting_date_nzt` changes) or time-driven (NZT wall-clock midnight)? → A: Option A — API-driven. Reset triggered when the Interim API returns a price for a new NZT date. Additionally, a new `PreviousDayImportCostSensor` and `PreviousDayExportRevenueSensor` are added to capture the prior day's total at the moment of each daily reset.
