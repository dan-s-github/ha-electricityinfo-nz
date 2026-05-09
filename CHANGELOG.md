# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-05-05

### Added - Price Schedules Sensor Platform (Phase 2)

#### Core Features
- **Price Sensors**: New sensor platform displays electricity prices from Electricityinfo NZ API
  - Updates every 30 minutes automatically
  - Displays current price with timestamp and forecast data
- **Multiple Sensor Support**: Users can configure multiple price sensors with different parameters
  - Schedule type: daily spot, forward market, generation forecast, etc.
  - Market type and node (region) selection per sensor
  - Configurable number of forward prices to retrieve
- **Price Unit Preference**: Display prices in either NZD/MWh or c/kWh
  - Automatic conversion (1 NZD/MWh = 0.1 c/kWh)
  - Per-sensor configuration
  - Conversion accuracy within ±0.01 c/kWh

#### Configuration & Setup
- **Options Flow UI**: Integrated into config flow for easy sensor management
  - Add/edit/delete sensor configurations
  - Inline validation of configuration values
  - Live sensor list with action buttons
- **State Persistence**: Prices persist across Home Assistant restarts
  - Automatic state restoration on startup
  - Users see most recent price immediately

#### Error Handling & Reliability
- **Graceful Failure Recovery**:
  - Automatic retry with exponential backoff (1-minute first retry)
  - Mark sensors as unavailable after 2 consecutive failures
  - Automatic recovery when API returns to normal
- **Partial Failure Isolation**: If API call fails for one sensor configuration, others continue to update
- **Network Resilience**: Handles connection errors, timeouts, API errors with proper logging

#### Technical Details
- Native unit storage in NZD/MWh for consistency
- Unit conversion applied at display time
- Separate entity per sensor configuration with unique IDs
- Coordinator pattern for centralized data management
- Full type checking (mypy clean)
- Comprehensive test coverage (31 tests)

### Testing
- Added unit tests for multiple sensors configuration and isolation
- Added unit tests for price unit conversion accuracy
- Added integration tests for config flow operations
- All tests passing (31/31)

### Success Criteria Met
✓ Users can configure 1+ price sensors with custom parameters
✓ Prices update every 30 minutes with real-time data
✓ Multiple sensors update independently without interference
✓ Graceful error handling with automatic recovery
✓ State persistence across Home Assistant restarts
✓ Price display in user-selected unit (NZD/MWh or c/kWh)
✓ Full test coverage with proper type checking
✓ Pre-commit hooks and linting pass

## [0.1.0] - 2026-04-XX

### Added - OAuth Config Flow (Phase 1)

- OAuth 2.0 Client Credentials authentication flow
- MarketPricesClient library wrapper integration
- Config flow user interface for credentials entry
- Token validation and management
- State persistence with config entry
- Full type checking and test coverage
