# Contract: Sensor Platform Entity Interface

**Feature**: Electricity Price Schedules Sensor Platform
**Component**: Home Assistant Sensor Platform (entity creation and state management)
**Date**: 2026-05-05

## Overview

This contract defines how price sensors integrate with Home Assistant's entity platform. Sensors are automatically created from `sensor` subentries on the config entry and updated via shared DataUpdateCoordinator every 30 minutes.

> **Architecture note**: This contract was originally written for an Options-list UX. The shipped implementation uses `ConfigSubentryFlow` — HA's native subentry system. Each sensor subentry produces two entities (NZD/MWh and c/kWh) that share one device context and one coordinator.

---

## Entity Creation

### Trigger

Entities created when:
1. Integration loads (on Home Assistant startup)
2. User adds a sensor subentry via **Settings > Devices & Services > Electricityinfo NZ > + Add sensor**
3. Integration reloads after a subentry change (full reload, not incremental)

### Entity Lifecycle

```python
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    for subentry in entry.subentries.values():
        if subentry.subentry_type == "sensor":
            entities = [
                PriceSensorEntity(coordinator, entry, subentry, unit=unit)
                for unit in ("NZD/MWh", "c/kWh")
            ]
            async_add_entities(entities, config_subentry_id=subentry.subentry_id)
```

### Entity ID Generation

Unique ID is based on the config entry ID and subentry ID, not on node/schedule values (which change on reconfigure):

```python
unit_suffix = unit.replace("/", "_").lower()
unique_id = f"electricityinfo_nz_{entry.entry_id}_{subentry.subentry_id}_{unit_suffix}"
```

**Example** (two entities per subentry):
- `electricityinfo_nz_abc123_sub001_nzd_mwh`
- `electricityinfo_nz_abc123_sub001_c_kwh`

Device identifier: `(DOMAIN, subentry.subentry_id)` — both unit entities share one device.

---

## Entity State & Attributes

### State (Current Price)

| Property | Value | Type | Example |
|----------|-------|------|---------|
| `state` | Current market price | float (str in HA) | `"45.23"` |
| `native_unit_of_measurement` | Entity's unit | str | `"NZD/MWh"` or `"c/kWh"` |
| `device_class` | `SensorDeviceClass.MONETARY` | — | monetary |
| `suggested_display_precision` | Decimal places | int | `2` (NZD/MWh), `3` (c/kWh) |

> **Canonical storage**: `_native_value` is always stored internally in NZD/MWh regardless of entity unit. The `native_value` property applies conversion at read time. On state restore, c/kWh values are multiplied back to NZD/MWh before storing.

### Attributes (Metadata)

Attributes align with **FR-006** (shipped implementation). The following are stored for every entity:

| Attribute | Type | Example | Description |
|-----------|------|---------|-------------|
| `timestamp` | str (ISO 8601) | `"2026-05-05T17:30:00+00:00"` | Trading datetime of current period |
| `trading_period` | int | `35` | HA trading period number |
| `node` | str | `"HAY2201"` | Market node (from API response) |
| `schedule` | str | `"RTD"` | Schedule type (from API response) |
| `run_type` | str | `"RTD"` | Run type (from API response) |
| `prices_array` | list[dict] | see below | All forward prices |

`prices_array` element shape:
```json
{
  "trading_date": "2026-05-05",
  "trading_period": 35,
  "price": 45.23
}
```
For c/kWh entities, `price` in each element is converted to c/kWh. For NZD/MWh entities, `price` is in NZD/MWh.

### Example State JSON

```json
{
  "entity_id": "sensor.electricityinfo_nz_abc123_sub001_nzd_mwh",
  "state": "45.23",
  "attributes": {
    "timestamp": "2026-05-05T17:30:00+00:00",
    "trading_period": 35,
    "node": "HAY2201",
    "schedule": "RTD",
    "run_type": "RTD",
    "prices_array": [
      {"trading_date": "2026-05-05", "trading_period": 35, "price": 45.23},
      {"trading_date": "2026-05-05", "trading_period": 36, "price": 46.10}
    ],
    "native_unit_of_measurement": "NZD/MWh",
    "icon": "mdi:flash"
  }
}
```

---

## Update Mechanism

### Global Update Cycle

All sensors share a single `DataUpdateCoordinator` that updates every 30 minutes. The coordinator fetches prices for each sensor subentry independently. `forward_prices_count` (hours) is multiplied by 2 before the API call to convert to 30-minute trading period count.

```python
for subentry in entry.subentries.values():
    if subentry.subentry_type == "sensor":
        forward_prices = subentry.data["forward_prices_count"] * 2  # hours → periods
        prices = await client.get_schedule_prices(
            schedule=subentry.data["schedule_type"],
            market_type=subentry.data["market_type"],
            nodes=[subentry.data["node"]],
            forward=forward_prices,
        )
        price_data[subentry.subentry_id] = {"prices": prices, "config": ...}
```

### Entity Update

When coordinator updates, `_handle_coordinator_update` is called on each entity:

```python
def _handle_coordinator_update(self) -> None:
    if not self.coordinator.data or self._sensor_id not in self.coordinator.data:
        self._native_value = None
        self._attributes = {}
        self.async_write_ha_state()
        return

    sensor_data = self.coordinator.data[self._sensor_id]
    if "error" in sensor_data:
        self._native_value = None
        self._attributes = {}
        self.async_write_ha_state()
        return

    # Update _native_value (always NZD/MWh) and _attributes
    # native_value property converts to c/kWh at read time
    self.async_write_ha_state()
```

Startup note: `async_request_refresh()` is called once per entity in `async_added_to_hass`. With two entities per subentry, two calls fire — the coordinator deduplicates in-flight requests.

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

### Canonical Internal Storage

`_native_value` is **always stored in NZD/MWh** regardless of the entity's display unit. Conversion is applied at read time:

```python
@property
def native_value(self) -> float | None:
    if self._native_value is None:
        return None
    if self._unit == "c/kWh":
        return round(self._native_value * 0.1, 3)  # NZD/MWh × 0.1 = c/kWh
    return round(self._native_value, 3)
```

On state restore, c/kWh values from storage are divided by 0.1 (multiplied by 10) to recover the NZD/MWh canonical value before storing in `_native_value`.

### prices_array Conversion

The c/kWh entity's `extra_state_attributes` converts each price in `prices_array`:

```python
if self._unit == "c/kWh" and "prices_array" in attrs:
    attrs["prices_array"] = [
        {**p, "price": round(p["price"] * 0.1, 3)}
        for p in attrs["prices_array"]
    ]
```

**Accuracy**: ±0.001 c/kWh (3 decimal places retained).

---

## State Persistence (RestoreEntity)

### Automatic Persistence

`PriceSensorEntity` extends `RestoreEntity`. HA saves state to `/.storage/core.restore_state` after each write.

```python
async def async_added_to_hass(self) -> None:
    await super().async_added_to_hass()

    if (last_state := await self.async_get_last_state()) is not None:
        raw_value = float(last_state.state) if last_state.state not in ("unknown", "unavailable") else None
        # c/kWh state is converted back to canonical NZD/MWh
        if raw_value is not None and self._unit == "c/kWh":
            raw_value = raw_value * 10.0  # c/kWh → NZD/MWh
        self._native_value = raw_value
        self._attributes = dict(last_state.attributes)

    await self.coordinator.async_request_refresh()
```

### Saved Data

Persisted in `/.storage/core.restore_state`:
- Current price (state) in display unit
- `prices_array`, `timestamp`, `trading_period`, `node`, `schedule`, `run_type` (attributes)

### On Home Assistant Restart

1. `async_added_to_hass` restores `_native_value` and `_attributes` from storage
2. `async_request_refresh()` is triggered to fetch fresh data
3. **Known limitation (T049)**: The `available` property returns `False` while `coordinator.data` is `None`, even though `_native_value` has been restored. The entity will show as unavailable until the first successful coordinator fetch. This conflicts with SC-008. Fix: `available` should return `True` when `_native_value` is set and `coordinator.data` is `None` (i.e., treat pre-fetch as "restored, pending refresh").

---

## Configuration Changes

### When Subentry Updated or Added

1. Subentry data updated in HA config entry store
2. `add_update_listener` callback fires in `__init__.py`
3. **Full integration reload** triggered (`async_reload`) — all sensors briefly reinitialise, coordinator restarts
4. New/updated entities appear within 2 minutes (SC-007)

### When Sensor Deleted

1. User deletes subentry via HA UI
2. Full integration reload triggered (same mechanism)
3. Entities associated with that subentry are removed from HA

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

Price sensors integrate with Home Assistant using `SensorEntity`, `RestoreEntity`, and `CoordinatorEntity` patterns with `ConfigSubentryFlow` for configuration. Each sensor subentry produces two entities (NZD/MWh and c/kWh) sharing one device and one coordinator. All sensors share a 30-minute global update cycle with exponential-backoff error recovery. Internal state is always in NZD/MWh; c/kWh conversion applied at display time. `prices_array` is a `list[dict]` with `{trading_date, trading_period, price}` per element. Known issue: restored state is not surfaced until first coordinator fetch (T049).

### Revision: Gap Report Sync 2026-05-09
- Reason: Rewrote entity lifecycle (subentry model), entity ID scheme, attribute table (aligned to FR-006), prices_array dict shape, update mechanism (hours×2 multiplier, async_request_refresh per entity), unit conversion (canonical NZD/MWh storage), state persistence (availability bug documented), configuration changes (full reload mechanism), and Summary. Removed all pre-subentry Options-list references.
