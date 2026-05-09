# Feature Specification: Electricity Price Schedules Sensor Platform

**Feature Branch**: `002-price-schedules-sensor`
**Created**: 2026-05-05
**Status**: Draft
**Input**: User description: "Implement a Home Assistant sensor platform that retrieves and displays electricity price schedules from the Electricityinfo API using authenticated OAuth credentials. Support multiple sensor configurations with user-customizable parameters."

## Clarifications

### Session 2026-05-05

- Q1: Config flow UX for adding/editing/removing multiple sensors → A: Options Flow (users access via Settings > Devices & Services > Electricity Info NZ > Options; single list of sensors per integration instance)
- Q2: Per-sensor vs global update interval → A: Global interval (all sensors share the 30-minute update cycle; not individually configurable per sensor in v1)
- Q3: Handling partial API responses → A: Accept partial data as valid (sensor displays available data; missing attributes show as empty/null; no error state triggered)
- Q4: State persistence & history storage → A: Latest + full forecast array (sensor state stores current price and all forward prices from last successful update; restored on Home Assistant restart)
- Q5: Test scope & API integration → A: Both mocked (unit/integration tests) and live API tests (optional/manual); mocked responses used in CI; live tests can be run manually with valid credentials for verification

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure Single Price Sensor (Priority: P1)

As a New Zealand Home Assistant user concerned about energy costs, I want to add a single price sensor for my local electricity market node, so that I can see current and forecast electricity prices in my Home Assistant dashboard.

**Why this priority**: This is the core MVP use case. Every user needs to be able to add and view price data. Without this, the feature delivers no value.

**Independent Test**: Can be fully tested by adding one sensor via config flow, seeing it appear in Home Assistant, and verifying data appears and updates every 30 minutes.

**Acceptance Scenarios**:

1. **Given** I have Home Assistant running with Electricity Info NZ integration configured with OAuth credentials, **When** I open the integration options/settings, **Then** I can add a new price sensor and specify: schedule type, market node, and forward price count
2. **Given** I have configured a price sensor, **When** I check Home Assistant after 5 minutes, **Then** the sensor displays a current price in my chosen unit (NZD/MWh or c/kWh)
3. **Given** a price sensor is configured, **When** 30 minutes pass, **Then** the sensor automatically updates with the latest price data without manual intervention
4. **Given** a sensor is displaying a price, **When** I inspect the entity attributes in Home Assistant, **Then** I see timestamp, market type, node, and schedule type populated

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

### User Story 3 - Switch Price Units (Priority: P2)

As a Home Assistant user, I want to view electricity prices in either NZD/MWh or cents/kWh, so that I can see prices in the unit most meaningful for my energy management decisions.

**Why this priority**: P2 - Supports different user workflows (wholesale vs retail tracking). Important for user experience but can be added post-MVP if needed.

**Independent Test**: Can be fully tested by creating sensors with different unit configurations and verifying prices display correctly in each unit.

**Acceptance Scenarios**:

1. **Given** I configure a price sensor, **When** I select "NZD/MWh" as the unit, **Then** the sensor displays prices in that unit
2. **Given** I configure a price sensor, **When** I select "c/kWh" as the unit, **Then** the sensor displays prices converted to cents per kilowatt-hour
3. **Given** a sensor displays prices in one unit, **When** I reconfigure it to use a different unit, **Then** the display updates and reflects prices in the new unit

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

- What happens when OAuth token expires during a price update? (Should trigger token refresh from stored credentials and retry)
- How does the system handle API returning partial data (e.g., missing forecast prices for some nodes)? (Sensor accepts and displays available data; missing attributes render as empty/null; no error state triggered)
- What happens if a user misconfigures a sensor with an invalid node/market type? (Config validation should catch before save)
- How does the system behave if the configured number of forward prices is reduced after initial setup? (Data should simply be truncated in attributes)
- What if multiple sensors are added rapidly in succession? (Should queue and process sequentially without race conditions)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST retrieve price schedules from the Electricityinfo API using OAuth 2.0 Client Credentials flow authenticated credentials
- **FR-002**: System MUST support adding, editing, and removing multiple price sensor configurations via Home Assistant Options Flow (accessed via Settings > Devices & Services > Electricity Info NZ > Options); all sensors stored as a list within the single config entry
- **FR-003**: Each sensor configuration MUST be customizable with: schedule type, market type, electricity market node, number of forward prices, and price unit preference (NZD/MWh or c/kWh)
- **FR-004**: System MUST automatically update all configured sensors every 30 minutes on a shared global schedule (not individually configurable per sensor); users can customize the global interval in future versions
- **FR-005**: System MUST display the current price as the sensor state in the user's selected unit (NZD/MWh or c/kWh)
- **FR-006**: System MUST expose price metadata as sensor attributes: timestamp, confidence level, forecast period, market type, node, schedule type
- **FR-007**: System MUST persist price data across Home Assistant restarts (using Home Assistant's state storage)
- **FR-008**: System MUST gracefully handle OAuth token expiration by requesting a new token from stored credentials before retrying the API call
- **FR-009**: System MUST implement exponential backoff retry logic: after first failure, retry after 1 minute; after second failure, mark sensor unavailable
- **FR-010**: System MUST mark sensors as unavailable (not error state) when updates cannot be retrieved, allowing automations to continue functioning
- **FR-011**: System MUST automatically transition sensors from unavailable back to normal state once data retrieval succeeds
- **FR-012**: System MUST validate all sensor configuration parameters before persisting to Home Assistant config entry
- **FR-013**: System MUST convert between NZD/MWh and c/kWh price units accurately (1 NZD/MWh = 0.1 c/kWh)

### Key Entities

- **PriceSensor**: Represents a configured sensor instance with parameters (schedule_type, market_type, node, forward_prices_count, unit_preference), state (current_price), and metadata (timestamp, confidence, forecast_period)
- **PriceSchedule**: Represents a price schedule response from Electricityinfo API, containing price data, forecast periods, node information, and confidence levels
- **SensorConfiguration**: User-provided configuration stored in Home Assistant config entry (list of sensor definitions with their parameters)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can add a new price sensor and see it update with current data within 5 minutes of configuration
- **SC-002**: Price data refreshes automatically every 30 minutes with zero user intervention required
- **SC-003**: System maintains 99% uptime for price sensors when API is available (excludes API downtime and network failures)
- **SC-004**: Temporary API or network failures do not trigger error states or user-facing alerts; sensors recover automatically within 2 minutes of service restoration
- **SC-005**: Users can successfully configure and display multiple sensors (minimum 5) simultaneously without performance degradation
- **SC-006**: Price unit conversion displays prices within ±0.01 c/kWh or ±0.1 NZD/MWh of accurate conversion
- **SC-007**: 90% of sensor configuration changes take effect within 2 minutes without requiring Home Assistant restart
- **SC-008**: Price data persists through Home Assistant restarts; users see current price and full forecast array (all forward prices) restored from last successful update

## Assumptions

- **OAuth Credentials Availability**: Users have already completed OAuth 2.0 authentication with the Electricityinfo API and their credentials are stored in the Home Assistant config entry by the prior OAuth Config Flow feature
- **30-Minute Update Default**: The 30-minute update interval is a sensible default for most users; users can customize this via configuration if needed in future updates
- **API Stability**: The Electricityinfo API response structure remains stable and continues to return price_value, timestamp, and confidence_level fields
- **Price Unit Conversion**: Simple linear conversion (1 NZD/MWh = 0.1 c/kWh) is sufficient for user needs; no complex regional tariff calculations are required
- **Single Config Entry Scope**: All sensor configurations are stored as a list within the single OAuth config entry (not separate config entries per sensor)
- **Network Connectivity**: Home Assistant has stable internet connectivity for regular API calls; temporary network failures are recoverable and expected
- **Token Refresh**: OAuth token refresh is already implemented by the prior OAuth Config Flow and can be reused by this sensor platform
- **Home Assistant Version**: Running on Home Assistant 2026.3.1 or later with full async/await support for EntityPlatform
- **No Data Transformation**: Prices returned by API require minimal transformation; conversion between units is the only calculation needed

## Testing Strategy

- **Primary Test Harness**: Unit and integration tests use mocked Electricityinfo API responses (pytest fixtures); tests run in CI without external dependencies
- **Live API Tests**: Optional manual tests with valid OAuth credentials to verify real API integration; can be skipped in automated CI
- **Test Coverage Scope**: Covers all user stories (single sensor, multiple sensors, unit conversion, failure recovery), edge cases, and state persistence scenarios
