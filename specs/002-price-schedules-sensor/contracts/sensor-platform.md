# Contract: Sensor Platform Entity Interface

**Feature**: Electricity Price Schedules Sensor Platform
**Component**: Home Assistant Sensor Platform (entity creation and state management)
**Date**: 2026-05-05

## Overview

This contract defines how price sensors integrate with Home Assistant's entity platform. Sensors are automatically created from SensorConfiguration list in config entry options and updated via shared DataUpdateCoordinator every 30 minutes.

---

## Entity Creation

### Trigger

Entities created when:
1. Integration loads (on Home Assistant startup)
2. User adds a sensor via Options Flow
3. Integration options are updated

### Entity Lifecycle

```python
async def async_setup_entry(hass, config_entry, async_add_entities, discovery_info=None):
    """Setup price sensors from config entry options"""

    # 1. Get sensor list from config entry options
    sensor_configs = config_entry.options.get("sensors", [])

    # 2. For each sensor config, create a SensorEntity
    entities = []
    for sensor_config in sensor_configs:
        entity = PriceSensorEntity(coordinator, sensor_config)
        entities.append(entity)

    # 3. Add entities to Home Assistant
    async_add_entities(entities)
```

### Entity ID Generation

```python
entity_id = f"sensor.electricityinfo_nz_{node}_{schedule_type}_{market_type}_{unit_suffix}"
```

**Example**:
- node="NEA", schedule_type="daily_spot", market_type="energy", unit="NZD/MWh"
- entity_id = `sensor.electricityinfo_nz_nea_daily_spot_energy_nzd_mwh`

---

## Entity State & Attributes

### State (Current Price)

| Property | Value | Type | Example |
|----------|-------|------|---------|
| `state` | Current market price | float (str in HA) | `"45.23"` |
| `native_unit_of_measurement` | Always NZD/MWh | str | `"NZD/MWh"` |
| `unit_of_measurement` | Display unit (may differ) | str | `"NZD/MWh"` or `"c/kWh"` |

### Attributes (Metadata)

| Attribute | Type | Example | Description |
|-----------|------|---------|-------------|
| `timestamp` | str (ISO 8601) | `"2026-05-05T17:30:00Z"` | When this price was fetched |
| `confidence_level` | float (0-1) | `0.95` | API confidence in forecast |
| `forecast_period` | str | `"24h"` | Time range of forecast |
| `market_type` | str | `"energy"` | Market segment (ref) |
| `node` | str | `"NEA"` | Market node (ref) |
| `schedule_type` | str | `"daily_spot"` | Schedule type (ref) |
| `prices_array` | list[float] | `[45.23, 46.10, 47.50, ...]` | All forward prices |
| `friendly_name` | str | `"Electricityinfo NZ NEA Daily Spot Energy (NZD/MWh)"` | User-visible name |
| `icon` | str | `"mdi:flash"` | UI icon |

### Example State JSON

```json
{
  "entity_id": "sensor.electricityinfo_nz_nea_daily_spot_energy_nzd_mwh",
  "state": "45.23",
  "attributes": {
    "timestamp": "2026-05-05T17:30:00Z",
    "confidence_level": 0.95,
    "forecast_period": "24h",
    "market_type": "energy",
    "node": "NEA",
    "schedule_type": "daily_spot",
    "prices_array": [45.23, 46.10, 47.50, 46.80, 45.95],
    "native_unit_of_measurement": "NZD/MWh",
    "unit_of_measurement": "NZD/MWh",
    "icon": "mdi:flash",
    "friendly_name": "Electricityinfo NZ NEA Daily Spot Energy (NZD/MWh)"
  },
  "last_changed": "2026-05-05T17:30:00Z",
  "last_updated": "2026-05-05T17:30:00Z"
}
```

---

## Update Mechanism

### Global Update Cycle

All sensors share a single `DataUpdateCoordinator` that updates every 30 minutes:

```python
coordinator = DataUpdateCoordinator(
    hass=hass,
    logger=logging.getLogger(__name__),
    name="Electricityinfo NZ Price Scheduler",
    update_interval=timedelta(minutes=30),
    update_method=_async_update_prices,
)

async def _async_update_prices():
    """Fetch prices from Electricityinfo API for all sensors"""
    # 1. Collect unique (node, schedule_type) combinations from all sensors
    unique_requests = {
        (sensor.node, sensor.schedule_type)
        for sensor in sensors
    }

    # 2. Fetch prices for each combination (single API call per combo)
    all_prices = {}
    for node, schedule_type in unique_requests:
        prices = await library.get_schedules(node, schedule_type)
        all_prices[(node, schedule_type)] = prices

    # 3. Return aggregated prices
    return all_prices
```

### Entity Update

When coordinator updates (success or failure):

```python
def _handle_coordinator_update(self):
    """Update entity state from coordinator data"""

    if not self.coordinator.last_update_success:
        # API call failed
        self.set_available(False)  # Mark unavailable
        return

    # Get prices matching this sensor's (node, schedule_type)
    prices = self.coordinator.data.get(
        (self.node, self.schedule_type)
    )

    if not prices:
        self.set_available(False)
        return

    # Update state and attributes
    self.set_available(True)
    self._attr_native_value = prices[0]["price_value"]  # Current price
    self._attr_extra_state_attributes = {
        "timestamp": prices[0]["timestamp"],
        "confidence_level": prices.get("confidence_level"),
        "forecast_period": prices.get("forecast_period"),
        "market_type": self.market_type,
        "node": self.node,
        "schedule_type": self.schedule_type,
        "prices_array": [p["price_value"] for p in prices],
    }
    self.async_write_state()
```

---

## Availability Management

### Unavailable States

Entity marked unavailable in these scenarios:

1. **First API failure**: Coordinator retries after 1 minute
2. **Second API failure**: Coordinator marks all entities unavailable
3. **Token expired**: Attempt refresh; if fails, mark unavailable
4. **Network error**: Mark unavailable; retry after 1 minute
5. **Partial data**: If sensor's (node, schedule_type) missing from response, mark unavailable

### Recovery

Entity automatically transitions to available when:
1. Coordinator successfully fetches prices matching this sensor's config
2. All required attributes populated
3. `available` property set to True

### Automations During Unavailable

Automations will NOT trigger based on unavailable sensors:
- Template sensors expecting entity state will be empty
- Automations checking entity state will not execute
- State history will show "unavailable" gap

This is intentional—allows automations to gracefully handle temporary API outages.

---

## Unit Conversion

### Display Unit

Entity's `unit_of_measurement` determined by SensorConfiguration `unit_preference`:

```python
@property
def unit_of_measurement(self) -> str:
    """Return display unit (may differ from native unit)"""
    if self.sensor_config["unit_preference"] == "c/kWh":
        return "c/kWh"
    return "NZD/MWh"
```

### State Conversion

When Home Assistant displays state in UI, it automatically converts:

```python
display_value = convert_price_unit(
    native_value=45.23,
    from_unit="NZD/MWh",
    to_unit=entity.unit_of_measurement  # "c/kWh" or "NZD/MWh"
)
```

**Conversion formula**:
- NZD/MWh → c/kWh: divide by 10
- c/kWh → NZD/MWh: multiply by 10

**Accuracy**: ±0.01 c/kWh (conversion error < 0.01)

---

## State Persistence (RestoreEntity)

### Automatic Persistence

Using `RestoreEntity` mixin, Home Assistant automatically saves state:

```python
class PriceSensorEntity(SensorEntity, RestoreEntity, CoordinatorEntity):
    """Electricity price sensor with state persistence"""

    async def async_added_to_hass(self) -> None:
        """Restore state when entity is added"""
        await super().async_added_to_hass()

        # Restore from storage
        restored_data = await self.async_get_last_state()
        if restored_data:
            # Restore state and attributes
            self._attr_native_value = float(restored_data.state)
            self._attr_extra_state_attributes = restored_data.attributes
```

### Saved Data

In `/.storage/core.restore_state`:
- Current price (state)
- Forecast array (attributes)
- Timestamp
- Confidence level
- All other attributes

### On Home Assistant Restart

1. RestoreEntity loads previous state from storage
2. Entity immediately available in Home Assistant
3. Users see last known prices without waiting for next 30-min update
4. Coordinator update triggered normally (within 30 minutes)

---

## Configuration Changes

### When SensorConfiguration Updated

If user edits sensor via Options Flow:

1. Config entry options updated
2. Coordinator listeners notified
3. Integration async reload triggered (if entity still matches config)
4. Entity attributes updated without re-creating entity

### When Sensor Added

1. Config entry options updated
2. New SensorEntity created and added to Home Assistant
3. Entity immediately joins coordinator for next update cycle

### When Sensor Deleted

1. Config entry options updated
2. Entity removed from Home Assistant platform
3. Entity state deleted from storage

---

## Error Handling

### API Errors

| Error | Handling |
|-------|----------|
| Connection timeout | Mark unavailable, retry in 1 minute |
| Invalid OAuth token | Attempt token refresh (library), retry; if fails mark unavailable |
| Partial data (missing node/schedule) | Mark unavailable for this sensor (other sensors unaffected) |
| Invalid price data (non-numeric) | Log warning, mark unavailable, retry in 1 minute |

### Logging

```python
_LOGGER.debug(f"Updating prices for sensor {self.entity_id}")
_LOGGER.info(f"Updated {self.entity_id}: {self._attr_native_value} {self.unit_of_measurement}")
_LOGGER.warning(f"Failed to update {self.entity_id}: {error}")
_LOGGER.error(f"Critical error in {self.entity_id}: {error}", exc_info=True)
```

**Never log**:
- OAuth tokens or credentials
- Full API responses (log summary instead)
- Sensitive user data

---

## Testing Contract

### Test Scenarios

1. **Entity creation**: Verify entity created for each SensorConfiguration
2. **State updates**: Verify state/attributes updated on coordinator update
3. **Unit conversion**: Verify price displayed correctly in both units
4. **Partial data**: Verify entity handles missing forecast prices gracefully
5. **Error recovery**: Verify unavailable → available transition on success
6. **State persistence**: Verify state restored after Home Assistant restart
7. **Configuration changes**: Verify entity updates when config modified

### Mock Fixtures

```python
@pytest.fixture
def mock_market_prices():
    return {
        "NEA": {
            "daily_spot": {
                "prices": [
                    {"price_value": 45.23, "timestamp": "...", "confidence_level": 0.95},
                    {"price_value": 46.10, "timestamp": "...", "confidence_level": 0.94},
                ],
                "forecast_period": "24h"
            }
        }
    }
```

---

## Summary

Price sensors integrate with Home Assistant using standard SensorEntity, RestoreEntity, and DataUpdateCoordinator patterns. Each sensor represents a single user configuration (node + schedule type + market type). All sensors share a 30-minute global update cycle with automatic error recovery. State persists across restarts via RestoreEntity. Unit conversion is applied at display time. Changes to configuration immediately update corresponding entities.
