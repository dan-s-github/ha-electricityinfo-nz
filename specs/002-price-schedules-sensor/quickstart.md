# Quickstart: Electricity Price Schedules Sensor Platform

**Feature**: Electricity Price Schedules Sensor Platform
**Branch**: `002-price-schedules-sensor`
**Date**: 2026-05-05

## Feature Overview

This feature adds a Home Assistant sensor platform to the Electricityinfo NZ integration that displays electricity price schedules. Users can:

- Configure multiple price sensors via Home Assistant Options Flow
- View current and forecast prices in their preferred unit (NZD/MWh or c/kWh)
- Prices automatically update every 30 minutes
- Sensors gracefully recover from API failures

**Key Design Decisions**:
- Single 30-minute update cycle for all sensors (not per-sensor configurable in v1)
- Options Flow for managing sensors (not separate config entries)
- State persistence via RestoreEntity (forecast prices restored after restart)
- Partial data accepted as valid (robust to transient API issues)

---

## Developer Setup

### Prerequisites

- Home Assistant 2026.3.1+ running with Electricityinfo NZ integration (Phase 1: OAuth Config Flow)
- Python 3.14+
- Project dependencies installed: `uv sync`

### Clone and Branch

```bash
cd /path/to/ha-electricityinfo-nz
git checkout 002-price-schedules-sensor
```

### Directory Structure

```
custom_components/electricityinfo/
├── __init__.py              # Integration entry point
├── config_flow.py           # MODIFY: Add Options Flow steps for sensors
├── const.py                 # MODIFY: Add sensor constants
├── sensor.py                # CREATE: New sensor platform
├── manifest.json            # No changes
├── strings.json             # CREATE/MODIFY: Sensor translations
└── models/
    └── ...

specs/002-price-schedules-sensor/
├── spec.md                  # Feature specification
├── plan.md                  # This implementation plan
├── research.md              # Technology decisions
├── data-model.md            # Entity definitions
├── quickstart.md            # This file
└── contracts/
    ├── config-flow.md       # Options Flow UI contract
    └── sensor-platform.md   # Sensor entity contract

tests/
├── conftest.py              # MODIFY: Add sensor fixtures
├── test_config_flow_sensor_options.py  # CREATE
├── test_sensor_platform.py  # CREATE
└── integration/
    └── test_sensor_end_to_end.py   # CREATE
```

---

## Architecture Overview

### High-Level Flow

```
User opens Options in Home Assistant
    ↓
    ├─> Adds sensor config (node, schedule_type, market_type, unit_preference)
    ├─> Config saved to config_entry.options["sensors"]
    ├─> Sensor platform detects change
    └─> Creates PriceSensorEntity for each sensor
        ↓
        ├─> Shared DataUpdateCoordinator
        ├─> Fetches from Electricityinfo API (every 30 min)
        ├─> Updates all sensor states
        └─> State persisted via RestoreEntity
            ↓
            Home Assistant UI displays prices
```

### Key Components

1. **Options Flow** (`config_flow.py`)
   - Adds `async_step_options()` to manage sensor list
   - Users add/edit/remove sensors via Settings > Devices & Services > Options

2. **Sensor Platform** (`sensor.py` - new file)
   - Creates PriceSensorEntity for each SensorConfiguration
   - Uses DataUpdateCoordinator for 30-minute update cycle
   - Uses RestoreEntity for state persistence
   - Handles unit conversion and error recovery

3. **Data Models** (`const.py`, `models/`)
   - SensorConfiguration: user-provided config
   - PriceSensorEntity: Home Assistant entity
   - MarketPriceSchedule: API response

4. **Tests** (`tests/`)
   - Unit tests for config flow validation
   - Integration tests for sensor lifecycle
   - E2E tests with mocked API

---

## Implementation Phases

### Phase 1: Config Flow Options (Week 1)

**Goal**: Users can add/edit/remove sensor configurations

**Files to modify**:
- `config_flow.py`: Add `OptionsFlowHandler` with `async_step_options()` and sensor CRUD steps
- `const.py`: Add allowed schedule_type, market_type, node values
- `strings.json`: Add sensor configuration translations

**Key Methods**:
```python
class OptionsFlowHandler(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        """Start of options flow"""

    async def async_step_configure_sensors(self, user_input=None):
        """Display existing sensors, allow add/edit/delete"""

    async def async_step_add_sensor(self, user_input=None):
        """Add new sensor"""

    async def async_step_edit_sensor(self, user_input=None):
        """Edit existing sensor"""
```

**Tests**:
- `test_config_flow_sensor_options.py`: Test form validation, CRUD operations

### Phase 2: Sensor Platform (Week 2)

**Goal**: Create sensor entities and implement 30-minute update cycle

**Files to create**:
- `sensor.py`: New file with DataUpdateCoordinator + PriceSensorEntity

**Key Classes**:
```python
class PriceSensorEntity(SensorEntity, RestoreEntity, CoordinatorEntity):
    """Electricity price sensor"""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT  # Enables long-term statistics

    def __init__(self, coordinator, sensor_config):
        # Initialize from SensorConfiguration

    @property
    def native_value(self) -> float | None:
        # Return current price from coordinator data

    @property
    def native_unit_of_measurement(self) -> str:
        # Return "NZD/MWh"

    @property
    def unit_of_measurement(self) -> str:
        # Return user's preferred unit (NZD/MWh or c/kWh)

    async def async_added_to_hass(self):
        # Restore state from previous session
```

**Coordinator Logic**:
```python
async def _async_update_prices(coordinator):
    """Fetch prices for all sensors"""
    # Collect unique (node, schedule_type) combinations
    # Fetch from electricityinfo-nz library
    # Return aggregated prices dict
    # Handle errors (token expiry, network timeouts)
```

**Tests**:
- `test_sensor_platform.py`: Test entity creation, state updates, unit conversion
- `integration/test_sensor_end_to_end.py`: E2E with mocked API

### Phase 3: Testing & Polish (Week 3)

**Goal**: Full test coverage and documentation

**Tasks**:
- Verify all test scenarios pass
- Run linting: `ruff check --fix`
- Type checking: `mypy custom_components/`
- Update CHANGELOG.md

---

## Testing Strategy

### Unit Tests (Mocked API)

```bash
pytest tests/test_config_flow_sensor_options.py -v
pytest tests/test_sensor_platform.py -v
```

**Mocked fixtures**:
```python
@pytest.fixture
def mock_market_prices():
    """Mock Electricityinfo API response"""
    return {
        ("NEA", "daily_spot"): [
            {"price_value": 45.23, "timestamp": "...", "confidence_level": 0.95},
            {"price_value": 46.10, "timestamp": "...", "confidence_level": 0.94},
        ]
    }
```

### Integration Tests

```bash
pytest tests/integration/test_sensor_end_to_end.py -v
```

**Scenarios**:
- Add sensor via Options Flow → verify entity created
- Coordinator updates → verify state/attributes updated
- Partial data response → verify entity handles gracefully
- API failure → verify entity marked unavailable
- API recovers → verify entity transitions back to available
- Home Assistant restart → verify state restored
- Configuration change → verify entity updated

### Manual Testing (Optional)

With valid Electricityinfo OAuth credentials:

```bash
pytest tests/manual_live_api_test.py -v
```

**Verification**:
- Real API call returns prices
- Token refresh works
- Price conversion accurate

---

## Key Implementation Details

### DataUpdateCoordinator Usage

```python
coordinator = DataUpdateCoordinator(
    hass=hass,
    logger=logging.getLogger(__name__),
    name="Electricityinfo NZ Prices",
    update_interval=timedelta(minutes=30),
    update_method=_async_update_prices,
)
await coordinator.async_config_entry_first_refresh()
```

**Benefits**:
- Centralized 30-minute update cycle for all sensors
- Automatic retry on failure (can customize)
- Automatic unavailable state management
- Built-in error handling

### RestoreEntity Usage

```python
async def async_added_to_hass(self):
    await super().async_added_to_hass()

    # Restore previous state if Home Assistant restarted
    restored_data = await self.async_get_last_state()
    if restored_data:
        self._attr_native_value = float(restored_data.state)
        self._attr_extra_state_attributes = restored_data.attributes
```

**Benefits**:
- Prices visible immediately after restart
- No need to wait for first 30-minute update
- Automatic Home Assistant storage management

### Unit Conversion

```python
def _convert_price(price: float, from_unit: str, to_unit: str) -> float:
    if from_unit == "NZD/MWh" and to_unit == "c/kWh":
        return price / 10.0
    elif from_unit == "c/kWh" and to_unit == "NZD/MWh":
        return price * 10.0
    return price

@property
def state(self) -> str | None:
    if self.native_value is None:
        return None

    price = self.native_value
    if self.unit_of_measurement != self.native_unit_of_measurement:
        price = _convert_price(
            price,
            self.native_unit_of_measurement,
            self.unit_of_measurement
        )
    return str(round(price, 2))
```

### Error Handling

```python
async def _async_update_prices(coordinator):
    try:
        # Fetch from library
        prices = await library.get_schedules(...)
        return prices
    except TokenExpiredError:
        # Library handles token refresh
        raise UpdateFailed("Token refresh needed, retrying...")
    except (ConnectionError, TimeoutError) as err:
        raise UpdateFailed(f"Connection failed: {err}")
```

---

## Build & Test Commands

```bash
# Install dependencies
uv sync

# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_sensor_platform.py -v

# Lint and format
ruff check --fix custom_components/ tests/

# Type checking
mypy custom_components/

# Run integration tests
pytest tests/integration/ -v

# Run manual live API tests (requires valid OAuth credentials)
# pytest tests/manual_live_api_test.py -v
```

---

## Common Issues & Troubleshooting

### Issue: "Invalid sensor configuration"

**Cause**: Options Flow validation failed (e.g., invalid node name)

**Solution**: Check allowed values in `const.py` for schedule_type, market_type, node. Verify user selected valid values.

### Issue: "Sensor marked unavailable"

**Cause**: API call failed or data missing for sensor's (node, schedule_type)

**Solution**: Check coordinator logs. Verify OAuth token is valid. Check Electricityinfo API status. Coordinator will retry in 1 minute.

### Issue: "State not persisting after restart"

**Cause**: RestoreEntity not properly integrated

**Solution**: Verify PriceSensorEntity inherits from RestoreEntity. Verify `async_added_to_hass()` calls super and loads previous state.

### Issue: "Unit conversion inaccurate"

**Cause**: Rounding errors or incorrect conversion formula

**Solution**: Use formula: NZD/MWh ÷ 10 = c/kWh. Round to 2 decimal places for display. Test with known values (e.g., 100 NZD/MWh = 10 c/kWh).

---

## Development Checklist

- [ ] Create `sensor.py` with PriceSensorEntity and DataUpdateCoordinator
- [ ] Add Options Flow steps to `config_flow.py`
- [ ] Add sensor constants to `const.py`
- [ ] Add sensor translations to `strings.json`
- [ ] Write unit tests for config flow validation
- [ ] Write integration tests for sensor platform
- [ ] Verify all tests pass: `pytest tests/ -v`
- [ ] Run linting: `ruff check --fix`
- [ ] Run type checking: `mypy custom_components/`
- [ ] Test manually with Home Assistant dev instance
- [ ] Update CHANGELOG.md with new features
- [ ] Create PR with reference to specification and design docs

---

## References

- **Specification**: `specs/002-price-schedules-sensor/spec.md` (user stories, requirements)
- **Plan**: `specs/002-price-schedules-sensor/plan.md` (implementation strategy)
- **Research**: `specs/002-price-schedules-sensor/research.md` (technology decisions)
- **Data Model**: `specs/002-price-schedules-sensor/data-model.md` (entity definitions)
- **Config Flow Contract**: `specs/002-price-schedules-sensor/contracts/config-flow.md` (UI/UX)
- **Sensor Platform Contract**: `specs/002-price-schedules-sensor/contracts/sensor-platform.md` (entity lifecycle)
- **Home Assistant Docs**: https://developers.home-assistant.io/
  - [DataUpdateCoordinator](https://developers.home-assistant.io/docs/integration_architecture/#update_coordinator)
  - [RestoreEntity](https://developers.home-assistant.io/docs/integration_architecture/#restore_entity)
  - [SensorEntity](https://developers.home-assistant.io/docs/core/entity/sensor/)

---

## Next Steps

1. **Read the specification** (`spec.md`) to understand user stories and requirements
2. **Review design decisions** (`research.md`) to understand technology choices
3. **Study the data model** (`data-model.md`) to understand entities and relationships
4. **Read the contracts** (`contracts/*.md`) to understand implementation details
5. **Implement Phase 1: Config Flow** (Options Flow for sensor management)
6. **Implement Phase 2: Sensor Platform** (DataUpdateCoordinator + PriceSensorEntity)
7. **Write comprehensive tests** (mocked fixtures, unit tests, integration tests)
8. **Run full test suite** before submitting PR

Good luck! 🚀
