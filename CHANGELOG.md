# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v1.0.0rc8 (2026-11-03)

### Fix

- **coordinator**: keep live price through a missed poll and keep retry flag
- **config-flow**: return to credentials form after connection retries
- **coordinator**: address review findings on kept data and retries
- **config-flow**: show rate limits separately from connection errors
- **coordinator**: keep last good data and retry failed schedules sooner
- **config-flow**: handle all credential validation errors
- **coordinator**: isolate failures per price schedule
- **release**: keep uv.lock version in sync on bump

## v1.0.0rc7 (2026-11-01)

### Fix

- **accounting**: persist meter readings across restarts and reloads

## v1.0.0rc6 (2026-11-01)

### Fix

- **manifest**: sync version with the current release
- **accounting**: correct daily totals and cap retry backoff

## v1.0.0rc5 (2026-11-01)

### Fix

- **sensor**: import RestoreEntity from helpers.restore_state

### Refactor

- **config-flow**: migrate from voluptuous to probatio

## v1.0.0rc4 (2026-08-02)

### Feat

- **config-flow**: support reauth and manual credential reconfigure (#18)

### Fix

- **config-flow**: repopulate import/export meter entities on reconfigure (#19)
- **nodes**: replace fabricated market node list with full NZEM node set (#17)

## v1.0.0rc3 (2026-06-01)

### Feat

- **accounting**: add accounting meter support and previous-day sensors
- **accounting**: add accounting meter support and previous-day sensors

## v1.0.0rc2 (2026-05-31)

### Feat

- Implement RTD-based Live Price Sensor with 5-Minute Polling (#9)

## v1.0.0rc1 (2026-05-28)

### Feat

- complete Phase 6-8 implementation (T030-T044)
- ensure forecast and history arrays are sorted
- manually call _handle_coordinator_update on setup
- add async_added_to_hass logging to forecast sensor
- add initial handler log to forecast sensor
- add setup diagnostics logging to sensor platform
- enhance forecast sensor price diagnostics
- add detailed price filtering logs to forecast sensor
- add debug logging for forecast sensor API calls
- complete phase 4 forecast sensors
- complete phase 3 live price setup
- complete phase 2 foundational tasks
- implement phase 7 accounting sensors
- implement phase 6 reconfigure lifecycle
- implement phases 1-5 for multi-entity market-node

### Fix

- resolve PR review issues in syntax, MRO, and docs
- derive forecast and accounting back window from retention config
- align period handling across forecast and accounting sensors

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
