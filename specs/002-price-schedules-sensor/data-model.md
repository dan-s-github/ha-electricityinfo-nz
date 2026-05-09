# Data Model: Electricity Price Schedules Sensor Platform

**Feature**: Electricity Price Schedules Sensor Platform
**Branch**: `002-price-schedules-sensor`
**Date**: 2026-05-05
**Status**: Phase 1 Complete (Entity definitions and relationships)

## Overview

This document defines the core data entities, their attributes, relationships, and lifecycle for the price schedules sensor platform. All entities map to Home Assistant concepts (config entries, sensor entities, state storage).

---

## Entity: SensorConfiguration

**Purpose**: User-provided configuration for a single price sensor. Stored in Home Assistant config entry options.

**Storage**: Home Assistant config subentry data (`config_subentry_id`-keyed; one subentry per sensor configuration)

**Fields**:

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|-----------|-------------|
| `name` | str | No | — | Optional free text | User-facing display name for this subentry (e.g., "Auckland Daily") |
| `schedule_type` | str | Yes | — | Must be in Electricityinfo API allowed values | Type of price schedule (e.g., "daily_spot", "forward_market", "generation_forecast") |
| `market_type` | str | Yes | — | Must be in Electricityinfo API allowed values | Electricity market segment (e.g., "energy", "ancillary", "reserve") |
| `node` | str | Yes | — | Must be in Electricityinfo API allowed nodes (e.g., "NEA", "MID", "SOU") | Market node/region (e.g., "NEA" = North East Auckland) |
| `forward_prices_count` | int | Yes | 24 | Must be between 1 and 84 (FR-012) | Number of forward prices to retrieve and store (e.g., 24 = next 24 hours) |

**Example**:
```python
{
    "name": "Auckland Daily",      # optional
    "schedule_type": "daily_spot",
    "market_type": "energy",
    "node": "NEA",
    "forward_prices_count": 24,
}
```

**Lifecycle**:
1. Created: User adds a sensor subentry via Config Subentry Flow (Settings > Devices & Services > Electricity Info NZ > Add entry)
2. Updated: User reconfigures the subentry (name, schedule_type, market_type, node, forward_prices_count)
3. Deleted: User removes the subentry via the integration device page
4. Persisted: Config subentry data automatically saved by Home Assistant

**Relationships**:
- Multiple SensorConfiguration objects can exist in a single config entry (one list)
- Each SensorConfiguration drives creation of **two** PriceSensorEntity instances (one NZD/MWh, one c/kWh) — FR-005
- Config entry's OAuth credentials (client_id, client_secret, access_token) shared by all sensors

---

## Entity: PriceSensorEntity (Home Assistant SensorEntity)

**Purpose**: Home Assistant sensor entity that displays electricity price data to users. One entity per SensorConfiguration.

**Storage**: Home Assistant entity state + attributes (persisted via RestoreEntity)

**Home Assistant Properties**:

| Property | Type | Value | Description |
|----------|------|-------|-------------|
| `entity_id` | str | `sensor.electricityinfo_nz_{node}_{schedule_type}_{market_type}_{unit_suffix}` | Unique Home Assistant entity identifier |
| `unique_id` | str | `electricityinfo_nz_{config_entry_id}_{sensor_id}` | Unique ID within integration (used for entity tracking) |
| `name` | str | "Electricityinfo NZ {Node} {Schedule Type} {Market Type} ({Unit})" | User-visible friendly name |
| `icon` | str | `mdi:flash` | Icon displayed in UI |
| `device_class` | str | `"monetary"` | Tells Home Assistant this is a price (numeric with currency) |

**State & Attributes**:

| Name | Type | Example | Description |
|------|------|---------|-------------|
| **state** (current_price) | float | `45.23` | Current market price in native unit (NZD/MWh) |
| **native_unit_of_measurement** | str | `"NZD/MWh"` | Unit of raw state; always NZD/MWh internally |
| **unit_of_measurement** | str | `"NZD/MWh"` or `"c/kWh"` | Display unit (based on `unit_preference`); Home Assistant will convert state for UI |
| **timestamp** | str (ISO 8601) | `"2026-05-05T17:30:00Z"` | When this price was last successfully fetched from API |
| **trading_period** | int | `35` | NZ trading period number (1–48) for the current price |
| **node** | str | `"NEA"` | The market node (for reference; matches SensorConfiguration) |
| **schedule** | str | `"daily_spot"` | The schedule type (for reference; matches SensorConfiguration) |
| **run_type** | str | `"actual"` | Price run type returned by the API |
| **forecast** | list[dict] | `[{"period_start": "2026-05-09T12:00:00+12:00", "price": 45.23}, …]` | Time-series forecast in `forecast_solar` format. Each entry: `period_start` (ISO 8601 datetime with NZ timezone) and `price` (float in entity display unit). One entry per 30-min trading period up to `forward_prices_count`. |
| **available** | bool | `true` or `false` | Entity availability; set to False when data retrieval fails (FR-010) |

**State JSON Example**:
```json
{
  "entity_id": "sensor.electricityinfo_nz_nea_daily_spot_energy_nzd_mwh",
  "state": "45.23",
  "attributes": {
    "timestamp": "2026-05-05T17:30:00Z",
    "trading_period": 35,
    "node": "NEA",
    "schedule": "daily_spot",
    "run_type": "actual",
    "forecast": [
      {"period_start": "2026-05-09T12:00:00+12:00", "price": 45.23},
      {"period_start": "2026-05-09T12:30:00+12:00", "price": 46.10},
      {"period_start": "2026-05-09T13:00:00+12:00", "price": 47.50}
    ],
    "native_unit_of_measurement": "NZD/MWh",
    "unit_of_measurement": "NZD/MWh",
    "icon": "mdi:flash",
    "friendly_name": "Electricityinfo NZ NEA Daily Spot Energy (NZD/MWh)"
  }
}
```

**Lifecycle**:

1. **Setup** (`async_added_to_hass()`):
   - Entity created when config entry is loaded and sensor added to Options
   - RestoreEntity loads previous state from `.storage/restore_state`
   - DataUpdateCoordinator is initialized (single instance per config entry)

2. **Update** (every 30 minutes):
   - Coordinator calls `_async_update_data()` to fetch prices from Electricityinfo API
   - Coordinator updates all sensors with new data
   - Entity state/attributes updated; Home Assistant UI refreshes

3. **Failure** (API error or network failure):
   - First failure: Coordinator retries after 1 minute (exponential backoff)
   - Second failure: Coordinator marks entity `available = False` (unavailable state)
   - User sees "unavailable" in UI; automations triggered on this entity do not fire

4. **Recovery** (API returns after unavailable):
   - Coordinator successfully fetches prices
   - Entity automatically transitions from unavailable to available
   - State updated; UI refreshes

5. **Restart** (Home Assistant restarts):
   - RestoreEntity loads last known state + attributes from storage
   - Entity re-joins coordinator for next 30-minute update cycle
   - Users see forecast prices immediately (don't have to wait for next API call)

6. **Removal** (User deletes sensor from Options):
   - Sensor removed from `config_entry.options["sensors"]` list
   - Entity platform detects removal and calls `async_will_remove_from_hass()`
   - Entity state removed from storage

**Relationships**:
- 1:1 mapping to SensorConfiguration (one entity per config sensor)
- All entities in a config entry share a single DataUpdateCoordinator (for 30-minute global update cycle)
- All entities use OAuth credentials from parent config entry

---

## Entity: MarketPriceSchedule (API Response)

**Purpose**: Internal data model representing a price schedule response from Electricityinfo API. Fetched by coordinator, parsed, and used to update sensor entities.

**Storage**: Transient (in-memory); not persisted to Home Assistant storage

**Fields** (from electricityinfo-nz library response):

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `node` | str | `"NEA"` | Market node identifier |
| `schedule_type` | str | `"daily_spot"` | Schedule type |
| `market_type` | str | `"energy"` | Market segment |
| `timestamp` | str (ISO 8601) | `"2026-05-05T17:30:00Z"` | When this schedule was generated |
| `confidence_level` | float (0-1) | `0.95` | Forecast confidence |
| `prices` | list[dict] | `[{"price_value": 45.23, "period": 0}, ...]` | Array of price points |

**Example**:
```python
{
    "node": "NEA",
    "schedule_type": "daily_spot",
    "market_type": "energy",
    "timestamp": "2026-05-05T17:30:00Z",
    "confidence_level": 0.95,
    "prices": [
        {"price_value": 45.23, "period": 0},  # Hour 0
        {"price_value": 46.10, "period": 1},  # Hour 1
        {"price_value": 47.50, "period": 2},  # Hour 2
        # ... (up to forward_prices_count)
    ]
}
```

**Lifecycle**:
1. **Fetched**: Coordinator calls `electricityinfo_nz.MarketPricesClient.get_schedules()` once per 30-minute cycle
2. **Parsed**: Response validated and parsed into MarketPriceSchedule objects (one per node/schedule_type combination)
3. **Distributed**: Coordinator updates each sensor entity with matching prices
4. **Discarded**: Schedule goes out of scope after update (garbage collected)

**Relationships**:
- Multiple MarketPriceSchedule objects returned per API call (one per node/schedule_type)
- Each schedule matches one or more SensorConfiguration objects (by node, schedule_type, market_type)
- Current price (first element of prices array) mapped to PriceSensorEntity.state
- Full prices array mapped to PriceSensorEntity.prices_array attribute

---

## Data Transformations & Conversions

### 1. Price Unit Conversion

**Transformation**: NZD/MWh ↔ c/kWh

**Logic**:
```python
def convert_price_unit(price: float, from_unit: str, to_unit: str) -> float:
    """Convert electricity price between units"""
    if from_unit == to_unit:
        return price

    # NZD/MWh to c/kWh: divide by 10 (1 NZD = 10 cents, 1 MWh = 1000 kWh)
    if from_unit == "NZD/MWh" and to_unit == "c/kWh":
        return price / 10.0

    # c/kWh to NZD/MWh: multiply by 10
    if from_unit == "c/kWh" and to_unit == "NZD/MWh":
        return price * 10.0

    raise ValueError(f"Unknown conversion: {from_unit} -> {to_unit}")
```

**Applied**: In entity `state` property getter; display unit determined by `unit_preference` from SensorConfiguration

**Accuracy**: ±0.01 c/kWh (satisfies SC-006)

### 2. Entity ID Generation from Configuration

**Transformation**: SensorConfiguration → entity_id

**Logic**:
```python
def generate_entity_id(node: str, schedule_type: str, market_type: str, unit_preference: str) -> str:
    """Generate Home Assistant entity ID from sensor config"""
    unit_suffix = "c_kwh" if unit_preference == "c/kWh" else "nzd_mwh"
    parts = [
        "electricityinfo_nz",
        node.lower(),
        schedule_type.lower(),
        market_type.lower(),
        unit_suffix
    ]
    return f"sensor.{('_'.join(parts))}"
```

**Example**:
- Input: node="NEA", schedule_type="daily_spot", market_type="energy", unit="NZD/MWh"
- Output: `sensor.electricityinfo_nz_nea_daily_spot_energy_nzd_mwh`

**Applied**: In sensor platform setup (`async_setup_entry()`) when creating entities from SensorConfiguration list

---

## State Persistence & Restoration

### RestoreEntity Serialization

**Saved to**: `/.storage/core.restore_state`

**Format**: JSON

**Example**:
```json
{
  "version": 1,
  "key": "electricityinfo_nz.config_entry_xyz",
  "data": [
    {
      "entity_id": "sensor.electricityinfo_nz_nea_daily_spot_energy_nzd_mwh",
      "state": {
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
          "unit_of_measurement": "NZD/MWh"
        },
        "last_changed": "2026-05-05T17:30:00Z",
        "last_updated": "2026-05-05T17:30:00Z"
      }
    }
  ]
}
```

**Restoration**: When Home Assistant restarts and integration loads, RestoreEntity automatically loads this state. Users see forecast prices immediately without waiting for next 30-minute update cycle.

---

## Validation Rules

### SensorConfiguration Validation

Applied in Options Flow before save:

| Field | Validation |
|-------|-----------|
| `id` | Required; unique within config entry; alphanumeric + underscore only; max 64 chars |
| `schedule_type` | Required; must be in allowed Electricityinfo API values (e.g., "daily_spot", "forward_market") |
| `market_type` | Required; must be in allowed Electricityinfo API values (e.g., "energy", "ancillary") |
| `node` | Required; must be in allowed Electricityinfo API nodes (e.g., "NEA", "MID", "SOU") |
| `forward_prices_count` | Required; must be integer > 0 and <= 168 (max 7 days) |
| `unit_preference` | Required; must be exactly "NZD/MWh" or "c/kWh" |

### MarketPriceSchedule Validation

Applied in coordinator when parsing API response:

| Field | Validation |
|-------|-----------|
| `prices[].price_value` | Must be numeric; negative prices allowed (market anomalies) |
| `confidence_level` | Must be float 0.0–1.0; if missing or invalid, default to 0.5 |
| `timestamp` | Must be valid ISO 8601; if missing, use current time |

---

## Entity Relationships Diagram

```
ConfigEntry (OAuth credentials)
│
├─ options["sensors"] = [SensorConfiguration, ...]
│  │
│  ├─ SensorConfiguration #1
│  │  └─> PriceSensorEntity #1 (1:1 mapping)
│  │
│  ├─ SensorConfiguration #2
│  │  └─> PriceSensorEntity #2
│  │
│  └─ SensorConfiguration #N
│     └─> PriceSensorEntity #N
│
└─ DataUpdateCoordinator (shared across all sensors)
   │
   ├─> Fetches from Electricityinfo API (via electricityinfo-nz library)
   │   └─> Returns [MarketPriceSchedule, ...]
   │
   └─> Updates all PriceSensorEntity objects with latest prices
       └─> Each entity stores state + forecast array in Home Assistant storage (RestoreEntity)
```

---

## Summary: Key Data Flow

1. **Configuration**: User adds/edits sensors in Options Flow → SensorConfiguration dict saved to config entry options
2. **Initialization**: Integration loads → creates PriceSensorEntity for each SensorConfiguration → initializes shared DataUpdateCoordinator
3. **Update Cycle**: Every 30 minutes → Coordinator fetches from Electricityinfo API → gets MarketPriceSchedule → updates each PriceSensorEntity state + attributes
4. **Error**: API fails → Coordinator retries after 1 min → if fails again, marks entities unavailable
5. **Recovery**: API returns → Coordinator fetches → entities transition back to available
6. **Restart**: Home Assistant restarts → RestoreEntity loads previous state → entities show forecast prices until next 30-min update
7. **Display**: Home Assistant UI shows entity state (price) + attributes; unit conversion applied via `unit_of_measurement` property

All entities align with Home Assistant conventions (SensorEntity, RestoreEntity, DataUpdateCoordinator) and project constitution (OAuth security, library wrapper first, configurable architecture).
