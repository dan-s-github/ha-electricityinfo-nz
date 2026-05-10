# Feature Specification: Electricity Price Schedules Sensor Platform

**Feature Branch**: `002-price-schedules-sensor`
**Created**: 2026-05-05
**Status**: Reconciled to Current Implementation
**Input**: User description: "Implement a Home Assistant sensor platform that retrieves and displays electricity price schedules from the Electricityinfo API using authenticated OAuth credentials. Support multiple sensor configurations with user-customizable parameters."

## Clarifications

### Session 2026-05-05

- Q1: Config flow UX for adding/editing/removing multiple sensors → A: Config Subentry Flow via integration options (users add/reconfigure sensor subentries under one integration entry)
- Q2: Per-sensor vs global update interval → A: Global interval (all sensors share the 30-minute update cycle; not individually configurable per sensor in v1)
- Q3: Handling partial API responses → A: Missing or incomplete schedule payload for a configured sensor marks that sensor unavailable until valid data returns
- Q4: State persistence & history storage → A: Latest + full forecast array (sensor state stores current price and all forward prices from last successful update; restored on Home Assistant restart)
- Q5: Test scope & API integration → A: Both mocked (unit/integration tests) and live API tests (optional/manual); mocked responses used in CI; live tests can be run manually with valid credentials for verification

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure Single Price Sensor (Priority: P1)

As a New Zealand Home Assistant user concerned about energy costs, I want to add a single price sensor for my local electricity market node, so that I can see current and forecast electricity prices in my Home Assistant dashboard.

**Why this priority**: This is the core MVP use case. Every user needs to be able to add and view price data. Without this, the feature delivers no value.

**Independent Test**: Can be fully tested by adding one sensor via config flow, seeing it appear in Home Assistant, and verifying data appears and updates every 30 minutes.

**Acceptance Scenarios**:

1. **Given** I have Home Assistant running with Electricity Info NZ integration configured with OAuth credentials, **When** I open integration options and create a sensor subentry, **Then** I can specify: optional display name, schedule type, market type, market node, and forward hours
2. **Given** I have configured a sensor subentry, **When** I check Home Assistant after setup, **Then** two entities are created for that subentry: one in NZD/MWh and one in c/kWh
3. **Given** a price sensor is configured, **When** 30 minutes pass, **Then** the sensor automatically updates with the latest price data without manual intervention
4. **Given** a sensor is displaying a price, **When** I inspect the entity attributes in Home Assistant, **Then** I see timestamp, trading period, node, schedule, run type, and a `forecast` attribute containing a time-ordered list of `{period_start, price}` entries for **future** trading periods only (the current period is excluded — it is already the sensor state value) — compatible with the `forecast_solar` attribute format

---

### User Story 2 - Configure Multiple Price Sensors (Priority: P2)

As a Home Assistant user managing multiple properties or monitoring different market nodes, I want to configure multiple price sensors with different parameters, so that I can track prices across different locations and market types simultaneously.

**Why this priority**: P2 - Not all users need multiple sensors, but those who do represent significant value (power traders, multi-property owners). Should be included in MVP but not block P1 completion.

**Independent Test**: Can be fully tested by adding two sensors with different node/schedule type configurations, verifying both update independently and display correct data.

**Acceptance Scenarios**:

1. **Given** I have one price sensor already configured, **When** I add a second sensor with a different node/market type, **Then** both sensors coexist and update independently
2. **Given** I have two price sensors configured, **When** the update interval triggers, **Then** both sensors update with their respective data without interference
3. **Given** multiple sensors are configured, **When** one sensor fails to retrieve data, **Then** other sensors continue updating normally

---

### User Story 3 - View Dual Unit Sensors (Priority: P2)

As a Home Assistant user, I want both NZD/MWh and cents/kWh entities for each configured sensor, so that I can use either unit in dashboards and automations without reconfiguration.

**Why this priority**: P2 - Supports different user workflows (wholesale vs retail tracking). Important for user experience but can be added post-MVP if needed.

**Independent Test**: Can be fully tested by creating one sensor subentry and verifying both unit entities are created and updated from the same underlying data.

**Acceptance Scenarios**:

1. **Given** I configure a price sensor subentry, **When** entities are created, **Then** one entity displays prices in NZD/MWh
2. **Given** I configure a price sensor subentry, **When** entities are created, **Then** one entity displays converted prices in c/kWh
3. **Given** both unit entities exist for one subentry, **When** coordinator data updates, **Then** both entities update consistently for the same market data point

---

### User Story 4 - Handle Update Failures Gracefully (Priority: P1)

As a Home Assistant user, I want the integration to handle API failures and network errors gracefully, so that temporary service disruptions don't cause alerts or break my automations.

**Why this priority**: P1 - Essential for reliability. User experience degrades significantly if sensors become unavailable or trigger error states unexpectedly.

**Independent Test**: Can be tested by simulating network failures or API errors and verifying the sensor marks itself unavailable rather than throwing errors.

**Acceptance Scenarios**:

1. **Given** a price sensor is active and configured, **When** the API becomes temporarily unavailable, **Then** the sensor is marked as unavailable in Home Assistant (not errored)
2. **Given** a sensor fails to update twice consecutively, **When** the next update attempt is scheduled, **Then** the system retries with exponential backoff before marking unavailable
3. **Given** a sensor is marked unavailable, **When** the API returns to normal and retrieves data successfully, **Then** the sensor automatically returns to normal state and displays updated prices

---

### Edge Cases

- What if a user deletes a sensor subentry while entities are active? (Integration reloads automatically; HA removes the associated entities as part of the standard ConfigSubentryFlow lifecycle — no stale entities remain)
- What happens when OAuth token expires during a price update? (Should trigger token refresh from stored credentials and retry)
- How does the system handle API returning partial data (e.g., missing forecast prices for some nodes)? (The affected sensor becomes unavailable until a valid schedule payload is returned; other sensors continue updating)
- What happens if a user misconfigures a sensor with an invalid node/market type? (Selector/schema validation should reject before save)
- How does the system behave if the configured number of forward prices is reduced after initial setup? (Data should simply be truncated in attributes)
- What if multiple sensors are added rapidly in succession? (Should queue and process sequentially without race conditions)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST retrieve price schedules from the Electricityinfo API using OAuth 2.0 Client Credentials flow authenticated credentials
- **FR-002**: System MUST support adding and reconfiguring multiple price sensor configurations via Home Assistant config subentry flow (sensor subentries under a single integration entry); deleting a sensor subentry triggers an integration reload, after which the associated entities are automatically removed by Home Assistant (no custom cleanup logic required)
- **FR-003**: Each sensor configuration MUST be customizable with: optional display name, schedule type, market type, electricity market node, and number of forward hours
- **FR-004**: System MUST automatically update all configured sensors every 30 minutes on a shared global schedule (not individually configurable per sensor); users can customize the global interval in future versions
- **FR-005**: System MUST create two entities per configured sensor subentry, one with NZD/MWh state and one with c/kWh state; both entities MUST set `state_class = None` (no state class for instantaneous price values) to enable Home Assistant long-term statistics with mean-based aggregation (historical price tracking)
- **FR-006**: System MUST expose price metadata as sensor attributes: timestamp, trading_period, node, schedule, run_type, and forecast. The `forecast` attribute is a time-series list compatible with the `forecast_solar` integration format. Each element contains `period_start` (ISO 8601 datetime string with NZ timezone offset, e.g. `"2026-05-09T12:00:00+12:00"`) and `price` (float in the entity's display unit: NZD/MWh for the NZD/MWh entity, c/kWh for the c/kWh entity). The `forecast` list contains only **future** trading periods — the period whose price is the current sensor state is excluded from the list. One entry is produced per 30-minute NZ electricity trading period in the configured forward horizon, starting from the period immediately after the current one.
- **FR-007**: System MUST persist price data across Home Assistant restarts (using Home Assistant's state storage). Restored state is only used if its `timestamp` attribute is no older than 30 minutes (one update interval); stale restored state is discarded and the entity remains unavailable until the first coordinator fetch succeeds.
- **FR-008**: System MUST gracefully handle authentication failures through the library/client auth path; auth failures MUST not crash setup and MUST surface unavailable/auth-failed behavior through Home Assistant coordinator handling
- **FR-009**: System MUST implement exponential backoff retry logic for coordinator-level update failures: after first failure, retry after 1 minute; after second failure, mark sensors unavailable through failed coordinator state. Note: the HA DataUpdateCoordinator continues retrying indefinitely (no ceiling); sensors are marked unavailable (via `last_update_success=False`) after `MAX_RETRIES=2` failures, but the coordinator does not stop scheduling update attempts.
- **FR-010**: System MUST mark sensors as unavailable (not error state) when updates cannot be retrieved, allowing automations to continue functioning
- **FR-011**: System MUST automatically transition sensors from unavailable back to normal state once data retrieval succeeds
- **FR-012**: System MUST validate all sensor configuration parameters before persisting subentry data (valid schedule/market/node selections; forward hours constrained to 1-84)
- **FR-013**: System MUST convert between NZD/MWh and c/kWh price units accurately (1 NZD/MWh = 0.1 c/kWh)

### Key Entities

- **PriceSensorSubentry**: Represents one configured sensor subentry with parameters (optional name, schedule_type, market_type, node, forward_prices_count). Supported schedule types MUST support Electricityinfo API `forward` parameter for forecast retrieval (e.g., "daily_spot", "forward_market"). Schedules requiring date range parameters (e.g., "Final", "Interim") are not supported in this version.
- **PriceSensorEntity**: Represents one unit-specific sensor entity derived from a subentry (two entities per subentry: NZD/MWh and c/kWh), with state (current_price), `device_class = SensorDeviceClass.MONETARY`, `state_class = None` (enables HA long-term statistics with mean aggregation), and metadata (timestamp, trading_period, node, schedule, run_type, forecast). The `forecast` attribute is a `forecast_solar`-compatible time series of **future** periods only: `[{"period_start": "<ISO8601+tz>", "price": <float>}, …]`, with prices in the entity's display unit. The current period's price is the sensor state and is **not** included in `forecast`.
- **PriceSchedule**: Represents a price schedule response from Electricityinfo API, containing price data, forecast periods, node information, and confidence levels
- **SensorConfiguration**: User-provided configuration stored in Home Assistant sensor subentry data

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can add a new price sensor and see it update with current data within 5 minutes of configuration
- **SC-002**: Price data refreshes automatically every 30 minutes with zero user intervention required
- **SC-003**: System maintains 99% uptime for price sensors when API is available (excludes API downtime and network failures)
- **SC-004**: Temporary API or network failures do not trigger error states or user-facing alerts; sensors recover automatically within 2 minutes of service restoration
- **SC-005**: Users can successfully configure and display multiple sensors (minimum 5) simultaneously without performance degradation
- **SC-006**: Price unit conversion displays prices within ±0.01 c/kWh or ±0.1 NZD/MWh of accurate conversion
- **SC-007**: 90% of sensor subentry configuration changes take effect within 2 minutes without requiring Home Assistant restart
- **SC-008**: Price data persists through Home Assistant restarts; users see current price and full forecast restored from last successful update, provided the restored `timestamp` is no older than 30 minutes. If the restored state is stale (> 30 minutes old), the entity remains unavailable until the first coordinator fetch.

## Assumptions

- **OAuth Credentials Availability**: Users have already completed OAuth 2.0 authentication with the Electricityinfo API and their credentials are stored in the Home Assistant config entry by the prior OAuth Config Flow feature
- **30-Minute Update Default**: The 30-minute update interval is a sensible default for most users; users can customize this via configuration if needed in future updates
- **API Stability**: The Electricityinfo API response structure remains stable and continues to return price_value, timestamp, and confidence_level fields
- **Price Unit Conversion**: Simple linear conversion (1 NZD/MWh = 0.1 c/kWh) is sufficient for user needs; no complex regional tariff calculations are required
- **Single Config Entry Scope**: All sensor configurations are represented as sensor subentries within one integration config entry (not separate integration entries per sensor)
- **Network Connectivity**: Home Assistant has stable internet connectivity for regular API calls; temporary network failures are recoverable and expected
- **Token Refresh**: OAuth token refresh is already implemented by the prior OAuth Config Flow and can be reused by this sensor platform
- **Home Assistant Version**: Running on Home Assistant 2026.3.1 or later with full async/await support for EntityPlatform
- **No Data Transformation**: Prices returned by API require minimal transformation; conversion between units is the only calculation needed

## Testing Strategy

- **Primary Test Harness**: Unit and integration tests use mocked Electricityinfo API responses (pytest fixtures); tests run in CI without external dependencies
- **Live API Tests**: Optional manual tests with valid OAuth credentials to verify real API integration; can be skipped in automated CI
- **Implemented Coverage Scope**: Covers OAuth config flow validation and retry paths, subentry create/reconfigure, sensor platform setup, multi-sensor uniqueness/isolation basics, and unit conversion behavior

### Revision: Implementation Sync 2026-05-07
- Reason: Reconciled config model (subentries), dual-unit entity behavior, attribute set, validation limits, and known runtime behavior to match the shipped implementation.

### Revision: Forecast Attribute Format 2026-05-09
- Reason: Changed forecast representation from `prices_array` (list of dicts with `trading_date`, `trading_period`, `price`) to `forecast` attribute using `forecast_solar`-compatible format. Each element is `{"period_start": "<ISO 8601 datetime with NZ timezone>", "price": <float in entity unit>}`. One entry per 30-minute NZ trading period. Current price remains the sensor state value. This aligns the integration with the Home Assistant `forecast_solar` ecosystem pattern for time-series price/energy attributes.

### Revision: Forecast Excludes Current Period 2026-05-09
- Reason: The `forecast` attribute must contain only future trading periods. The current trading period's price is already the sensor state value and must not be duplicated in the `forecast` list. This matches the `forecast_solar` integration's convention (state = now, forecast = future only).

## Clarifications

### Session 2026-05-09

- Q: Should price sensors declare `state_class` for HA long-term statistics? → A: `state_class = None` — enables historical price tracking with mean-based aggregation (appropriate for instantaneous values like prices, not cumulative totals)
- Q: When a sensor subentry is deleted, what happens to its entities? → A: Entities are removed automatically when the integration reloads after subentry deletion (standard HA ConfigSubentryFlow behaviour; no custom cleanup logic required)
- Q: Should restored state have a staleness threshold? → A: Yes — discard restored state older than one update interval (30 minutes); entity shows unavailable until first coordinator fetch if restored `timestamp` is older than 30 minutes
