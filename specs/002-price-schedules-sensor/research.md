# Research: Electricity Price Schedules Sensor Platform

**Feature**: Electricity Price Schedules Sensor Platform
**Branch**: `002-price-schedules-sensor`
**Date**: 2026-05-05
**Status**: Phase 0 Complete (Technology decisions and patterns researched)

## Overview

This document captures technology decisions, design patterns, and best practices researched for the price schedules sensor platform feature. All decisions align with project constitution (OAuth security, library wrapper first, TDD methodology).

---

## 1. Home Assistant Sensor Platform Pattern

### Decision: DataUpdateCoordinator + RestoreEntity Pattern

**What was chosen**: Use Home Assistant's standard `DataUpdateCoordinator` for centralized price schedule fetching (single 30-minute update cycle for all sensors) combined with `RestoreEntity` mixin for state persistence across restarts.

**Rationale**:
- **DataUpdateCoordinator** is the canonical Home Assistant pattern for coordinating updates to multiple entities from a single data source (Electricityinfo API). It handles:
  - Centralized async update logic with single coordinator instance
  - Automatic retry/backoff on failures (can be customized)
  - Automatic unavailable state management when data unavailable
  - Entity synchronization during updates
- **RestoreEntity** provides automatic restoration of sensor state + attributes after Home Assistant restart (satisfies SC-008)
- Both patterns are widely used in official Home Assistant integrations (e.g., weather, energy, integration-based sensors)
- Reduces boilerplate; Home Assistant handles retry logic, update scheduling, error state transitions

**Alternatives considered**:
1. **Manual async update loop + entity state management** - More control but significantly more boilerplate; manual unavailable state logic; no built-in recovery
2. **Direct API calls per sensor** - Violates global update interval design; 30+ concurrent API calls for 5+ sensors is inefficient
3. **Background tasks (asyncio.create_task)** - No built-in error handling or coordination; manual logging required; harder to test

**Implementation location**: `custom_components/electricityinfo/sensor.py` (new file)

---

## 2. Configuration Flow: Config Subentry Flow

> ⚠️ **Superseded**: This section was originally drafted for an Options Flow (`OptionsFlowHandler` +
> `options["sensors"]` list) design. The shipped implementation uses `ConfigSubentryFlowHandler` instead.
> The list-in-options model was replaced by discrete config subentries for cleaner entity lifecycle
> management and native HA subentry support. See spec.md clarification Q1.

### Decision: Extend existing OAuth config entry with Config Subentry Flow for sensor management

**What was chosen**: Implement `ConfigSubentryFlowHandler` on the existing config entry to manage sensor
subentries. Each sensor is a discrete subentry identified by `config_subentry_id`. Users access via
Settings > Devices & Services > Electricity Info NZ > Add entry / Reconfigure entry.

**Rationale**:
- **Simplicity**: Single config entry avoids UI clutter (e.g., 5 sensors = 5 separate config entries)
- **Credential scope**: All sensors share the same OAuth credentials already stored in the parent config entry
- **Home Assistant convention**: ConfigSubentryFlow is the recommended HA pattern for managing typed
  sub-entities (sensors, devices) within a single integration entry
- **Data storage**: Each sensor's config is stored as a config subentry dict keyed by `config_subentry_id`;
  no sensor list to manage manually
- **UX**: Users see a single integration entry; they use "Add entry" / "Reconfigure" to manage sensors

**Subentry schema** (per subentry):
```python
{
    "name": "Auckland Daily",      # optional display name
    "schedule_type": "daily_spot",
    "market_type": "energy",
    "node": "NEA",
    "forward_prices_count": 24,
}
```

**Alternatives considered**:
1. **Separate config entries per sensor** - Cleaner isolation but creates UI clutter; requires duplicating
   OAuth credentials or complex entry linking
2. **Options Flow + sensor list** - Original design; replaced by ConfigSubentryFlow for better entity
   lifecycle management and native HA subentry support
3. **YAML-only configuration** - Users prefer UI; YAML adds complexity without benefit
4. **Custom UI card/helper** - Out of scope for v1

**Implementation location**: `custom_components/electricityinfo/config_flow.py` (extend existing class)

---

## 3. Price Unit Conversion Strategy

### Decision: Convert at display time; store raw API price in state

**What was chosen**: Store the current price in its raw API unit (NZD/MWh) in the sensor state, then apply unit conversion (NZD/MWh ↔ c/kWh) based on `unit_preference` at display time via `SensorEntity.native_unit_of_measurement` and `device_class`.

**Rationale**:
- **Single source of truth**: Raw price stored once; no duplicate storage
- **Easy reconfiguration**: Users can change `unit_preference` and display updates immediately without re-fetching
- **Home Assistant native**: Sensor `native_unit_of_measurement` + `device_class="monetary"` are standard Home Assistant attributes; unit conversion is transparent to automations
- **Accuracy**: Linear conversion (1 NZD/MWh = 0.1 c/kWh) applied consistently; no rounding errors from stored conversions

**Conversion math**:
```python
def convert_price(native_price: float, from_unit: str, to_unit: str) -> float:
    """Convert price between NZD/MWh and c/kWh"""
    if from_unit == to_unit:
        return native_price
    if from_unit == "NZD/MWh" and to_unit == "c/kWh":
        return native_price * 0.1  # 1 NZD = 10 cents, MWh = 1000 kWh
    if from_unit == "c/kWh" and to_unit == "NZD/MWh":
        return native_price / 0.1
    raise ValueError(f"Unknown conversion: {from_unit} -> {to_unit}")
```

**Alternatives considered**:
1. **Store both units** - Redundant; synchronization issues if either changes; violates DRY principle
2. **Convert at API fetch time** - Locks in unit choice; reconfiguration requires re-fetch; more complex coordinator logic
3. **Use Home Assistant native unit conversion system** - Home Assistant doesn't have built-in NZD↔c/kWh conversion; would require custom UOM; adds complexity

**Implementation location**: `custom_components/electricityinfo/sensor.py` (entity properties + helpers)

---

## 4. Error Handling & Retry Strategy

### Decision: Exponential backoff (1 min first retry, mark unavailable on second failure) + automatic recovery

**What was chosen**: Implement retry logic in coordinator with:
- First failure: retry after 1 minute
- Second consecutive failure: mark all sensors unavailable (not error state)
- Recovery: automatic transition to available state when update succeeds after unavailable

**Rationale**:
- **Graceful degradation**: Unavailable state doesn't break Home Assistant automations (unlike error state which can trigger alerts)
- **Network resilience**: 1-minute retry window catches transient network blips; 2-failure threshold avoids spam
- **Token refresh**: If OAuth token expires, library's token refresh is attempted automatically; manual retry window allows time for refresh
- **Home Assistant native**: DataUpdateCoordinator's built-in `last_update_success` tracking and `async_update_listeners()` handle state transitions automatically

**Coordinator update logic**:
```python
async def _async_update_data():
    try:
        # Fetch all sensor prices from API (single call for all sensors)
        all_prices = await self.library.get_schedules(config)
        # Update internal state with prices
        return all_prices
    except TokenExpiredError:
        # Library handles token refresh; retry will succeed
        raise UpdateFailed(f"Token refresh needed, retrying...")
    except (ConnectionError, TimeoutError) as err:
        raise UpdateFailed(f"API connection failed: {err}")
```

**Alternatives considered**:
1. **Immediate unavailable on any failure** - Too harsh; doesn't recover from transient failures
2. **Exponential backoff without unavailable state** - Keeps retrying with increasing delays but doesn't gracefully degrade; automations waiting for data will timeout
3. **Custom retry logic (no DataUpdateCoordinator)** - More control but loses Home Assistant's automatic error state management and testing utilities

**Implementation location**: `custom_components/electricityinfo/sensor.py` (coordinator `_async_update_data()` method)

---

## 5. State Persistence & Forecast Storage

### Decision: Store current price + full forecast array in sensor state; restore via RestoreEntity

**What was chosen**: Use Home Assistant's `RestoreEntity` mixin to persist:
- **State**: Current price (numeric value)
- **Attributes** (includes forecast array):
  - `timestamp`: ISO 8601 datetime of last successful API call
  - `confidence_level`: API confidence in the forecast
  - `forecast_period`: Time range of the forecast (e.g., "24h")
  - `market_type`: The electricity market segment
  - `node`: The market node
  - `schedule_type`: The schedule type (e.g., daily_spot)
  - `prices_array`: Array of all forward prices from API (e.g., [45.23, 46.10, 47.50, ...])

**Rationale**:
- **Home Assistant native**: RestoreEntity automatically saves state to `.storage/restore_state` and loads on restart
- **Forecast preservation**: Users see forecast prices immediately after restart (satisfies SC-008)
- **Minimal storage**: Only latest snapshot stored, not rolling history (keeps storage footprint small)
- **Easy debugging**: Attributes visible in Home Assistant UI for troubleshooting

**State JSON example**:
```json
{
  "entity_id": "sensor.electricityinfo_nz_auckland_nea_daily_spot",
  "state": "45.23",
  "attributes": {
    "timestamp": "2026-05-05T17:30:00Z",
    "confidence_level": 0.95,
    "forecast_period": "24h",
    "market_type": "energy",
    "node": "NEA",
    "schedule_type": "daily_spot",
    "prices_array": [45.23, 46.10, 47.50, 46.80, 45.95],
    "unit_of_measurement": "NZD/MWh"
  }
}
```

**Alternatives considered**:
1. **No persistence (state only during runtime)** - Violates SC-008; users lose forecast data after restart
2. **InfluxDB/database storage** - Overkill for single snapshot; adds external dependency; complex for typical home users
3. **File-based JSON state** - Home Assistant already provides `.storage/` mechanism; no need to reinvent

**Implementation location**: `custom_components/electricityinfo/sensor.py` (SensorEntity inheritance + `async_added_to_hass()` method)

---

## 6. Partial Data Handling

### Decision: Accept and display partial data; missing fields render as empty/None

**What was chosen**: If Electricityinfo API returns a response with missing forecast prices or incomplete node data, the sensor accepts it as valid and displays available data with missing attributes set to None.

**Rationale**:
- **Robustness**: API transient issues (e.g., one market node slow to respond) don't break all sensors
- **User experience**: Better to show partial current price than mark everything unavailable
- **Real-world API behavior**: Production APIs often have region-specific delays; partial responses are expected
- **Graceful degradation**: Forecast array may have fewer elements than requested; users still get current price

**Implementation approach**:
```python
def _update_from_response(response):
    # Response may have missing forecast prices for some nodes
    # Accept what we got and fill None for missing fields
    self.current_price = response.get("price_value") or None
    self.forecast_prices = response.get("forecast_prices", [])  # May be shorter than expected
    self.confidence = response.get("confidence_level") or None
    # Missing fields remain None; Home Assistant UI renders them as "unavailable"
```

**Alternatives considered**:
1. **Strict validation (fail on incomplete data)** - Requires all fields present; any missing field marks sensor unavailable; too strict for production APIs
2. **Retry on incomplete response** - May retry forever if API always returns partial data for that node; better to show what we have
3. **Discard incomplete responses entirely** - Wastes available data; violates principle of graceful degradation

**Implementation location**: `custom_components/electricityinfo/sensor.py` (data parsing in `_async_update_data()`)

---

## 7. Testing Strategy: Mocked + Optional Live

### Decision: Unit/integration tests use mocked API responses; optional manual live API tests

**What was chosen**:
- **CI/CD pipeline** uses mocked Electricityinfo API responses (via pytest fixtures) for fast, deterministic tests
- **Manual verification** optional: developers can run live API tests with valid OAuth credentials to verify real integration

**Rationale**:
- **Fast CI**: Mocked tests run in <10 seconds; no external dependency; no flakiness
- **Deterministic**: Fixtures provide predictable data for testing edge cases (partial data, token expiration, retries)
- **Real-world verification**: Optional live tests allow developers to catch API breaking changes before release
- **Production readiness**: Manual tests document how to verify against staging/production Electricityinfo API

**Mock fixtures** (in `tests/conftest.py`):
```python
@pytest.fixture
def mock_market_prices():
    """Mock Electricityinfo API MarketPricesClient.get_schedules() response"""
    return {
        "node": "NEA",
        "prices": [
            {"price_value": 45.23, "timestamp": "2026-05-05T17:30:00Z", "confidence_level": 0.95},
            {"price_value": 46.10, "timestamp": "2026-05-05T18:30:00Z", "confidence_level": 0.94},
        ]
    }
```

**Test organization**:
- `tests/test_config_flow_sensor_options.py` - Options flow validation, sensor configuration save/edit/delete
- `tests/test_sensor_platform.py` - Sensor entity lifecycle, state updates, unit conversion, partial data handling
- `tests/integration/test_sensor_end_to_end.py` - E2E tests with mocked API
- `tests/manual_live_api_test.py` - OPTIONAL: Manual test with real API (run locally only, not in CI)

**Alternatives considered**:
1. **Live API tests required in CI** - Flaky (depends on external API availability); slow; requires storing OAuth credentials in CI environment (security risk)
2. **No live tests at all** - Misses real-world API breaking changes; no verification before release
3. **Record/replay (VCR)** - Records real API responses; good for regression but doesn't help catch API evolution; VCR cassettes can become stale

**Implementation location**: `tests/` directory (multiple test files) + `.specify/templates/live-api-test.py` (optional manual template)

---

## 8. Config Entry Validation

### Decision: Validate sensor configuration parameters in Options Flow before save; validate OAuth token availability on every update

**What was chosen**:
1. In Options Flow: validate schedule_type, market_type, node, forward_prices_count are within allowed ranges (e.g., node in ["NEA", "MID", "SOU"], forward_prices_count > 0)
2. During coordinator update: validate OAuth token is still valid; attempt token refresh if expired; catch `TokenExpiredError` from library

**Rationale**:
- **Config-time validation**: Prevents users saving invalid configs (e.g., invalid market node that doesn't exist)
- **Runtime validation**: OAuth token may expire between config save and first update; library handles refresh, but we catch and log appropriately
- **User feedback**: Options Flow shows validation errors immediately (before save); users can correct before closing dialog

**Validation logic**:
```python
async def async_step_user_sensors(self, user_input=None):
    """Add/edit sensor in Options Flow"""
    errors = {}

    if user_input:
        # Validate node is in allowed list
        if user_input["node"] not in ["NEA", "MID", "SOU"]:
            errors["node"] = "invalid_node"

        # Validate forward price count is positive
        if user_input["forward_prices_count"] <= 0:
            errors["forward_prices_count"] = "invalid_count"

        if not errors:
            return self.async_create_entry(data=user_input)

    # Return form with errors for user correction
    return self.async_show_form(step_id="user_sensors", errors=errors)
```

**Alternatives considered**:
1. **No validation (accept any config)** - Leads to confusing errors at runtime; bad UX
2. **Strict validation only (fail on any misconfiguration)** - Prevents graceful handling of transient API issues; too strict

**Implementation location**: `custom_components/electricityinfo/config_flow.py` (OptionsFlowHandler methods)

---

## 9. Entity ID Naming Convention

### Decision: Use hierarchical naming to reflect config hierarchy

**What was chosen**: Entity ID format: `sensor.electricityinfo_nz_{node}_{schedule_type}_{market_type}_{unit_suffix}`
- Example: `sensor.electricityinfo_nz_nea_daily_spot_energy_nzd_mwh`
- Friendly name: "Electricityinfo NZ NEA Daily Spot Energy (NZD/MWh)"

**Rationale**:
- **Uniqueness**: Ensures no collisions even with 10+ sensors
- **Readability**: Developers can immediately understand which sensor is which from entity ID
- **Home Assistant convention**: Follows standard entity ID naming (domain_manufacturer_description)
- **UX**: Friendly name is more user-readable in automations and UI

**Alternatives considered**:
1. **Generic naming** (e.g., `sensor.price_1`, `sensor.price_2`) - Not descriptive; hard to remember which is which
2. **User-provided names** - Adds complexity to config flow; potential for duplicates/invalid characters

**Implementation location**: `custom_components/electricityinfo/sensor.py` (entity platform setup)

---

## 10. Data Model: SensorConfiguration List Storage

### Decision: Store sensor list as `config_entry.options["sensors"]` = list of dicts

**What was chosen**: Each sensor represented as a dict with keys:
```python
{
    "id": str,  # Unique ID (e.g., "sensor_1", "auckland_daily", etc.)
    "schedule_type": str,  # e.g., "daily_spot"
    "market_type": str,  # e.g., "energy"
    "node": str,  # e.g., "NEA"
    "forward_prices_count": int,  # e.g., 24
    "unit_preference": str,  # "NZD/MWh" or "c/kWh"
}
```

**Rationale**:
- **Simple JSON-serializable**: Home Assistant config entry naturally serializes to JSON; no need for custom ORM
- **Flexible**: Easy to add fields in future (e.g., "refresh_interval" per-sensor in v2)
- **Options Flow friendly**: Forms naturally map to dict structure
- **Version-safe**: List allows incremental sensor additions without schema migration complexity

**Alternatives considered**:
1. **Dataclass/Pydantic models** - Overkill for simple config storage; adds external dependency
2. **Flat list** (only node names) - Too simplistic; can't store full sensor config (unit, schedule type, etc.)
3. **Nested objects** - Already using nested dict; could add nested objects but lists of dicts is sufficient

**Implementation location**: `custom_components/electricityinfo/const.py` + `config_flow.py` (data structure definitions)

---

## Summary: Technology Decisions

| Decision | Chosen Approach | Why | Alternatives |
|----------|-----------------|-----|--------------|
| **Entity coordination** | DataUpdateCoordinator + RestoreEntity | Canonical HA pattern; built-in error handling; auto recovery | Manual loops, per-entity API calls, background tasks |
| **Config management** | Options Flow (extend OAuth entry) | Single credential source; HA convention; no UI clutter | Separate entries per sensor, YAML-only |
| **Unit conversion** | Convert at display time | Single source of truth; easy reconfiguration; no rounding errors | Store both units, convert at fetch time |
| **Error recovery** | Exponential backoff + unavailable state | Graceful degradation; network resilience; HA native | Fail fast, mark unavailable immediately, manual recovery |
| **State persistence** | RestoreEntity + forecast array | HA native, forecast preserved, minimal storage | No persistence, database storage, file-based state |
| **Partial data** | Accept and display | Robustness to transient API issues; user sees partial price | Strict validation, retry forever |
| **Testing** | Mocked (CI) + optional live | Fast deterministic tests; real-world verification available | Live API required, record/replay, mocks only |
| **Config validation** | Validate at options time + runtime | Config-time feedback; runtime token refresh handling | No validation, strict validation only |
| **Entity naming** | Hierarchical (node_schedule_type_market_type) | Uniqueness, readability, HA convention | Generic names, user-provided names |
| **Sensor storage** | Config entry options list | Simple JSON, flexible, Options Flow friendly | Dataclass models, flat list, nested objects |

All decisions align with project constitution (OAuth security, library wrapper first, TDD, configurable architecture).
