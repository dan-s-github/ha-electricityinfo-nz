# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


### Added - OAuth Config Flow (Phase 1)

- OAuth 2.0 Client Credentials authentication flow
- MarketPricesClient library wrapper integration
- Config flow user interface for credentials entry
- Token validation and management
- State persistence with config entry
- Full type checking and test coverage

## v1.0.0rc0 (2026-05-11)

### Feat

- remove unsupported Final and Interim schedule types
- forecast excludes current period; staleness guard on restore
- **sensor**: migrate forecast attribute to forecast_solar convention (T056-T063)
- consolidate price schedules sensor platform updates
- Phase 1-6 implementation complete
- **002-price-schedules-sensor**: Generate actionable task breakdown
- Add implementation plan for price schedules sensor
- Add spec and checklist for price schedules sensor (002)
- **oauth**: Complete Phase 4 - Token Validation & Phase 7 Polish
- **oauth**: Phase 3 - OAuth flow initialization and redirect
- add OAuth config flow feature specification
- scaffold electricityinfo_nz integration

### Fix

- remove incorrect state_class for monetary sensors
- add state_class attribute for long-term statistics (FR-005)
- **sensor**: SC-008 available property; add T049-T055 tests
- round all prices to 3 decimal places
- set display precision to 3 for c/kWh, 2 for NZD/MWh
- sort prices ascending; prices_array includes trading_date and period
- log native_value (converted) not raw price in sensor update
- resolve PR review comments for price sensor platform
- satisfy mypy typing for selectors and subentry setup
- Update hacs.json country code and add repo topics
- Address Copilot PR review comments on OAuth config flow
- **oauth**: Resolve linting issues - ARG002, TC003, TC004

### Refactor

- implement Client Credentials OAuth flow with comprehensive fixes
- **oauth**: Fix import statement - use correct library interface
