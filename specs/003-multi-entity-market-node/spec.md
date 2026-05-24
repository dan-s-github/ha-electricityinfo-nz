# Feature Specification: Multiple Entities for Market Node

**Feature Branch**: `multi-entity-for-market-node`
**Created**: 2026-05-19
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Live Price Sensor Setup (Priority: P1)

A home owner wants to monitor the current wholesale electricity price for their local NZ market node in real time. They open the integration settings, pick their market node and preferred price unit, enable the live price option, and a sensor appears in Home Assistant showing the current price.

**Why this priority**: The live price sensor is the foundational value of the integration and delivers immediate, standalone value. All other sensor types build on this baseline.

**Independent Test**: Can be fully tested by configuring a single market node with only "Current electricity price" enabled, submitting, and verifying one price sensor is created showing a current value.

**Acceptance Scenarios**:

1. **Given** a user has the integration installed, **When** they open the market node configuration form, select a node, choose a price unit, enable "Current electricity price", and submit, **Then** a sensor is created for that node displaying the current electricity price in the selected unit.
2. **Given** a configured live price sensor, **When** the coordinator fetches new forecast data (PRSL or PRSS via `forward` parameter), **Then** the sensor value updates to the current trade period's price from the forecast response, and the forecast attribute is updated with the remaining periods.
3. **Given** a user selects c/kWh as the price unit, **When** the sensor displays its value, **Then** the price is shown in cents per kilowatt-hour.
4. **Given** a user selects NZD/kWh as the price unit, **When** the sensor displays its value, **Then** the price is shown in New Zealand dollars per kilowatt-hour.

---

### User Story 2 - Forecast Price Sensors (Priority: P2)

A home owner wants to automate energy-intensive tasks around periods of cheaper forecast electricity prices. They enable forecasting, choose a forecast type (price-responsive or non-responsive), and select one or both forecast horizons (day-ahead and/or intraday). Sensors are created that expose upcoming price forecasts.

**Why this priority**: Forecast sensors enable price-based automation which is a key differentiating use case. Multiple automation workflows depend on this data.

**Independent Test**: Can be fully tested by enabling only the forecasting section, selecting at least one forecast horizon, saving, and verifying the corresponding forecast sensor(s) are created and populated with forecast data.

**Acceptance Scenarios**:

1. **Given** forecasting is enabled with day-ahead (24h) horizon selected, **When** configuration is submitted, **Then** a day-ahead forecast price sensor is created for that market node.
2. **Given** forecasting is enabled with intraday (4h) horizon selected, **When** configuration is submitted, **Then** an intraday forecast price sensor is created for that market node.
3. **Given** both forecast horizons are selected, **When** configuration is submitted, **Then** two separate forecast sensors are created — one for day-ahead and one for intraday.
4. **Given** forecast type "Price-responsive" is selected, **When** the sensor is created, **Then** it uses price-responsive forecast data from the provider.
5. **Given** forecast type "Non-responsive" is selected, **When** the sensor is created, **Then** it uses non-responsive forecast data from the provider.
6. **Given** a forecast sensor is configured with 24h history retention, **When** historical data accumulates beyond 24 hours, **Then** only the most recent 24 hours of data is retained.

---

### User Story 3 - Accounting and Analytics Sensors (Priority: P3)

A prosumer (a household that both imports and exports electricity) wants to track what they actually paid and received based on settled prices. They enable the accounting section and sensors are created for settled price, import costs, export revenue, and daily total cost/revenue sensors that reset at midnight NZT.

**Why this priority**: This is an advanced feature for prosumers with solar or batteries. It has high value for a subset of users and completes the picture of electricity cost monitoring.

**Independent Test**: Can be fully tested by enabling only the accounting/analytics section, saving, and verifying that settled price, import cost, export revenue, and daily total sensors are created (with a linked energy meter for the calculated and daily total tiers).

**Acceptance Scenarios**:

1. **Given** accounting is enabled, **When** configuration is submitted, **Then** a raw Interim-sourced settled price sensor (converging to Final values within ~30 min) is always created; if an import meter is linked, per-period import cost, export revenue, daily import cost, and daily export revenue sensors are also created for that market node (if no export meter is provided, the import meter is reused as signed bidirectional input for export calculations).
2. **Given** accounting is enabled with no energy meter linked, **When** configuration is submitted, **Then** only the raw settled price sensor is created — import cost, export revenue, and daily total sensors are omitted without error.
3. **Given** accounting sensors are configured with a 24h or 48h retention period, **When** price data accumulates beyond that retention window, **Then** only data within the retention window is kept.
4. **Given** a user changes the accounting history retention setting, **When** the updated configuration is saved, **Then** the retention policy updates accordingly.
5. **Given** daily total sensors are active, **When** midnight NZT passes, **Then** `DailyImportCostSensor` and `DailyExportRevenueSensor` reset to zero and begin accumulating for the new day.
6. **Given** HA restarts, **When** the first coordinator poll completes, **Then** daily total sensors restore their last persisted accumulated value via `RestoreEntity` and continue accumulating; per-period accounting sensors (settled price, import cost, export revenue) show as unavailable until the first poll.

---

### User Story 4 - Multiple Market Nodes (Priority: P2)

A user with properties in different electricity distribution areas wants to monitor prices for multiple NZ market nodes simultaneously. They configure the integration for each node and manage independent sets of sensors per node.

**Why this priority**: Multi-node support is essential for users managing multiple properties or users who want to compare prices across regions for arbitrage or relocation decisions.

**Independent Test**: Can be fully tested by completing the configuration flow for a second, different market node and verifying a separate, correctly named set of sensors is created independently.

**Acceptance Scenarios**:

1. **Given** one market node is already configured, **When** the user adds a second, different market node, **Then** a distinct set of sensors is created prefixed with the second node's identifier.
2. **Given** two market nodes are configured, **When** prices update, **Then** each node's sensors update independently with their own respective data.
3. **Given** multiple market nodes are configured, **When** one node's configuration is changed, **Then** the other nodes are unaffected.

---

### User Story 5 - Modifying an Existing Market Node Configuration (Priority: P2)

A user wants to change the options they chose when first setting up a market node — for example, enabling forecasting they originally skipped, or changing history retention. They open the existing configuration and make changes without removing and re-adding the integration.

**Why this priority**: In-place editing is essential for usability. Without it, users must delete and reconfigure entirely, which is error-prone and disruptive.

**Independent Test**: Can be fully tested by saving an initial configuration, reopening it, changing at least one option (e.g., enabling a previously disabled sensor), saving again, and verifying the change is reflected in the sensor list.

**Acceptance Scenarios**:

1. **Given** a market node is configured with only the live price sensor, **When** the user reopens the configuration and enables forecasting, **Then** the forecast sensor(s) are added without removing the existing live price sensor.
2. **Given** a market node is configured with certain settings, **When** the user opens and saves the configuration with no changes, **Then** all existing sensors remain unchanged.
3. **Given** a user disables a previously enabled sensor type, **When** the updated configuration is saved, **Then** the corresponding sensors are removed from Home Assistant.

---

### Edge Cases

- If a user submits a configuration with no sensor types enabled, the flow rejects the save with a validation error and keeps the existing configuration unchanged.
- If a user attempts to configure the same market node a second time, the flow rejects the duplicate and preserves the existing node configuration.
- If forecast data is unavailable for a selected horizon during an update cycle, the corresponding forecast sensor remains unavailable until valid forecast data is received again.
- If a user switches from price-responsive to non-responsive forecast type (or vice versa), existing forecast sensors remain in place and begin reporting values from the newly selected forecast source after save.
- If history retention is reduced and stored history exceeds the new limit, history is trimmed to the new retention window on the next update cycle.
- If accounting is enabled with no linked energy meter, only the raw settled price sensor is created; calculated sensors are omitted and can be enabled later by linking a meter in reconfigure.
- If the same HA entity is linked for both import and export selectors, it is treated as a signed bidirectional meter (positive delta = import cost, negative delta absolute value = export revenue).
- If no export meter is configured but an import meter is configured, the import meter is used as the signed bidirectional source for both import and export calculations.
- On HA restart, the live price sensor restores its last known state (via `RestoreEntity`) so it shows a value immediately; forecast and per-period accounting sensors (settled price, import cost, export revenue) start as unavailable and refresh on the first coordinator poll. Daily total sensors (`DailyImportCostSensor`, `DailyExportRevenueSensor`) restore their last accumulated daily total via `RestoreEntity` and continue accumulating from that value; if HA was down and the energy meter changed during the outage, the restored total may be slightly stale — this is a known accepted limitation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow users to select a market node from the list of available NZ electricity market nodes
- **FR-002**: System MUST allow users to select a price display unit (c/kWh or NZD/kWh) per market node configuration. The selected unit is the **native stored unit** for all sensors in that node — prices are converted from the API's NZD/MWh format at ingest time and stored/reported in the selected unit directly. No runtime conversion at display time. This replaces the 002 convention of storing NZD/MWh internally.
- **FR-003**: System MUST create a live current-price sensor when the user enables the "Current electricity price" option. The live price sensor MUST source its current price from the **current trade period's price within the day-ahead forecast schedule response** (`forward=48`, using PRSL or NRSL based on configured forecast type). This unifies the live price and forecast data into a single coordinator fetch: the current trade period's price becomes the sensor state; remaining periods become the forecast attribute.
- **FR-004**: System MUST allow users to independently enable or disable forecasting, accounting, and live pricing sections
- **FR-005**: System MUST allow users to select forecast type: price-responsive or non-responsive
- **FR-006**: System MUST allow users to select one or both forecast horizons: day-ahead (48 trade periods / 24h) and intraday updates (4h)
- **FR-007**: System MUST allow users to configure history retention (6h, 12h, or 24h) for forecast sensors. The configured retention defines the forecast-history API lookback (`back`) window, and all returned prior trading periods within that window MUST be stored in the sensor `history` attribute.
- **FR-008**: System MUST create a forecast sensor for each selected forecast horizon when forecasting is enabled
- **FR-009**: System MUST apply accounting-specific enable/disable behavior independently of other sections: when accounting is enabled, accounting sensors are created per configuration; when accounting is disabled, accounting sensors are not created (or are removed on save if previously present).
- **FR-010**: System MUST create Interim-sourced settled price, import cost, export revenue, and daily total sensors when accounting is enabled; the settled price data source MUST be the Interim schedule (`back=48`), which fetches the full day's settled periods (up to 48 trade periods / 24h) and converges to identical Final settled values within ~30 minutes of each trading period. Three tiers of sensors are created: (1) a raw settled price sensor (Interim price in the node's selected unit — always created), (2) calculated per-period cost/revenue sensors (price × energy volume — created when the user links an import and/or export Home Assistant energy meter entity; silently omitted only if neither is linked), and (3) daily total sensors — `DailyImportCostSensor` and `DailyExportRevenueSensor` — that accumulate cost/revenue from midnight NZT and reset at midnight NZT (created when at least one meter selector is linked). If no export meter is configured but an import meter is configured, the import meter MUST also be used as the export source in signed bidirectional mode (positive delta = import, negative delta = export). Daily totals use `RestoreEntity` to persist their accumulated value across HA restarts and continue accumulating from the restored value (stale-if-meter-changed during outage is an accepted known limitation). The reset to zero at midnight NZT is triggered coordinator-side: on each poll, the NZT date of the latest Interim trade period in the API response is compared against the stored accumulation date; if the date has advanced, the running total is reset before accumulating the new period. Reset may occur up to ~30 minutes after midnight NZT (one coordinator interval delay — accepted). Per-period accounting sensors (settled price, import cost, export revenue) start unavailable on HA restart and refresh on the first coordinator poll. Arbitrage analytics sensors are out of scope for this version.
- **FR-011**: System MUST enforce a minimum accounting history retention of 24h (48 trade periods); configurable options are 24h or 48h with a default of 24h
- **FR-012**: All sensor identifiers created for a market node MUST be prefixed with that market node's identifier
- **FR-013**: System MUST support configuring multiple different market nodes simultaneously
- **FR-014**: System MUST allow users to modify an existing market node configuration after initial setup
- **FR-015**: System MUST remove sensors that correspond to disabled sections when a configuration is updated
- **FR-016**: System MUST prevent saving a configuration where no sensor types are enabled
- **FR-017**: The day-ahead forecast sensor MUST expose 48 trade periods of forward price data (24 hours) and include all previous trading periods returned by the retention-defined API lookback in `history` (not only the current period).
- **FR-018**: The config flow MUST expose two independently optional energy meter entity selectors per market node: one for grid import kWh and one for grid export kWh. Each linked entity MUST be validated to have `device_class: energy` (unit: kWh); entities that do not meet this contract MUST be rejected with a user-facing validation error. If the user provides the same entity for both import and export selectors, the integration MUST treat it as a signed bidirectional meter: positive delta = import cost; negative delta = export revenue (absolute value used for revenue calculation). If the export selector is left empty but an import meter is linked, the integration MUST treat that import meter as the signed bidirectional meter for both import and export calculations. Import cost sensors are created when an import meter is linked. Export revenue sensors are created when an export meter is linked or when export falls back to the import meter.
- **FR-019**: On upgrade from 002, the integration MUST automatically migrate existing 002 config entries to the 003 structure. Migration MUST map the existing single-node configuration (market node, price unit, enabled sensor types) to a 003 multi-node entry configuration. Historical price values are not migrated; prices are fetched after migration in the configured display unit during normal coordinator updates. During migration, each `market_node` may produce only one 003 entry; if duplicate legacy entries target the same `market_node`, the first encountered entry MUST be kept and later duplicates MUST be skipped with a warning. After migration, runtime entity setup MUST create `market_node` entities only; legacy `sensor` entities MUST NOT be created. Sensor entity IDs MUST be preserved where possible to avoid breaking existing automations and dashboards; where an ID cannot be preserved, the migration MUST log a warning listing the changed entity IDs.

### Key Entities

- **Market Node**: A specific NZ electricity grid location (e.g., BRB0331 Bream Bay, NI) for which price data is available from the provider
- **Market Node Configuration**: The complete set of user choices for a market node — price unit, enabled sensor types, forecast type, forecast horizons, and history retention periods
- **Live Price Sensor**: A sensor entity showing the current wholesale electricity price for a market node. The current price is sourced from the **current trade period's price in the forecast schedule response** (PRSL day-ahead or PRSS intraday, using the `forward` parameter). The same single coordinator fetch serves both the current price (sensor state = current trade period) and the forecast attribute (remaining future periods).
- **Forecast Price Sensor**: A sensor entity exposing upcoming price forecasts for a market node at a given horizon (day-ahead or intraday)
- **Settled Price Sensor**: A sensor entity reflecting the settled electricity price for a market node, sourced from the Interim schedule (`back=N`); Interim prices converge to identical Final settled values within ~30 minutes of each trading period, providing near-real-time settled pricing without the ~1-day publication lag of the Final schedule
- **Accounting Sensor Group**: The set of sensors created together when accounting is enabled for a market node. Comprises three tiers: (1) **Price tier** — a raw Interim-sourced settled price sensor (always created, no energy meter required); (2) **Calculated tier** — per-period import cost and export revenue sensors (created when at least one meter is linked; energy volume delta is computed coordinator-side: previous meter reading stored; delta = current − previous per poll; first poll after startup skips that period's delta); (3) **Daily total tier** — `DailyImportCostSensor` and `DailyExportRevenueSensor` (created when at least one meter is linked). If the same entity is linked for both import and export, or if export is omitted while import is linked, that import meter is treated as the signed bidirectional meter (positive delta = import, negative delta = export). The coordinator fetches `back=48` trade periods of Interim history on each poll. Daily total sensors use `RestoreEntity` to persist accumulated values across restarts. Arbitrage analytics sensors are out of scope for this version.
- **Daily Import Cost Sensor**: A sensor entity that accumulates the total import electricity cost for the current calendar day (midnight-to-midnight NZT), calculated as the sum of (settled price × import energy volume) for each trade period since midnight. Resets to zero at midnight NZT. Uses `RestoreEntity` to persist accumulated daily total across HA restarts; accumulation continues from the restored value. If HA was down and the energy meter changed during the outage, the restored total may be slightly stale (accepted limitation).
- **Daily Export Revenue Sensor**: A sensor entity that accumulates the total export electricity revenue for the current calendar day (midnight-to-midnight NZT), calculated as the sum of (settled price × export energy volume) for each trade period since midnight. Resets to zero at midnight NZT. Uses `RestoreEntity` to persist accumulated daily total across HA restarts; accumulation continues from the restored value. If HA was down and the energy meter changed during the outage, the restored total may be slightly stale (accepted limitation).
- **Trade Period**: The 30-minute interval unit used by the NZ electricity market. All price data — live, forecast, and settled — is structured as a sequence of trade periods. One hour equals 2 trade periods.
- **Forecast Horizon**: The time window of a price forecast. Day-ahead (PRSL) covers 48 trade periods forward (24 hours). Intraday (PRSS) covers 4 hours forward.
- **History Retention**: The lookback window for forecast history data. The configured retention value is used as the API `back` window for forecast history, and all prior trading periods returned in that window are stored in `history`. For example, a 24h retention setting keeps the previous 24h of trading periods in history.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can configure a market node and see at least one working price sensor within 3 minutes of starting the configuration flow
- **SC-002**: All selected entity types are created and visible in Home Assistant immediately after the configuration is saved, with no manual restart required
- **SC-003**: With 5 configured market nodes, saving a new or updated market-node configuration completes in under 10 seconds in at least 95% of attempts, and all selected sensors for that save become available within 3 minutes.
- **SC-004**: Users can update any part of an existing market node configuration without removing and re-adding the integration entry
- **SC-005**: Sensor values reflect the latest available data within the integration's standard data refresh cycle
- **SC-006**: Every sensor name clearly and unambiguously identifies both its market node and its data type (live price, day-ahead forecast, intraday forecast, settled price, import cost, export revenue, daily totals).
- **SC-007**: When a user disables a sensor type, the corresponding sensors are removed from Home Assistant within one configuration save

## Assumptions

- Users have already completed OAuth authentication with the NZ electricity data provider (this feature depends on Phase 1: OAuth config flow)
- The list of available market nodes is retrieved from the electricity data API at configuration time and presented as a searchable or paginated dropdown
- History retention governs data stored within the sensor's state attributes; it does not affect the underlying API or provider data retention
- The selected price unit applies uniformly to all sensor types created for a market node (live, forecast, and accounting sensors share one unit setting)
- The integration's global data refresh cycle (approximately 30 minutes) governs when sensor values update; per-sensor refresh rates are not configurable in this version. A single coordinator is shared by all sensor types (live, forecast, accounting). The coordinator's poll timing cannot be aligned to NZ market trade period boundaries (:00/:30) by the integration itself — users who require boundary-aligned updates should create a HA automation to reload the integration at :01 or :31 after any HA restart.
- Arbitrage analytics sensors are out of scope for this version; the accounting sensor group delivers settled price, per-period import cost/export revenue, and daily import cost/export revenue totals (when an energy meter is linked)
- Accounting sensor history retention is a minimum of 24h (48 trade periods) to ensure a full trading day's settled prices are available for daily total calculation; daily total sensors accumulate from midnight NZT and reset at midnight NZT
- At least one sensor type (live price, forecasting, or accounting) must be enabled; saving a configuration with none enabled is not permitted
- Duplicate market node configurations (same node added twice) are not supported; each market node may be configured once
- This feature (003) replaces the 002 single-node sensor implementation entirely; on upgrade, existing 002 config entries are automatically migrated to the 003 structure with no manual intervention required

## Clarifications

### Session 2026-05-19

- Q: What is the data structure of the day-ahead forecast sensor (forward/backward periods and period granularity)? → A: Day-ahead uses 48 trade periods forward (24h); lookback is defined by the configured retention (`back` window), and all prior periods returned in that window are included in history; trade periods are 30 minutes each.

### Session 2026-05-20

- Q: Which API schedule should accounting sensors use to source settled price data? → A: Interim schedule (`back=N`) — near real-time (~30 min lag), converges to identical Final settled values (confirmed identical prices in live API testing).
- Q: Do import cost / export revenue sensors show raw price only or calculated cost (price × volume)? → A: Both — a raw Interim settled price sensor is always created; separate calculated cost/revenue sensors are also created and require the user to optionally link a Home Assistant energy meter entity per node.
- Q: When accounting is enabled but no energy meter is linked, what should the config flow do? → A: Optional — settled price sensor always created; calculated sensors (import cost, export revenue, arbitrage analytics) silently omitted if no meter linked; user can link a meter later via reconfigure to activate them.
- Q: What entity validation should the config flow apply to a linked energy meter? → A: Require `device_class: energy` (unit: kWh) — standard HA energy meter type, ensuring dimensionally correct price × volume calculation.
- Q: What should the arbitrage analytics sensor(s) represent? → A: Deferred — arbitrage analytics removed from this version; accounting sensors deliver settled price, import cost, and export revenue only.

### Session 2026-05-20 (continued)

- Q: What API schedule and query pattern should the Live Price Sensor use? → A: Forecast schedule (`forward` parameter) — the current trade period's price is extracted from the forecast response; this unifies the live price and forecast data into a single coordinator fetch (current period price = sensor state; remaining periods = forecast attribute).
- Q: What is the native/internal price unit used by 003 sensors, and how does this relate to the 002 spec? → A: Store in the user-selected display unit directly (c/kWh or NZD/kWh). No internal NZD/MWh conversion needed. The 003 implementation replaces 002 entirely, so there is no need to maintain the 002 convention of storing NZD/MWh natively and converting at display time.
- Q: What coordinator update frequency should 003 use, and can the integration enforce poll alignment to trade period boundaries? → A: Single 30-minute coordinator shared by all sensor types (live, forecast, accounting). The integration cannot enforce alignment to trade period boundaries (:00/:30); users who require this must create a HA automation to reload the integration at :01 or :31 after HA restarts.
- Q: How should 003 handle existing 002 config entries on upgrade — clean removal, automatic migration, or coexistence? → A: Automatic migration — 003 reads and converts existing 002 config entries to the 003 structure; prices migrated from NZD/MWh to the node's configured display unit; entity IDs preserved where possible; changed IDs logged as warnings.
- Q: On HA restart, which sensor types should restore their last known state vs start unavailable? → A: Live price sensor only restores last known state (single value still useful as context); forecast and accounting sensors start unavailable and refresh on first coordinator poll (stale array data could mislead automations).
- Q: Should accounting sensors include daily total sensors, and what is the minimum history retention required to support daily spend/earned calculations? → A: Yes — add `DailyImportCostSensor` and `DailyExportRevenueSensor` (third tier of accounting group, created only when an energy meter is linked); these accumulate from midnight NZT and reset at midnight NZT. Minimum accounting retention is 24h; options are 24h/48h (default 24h). Coordinator uses `back=48` for Interim fetch.
- Q: On HA restart, how should daily total sensors recover their state (no HA recorder backfill, start-from-zero, or RestoreEntity)? → A: `RestoreEntity` — daily total sensors restore their last persisted accumulated value and continue accumulating from it. If HA was down and the energy meter changed during the outage the restored total may be slightly stale (accepted known limitation). Per-period accounting sensors (settled price, import cost, export revenue) still start unavailable on restart and refresh on the first coordinator poll.
- Q: How should `DailyImportCostSensor` and `DailyExportRevenueSensor` detect and trigger the midnight NZT reset? → A: Coordinator-side date check — on each coordinator poll, compare the NZT date of the latest Interim trade period in the API response against the stored accumulation date; if the date has advanced, reset the running total to zero before accumulating the new period's cost/revenue. Reset delay up to ~30 min is acceptable given trade period granularity.
- Q: How is the per-period energy volume (kWh delta) computed from the linked cumulative HA energy meter entity? → A: Coordinator-side delta — coordinator stores the previous meter reading; delta = current reading − previous reading on each poll; multiplied by the settled price for that period. On the first poll after HA startup (no previous reading stored), that period's delta is skipped; the daily total continues accumulating correctly from the next poll onwards.
- Q: Should the config flow expose one energy meter entity selector or two (import vs export) for accounting sensor creation? → A: Two separate optional entity selectors — one for import kWh, one for export kWh; each independently optional (only sensors for linked meters are created). If the user provides the same entity for both, the integration treats it as a signed bidirectional meter: positive delta = import cost, negative delta = export revenue (absolute value used for revenue calculation).

### Session 2026-05-24

- Q: How should migration handle duplicate legacy entries that resolve to the same `market_node`? → A: Enforce one migrated entry per `market_node`: keep the first encountered legacy entry and skip later duplicates with a warning.
- Q: When accounting is configured without an export meter but with an import meter, how should export calculations behave? → A: Treat the import meter as the signed bidirectional meter for both import and export calculations.
- Q: How should legacy runtime entities be handled after migration? → A: Legacy entries are converted to `market_node` entries, and runtime setup creates only `market_node` entities (no legacy `sensor` entities).
- Q: How should forecast history retention populate sensor history? → A: The retention setting defines the forecast API `back` window, and all returned previous trading periods are added to `history` (not just the current value).
