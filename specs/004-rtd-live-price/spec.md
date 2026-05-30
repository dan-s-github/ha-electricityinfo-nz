# Feature Specification: RTD-Based Live Price Sensor

**Feature Branch**: `004-rtd-live-price`
**Created**: 2026-05-31
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Accurate Real-Time Spot Price (Priority: P1)

As a home energy manager, I want to see the actual dispatched spot price for the current trading period — not a forecast — so that I can make informed decisions about when to consume or store energy based on prices that have already been settled by the market.

**Why this priority**: The live price is the primary reason users install this integration. Showing the actual dispatched price (RTD) rather than a forecast makes the sensor trustworthy for automation and decision-making. This is the core value change.

**Independent Test**: Can be fully tested by enabling the live price sensor for a market node and verifying the displayed price matches the current RTD schedule price from the electricity market, updated at 5-minute intervals.

**Acceptance Scenarios**:

1. **Given** a market node has the live price sensor enabled, **When** the coordinator completes an update cycle, **Then** the live price sensor displays the RTD price for the current or most recently dispatched trading period.
2. **Given** the RTD price is unavailable for the current trading period (e.g. dispatch has not yet completed), **When** the coordinator updates, **Then** the live price sensor displays the most recent available RTD price and records a timestamp indicating when that price was dispatched.
3. **Given** no RTD data is returned by the API, **When** the coordinator updates, **Then** the live price sensor state becomes unavailable until RTD data is successfully retrieved.

---

### User Story 2 - Near Real-Time Price Updates (Priority: P1)

As a home energy manager, I want the live price sensor to update every 5 minutes so that automations reacting to price spikes or troughs respond with minimal latency.

**Why this priority**: RTD prices are published approximately every 5 minutes. Polling every 30 minutes renders the RTD data stale by up to 25 minutes, defeating its purpose. A 5-minute poll interval ensures price changes are reflected promptly.

**Independent Test**: Can be fully tested by observing that the sensor's last-changed timestamp advances no more than ~5 minutes behind the system clock across multiple polling cycles.

**Acceptance Scenarios**:

1. **Given** the integration is running, **When** 5 minutes elapse, **Then** the coordinator fetches fresh prices and all enabled sensors may update their state.
2. **Given** the coordinator is running on a 5-minute cycle, **When** a transient API error occurs, **Then** the coordinator retries with a shorter back-off interval, re-establishing the 5-minute cadence once the API recovers.
3. **Given** forecast and accounting sensors share the same coordinator, **When** the coordinator runs every 5 minutes, **Then** forecast and accounting data also refresh at 5-minute intervals without error (more frequent than previously but not harmful).

---

### User Story 3 - Continued Forecast and Accounting Availability (Priority: P2)

As a home energy manager, I want my day-ahead forecast, intraday forecast, and accounting (settled price) sensors to continue working correctly after the coordinator polling interval is changed to 5 minutes, so that no existing sensor functionality is degraded.

**Why this priority**: The polling interval change is a side-effect of the live price improvement. Users who rely on forecast or accounting sensors must not experience regressions.

**Independent Test**: Can be fully tested by enabling all sensor types simultaneously and verifying each sensor continues to display valid data after several 5-minute update cycles.

**Acceptance Scenarios**:

1. **Given** forecast sensors are enabled, **When** the coordinator runs on a 5-minute cycle, **Then** day-ahead and intraday forecast data refreshes correctly and sensor history accumulates as expected.
2. **Given** accounting sensors are enabled, **When** the coordinator runs on a 5-minute cycle, **Then** settled prices, daily import cost, and daily export revenue sensors update correctly without duplicated or incorrect accounting entries.

---

### Edge Cases

- What happens when RTD prices are published for the current trading period but the coordinator polls mid-period before RTD data is available? (Show most recently dispatched RTD price with its timestamp.)
- What happens if the RTD API endpoint is temporarily unavailable while forecast/accounting APIs are healthy? (Live price sensor goes unavailable; forecast and accounting sensors are unaffected.)
- What happens if a user restarts Home Assistant mid-trading-period? (RestoreEntity behaviour preserves the last known live price until the coordinator delivers fresh RTD data, subject to the existing 30-minute staleness guard.)
- How does the 5-minute poll interact with HA's startup cost during initial setup? (First refresh is unchanged — coordinator fetches data once during async_config_entry_first_refresh; ongoing polling then runs at 5-minute intervals.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The live price sensor MUST derive its state from the RTD (Real-Time Dispatch) schedule price for the market node, not from a forecast schedule.
- **FR-002**: The coordinator MUST poll the electricity price API every 5 minutes when at least one market-node subentry is configured and active.
- **FR-003**: The live price sensor MUST display the price from the most recently dispatched RTD trading period for the configured market node.
- **FR-004**: The live price sensor MUST become unavailable if no RTD price data is returned by the API for a given update cycle, and recover automatically when RTD data is available again.
- **FR-005**: The live price sensor's state attributes MUST include the trading period identifier and the trading datetime of the RTD price it is currently showing, so users can verify data freshness.
- **FR-006**: All other enabled sensor types (day-ahead forecast, intraday forecast, settled price, daily cost/revenue) MUST continue to function correctly at the new 5-minute poll cadence.
- **FR-007**: The RTD API request MUST be made only when the live price sensor is enabled for a subentry; subentries with live price disabled MUST NOT trigger an RTD fetch.
- **FR-008**: On coordinator retry after an API error, the system MUST resume the 5-minute poll interval once the error clears.

### Key Entities

- **RTD Price**: The actual dispatched price for a 30-minute trading period, published by the electricity market for the RTD schedule. Identified by market node, trading period number, and trading datetime.
- **Live Price Sensor**: The Home Assistant sensor that exposes the current RTD price for a configured market node. Previously derived from a forecast schedule; now derived from RTD.
- **Coordinator Poll Interval**: The frequency at which the shared DataUpdateCoordinator fetches fresh data. Changed from 30 minutes to 5 minutes to align with RTD publication cadence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The live price sensor state reflects the most recently dispatched RTD price within 5 minutes of its publication by the electricity market.
- **SC-002**: The live price sensor's displayed price is the actual RTD dispatched price (not a forecast), verifiable by the sensor reporting a schedule type of "RTD" in its state attributes.
- **SC-003**: All existing sensor types (forecast, settled, accounting) continue to produce valid, non-errored states after migration to the 5-minute coordinator cadence — zero regressions in the automated test suite.
- **SC-004**: The live price sensor recovers from RTD unavailability within one polling cycle (≤ 5 minutes) of RTD data becoming available again.
- **SC-005**: The coordinator completes each 5-minute update cycle without increasing the average number of API calls per hour beyond what is proportionate to the new cadence (i.e., RTD fetches occur only for subentries with live price enabled).

## Assumptions

- The electricity market publishes RTD prices on approximately a 5-minute cycle; polling every 5 minutes is sufficient to retrieve each new RTD dispatch result promptly.
- The electricity market API exposes RTD schedule prices through the same endpoint used for forecast schedules; no separate dedicated RTD endpoint is required.
- RTD prices are available for recent past trading periods (back-looking) and the most recently dispatched period; the API does not typically publish RTD prices significantly in advance.
- A single API call with a small `back` parameter (e.g. covering the last 2–3 trading periods) is sufficient to guarantee the most recently dispatched period is included in the response, even if the poll does not land exactly at the moment of RTD publication.
- The 5-minute coordinator interval affects all sensor types for all subentries within a config entry; there is no per-subentry interval configuration.
- The existing staleness guard on RestoreEntity for the live price sensor (30 minutes) remains appropriate even with RTD; if RTD data is more than 30 minutes old, the sensor should present as unavailable on startup rather than restoring a stale value.
- Forecast and accounting sensors do not require any changes beyond accommodating the increased poll frequency; the new cadence is harmless for those sensor types.
- The change in live price source (forecast → RTD) constitutes a meaningful enough behaviour change that entity history will show a data-source transition; no special migration handling is required beyond what HA naturally provides.
