# Manual Testing Guide - Price Schedules Sensor Platform

This guide provides step-by-step instructions for testing the Electricity Price Schedules sensor platform integration.

## Prerequisites

1. **Home Assistant Setup**: A working Home Assistant instance
2. **Electricityinfo NZ Credentials**: OAuth client ID and secret (from Phase 1 OAuth setup)
3. **Python Environment**: Local testing environment with `pytest` and dependencies installed

## Automated Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test Suites
```bash
pytest tests/test_sensor_multiple.py -v      # Multiple sensors tests (Phase 4)
pytest tests/test_unit_conversion.py -v      # Unit conversion tests (Phase 5)
pytest tests/test_sensor.py -v               # Sensor platform tests
```

### Type Checking
```bash
mypy custom_components/electricityinfo/ --config-file=pyproject.toml
```

## Manual Testing Procedures

### 1. Initial Setup

1. Copy the integration to your Home Assistant `custom_components/` directory:
   ```bash
   cp -r custom_components/electricityinfo <HA_CONFIG_DIR>/custom_components/
   ```

2. Restart Home Assistant

3. Go to **Settings → Devices & Services → Create Integration**

4. Search for "Electricity Info NZ" and select it

### 2. OAuth Authentication

1. Enter your OAuth credentials (from Phase 1)
   - **Client ID**: Your OAuth client ID
   - **Client Secret**: Your OAuth client secret

2. Click **Submit**

3. Verify success: Integration should appear in your devices list

### 3. Add First Price Sensor

1. Go to **Settings → Devices & Services** → Find "Electricity Info NZ"

2. Click the integration

3. Click **Configure** (or **Options** if available)

4. Click **Configure Sensors** → **Add Sensor**

5. Fill in the sensor form:
   - **Sensor ID**: `nea_daily_spot` (unique identifier)
   - **Schedule Type**: `daily_spot`
   - **Market Type**: `ENERGY`
   - **Node**: `NEA` (North Island)
   - **Forward Prices**: `24` (hourly for 24 hours)
   - **Unit**: `NZD/MWh`

6. Click **Submit**

7. Verify: New entity `sensor.electricityinfo_nz_nea_daily_spot_energy_nzd_mwh` appears

### 4. Test Price Display

1. Go to **Developer Tools → States** and search for your new sensor

2. Verify the state shows a current price (e.g., `125.45`)

3. Check entity attributes:
   - `timestamp`: Current update timestamp
   - `confidence_level`: Forecast confidence
   - `forecast_period`: Forecast range
   - `prices_array`: List of forward prices

### 5. Add Second Sensor (Multiple Sensors Test)

1. Go back to **Configure → Add Sensor**

2. Add another sensor with different parameters:
   - **Sensor ID**: `mid_daily_spot`
   - **Schedule Type**: `daily_spot`
   - **Market Type**: `ENERGY`
   - **Node**: `MID` (Midland)
   - **Forward Prices**: `24`
   - **Unit**: `c/kWh` (different unit)

3. Verify both sensors appear in state list

4. Check that MID prices are roughly 1/10 of NEA prices (due to unit conversion)

### 6. Test Unit Conversion

1. Compare sensors with same schedule but different units:
   - **NEA in NZD/MWh**: Should be ~100-150
   - **MID in c/kWh**: Should be ~10-15

2. Manually verify conversion:
   - Calculate: `NZD_price × 0.1 = c_per_kWh_price`
   - Example: `120 NZD/MWh × 0.1 = 12 c/kWh`

### 7. Test 30-Minute Update Cycle

1. Note the current price and timestamp

2. Wait for next update (typically within 30 minutes)

3. Verify timestamp updated in state attributes

4. Check that prices are consistent (same hourly values shift forward)

### 8. Test Error Recovery

#### Simulate Network Failure
1. Temporarily disable your internet connection or block the API

2. Monitor Home Assistant logs for error messages:
   ```
   [custom_components.electricityinfo] Error fetching price data
   [custom_components.electricityinfo] Retry 1/2, next retry in 1 minutes
   ```

3. Verify sensor state shows as `unavailable` after 2 failed attempts

4. Re-enable connection

5. Verify sensor automatically recovers to showing price data

#### API Failure Simulation
1. Check integration logs for proper error handling:
   ```bash
   # In Home Assistant UI: Settings → Logs
   # Search for "electricityinfo" entries
   ```

2. Verify error messages don't contain:
   - Sensitive credentials (client_id, client_secret, access tokens)
   - Full API responses with PII

### 9. Test State Persistence

1. Note the current price and timestamp for a sensor

2. Restart Home Assistant

3. Immediately after restart, check the sensor state:
   - Should display the previously stored price
   - Should NOT show `unknown` or `unavailable`
   - Should restore all attributes

### 10. Test Configuration Editing

1. Go to sensor configuration and edit an existing sensor:
   - Change **Forward Prices** from `24` to `48`
   - Change **Unit** from `NZD/MWh` to `c/kWh`

2. Verify changes are applied immediately

3. Check that prices display in the new unit

### 11. Test Sensor Deletion

1. Go to sensor configuration

2. Select a sensor and delete it

3. Verify the corresponding entity is removed from Home Assistant

4. Verify remaining sensors continue to update normally

## Automation Testing

### Example Automations

#### Alert on High Prices
```yaml
automation:
  - alias: "Notify on high electricity prices"
    trigger:
      platform: state
      entity_id: sensor.electricityinfo_nz_nea_daily_spot_energy_nzd_mwh
    condition:
      condition: numeric_state
      entity_id: sensor.electricityinfo_nz_nea_daily_spot_energy_nzd_mwh
      above: 200
    action:
      service: notify.notify
      data:
        message: "High electricity prices: {{ states('sensor.electricityinfo_nz_nea_daily_spot_energy_nzd_mwh') }} NZD/MWh"
```

#### Schedule Load Shifting
```yaml
automation:
  - alias: "Run appliances during low-price periods"
    trigger:
      platform: state
      entity_id: sensor.electricityinfo_nz_nea_daily_spot_energy_c_per_kwh
      # Trigger when prices drop below 10 c/kWh
    condition:
      condition: numeric_state
      entity_id: sensor.electricityinfo_nz_nea_daily_spot_energy_c_per_kwh
      below: 10
    action:
      service: switch.turn_on
      target:
        entity_id: switch.pool_pump
```

## Troubleshooting

### Sensor Shows "Unavailable"
1. Check Home Assistant logs for coordinator errors
2. Verify OAuth credentials are still valid
3. Check your internet connection
4. Try restarting the integration

### Prices Not Updating
1. Check that 30 minutes have passed since last update
2. Verify sensor configuration in options flow
3. Check Home Assistant logs for update errors
4. Monitor coordinator refresh cycle

### Incorrect Unit Conversion
1. Verify `CONF_UNIT_PREFERENCE` is set correctly
2. Check that conversion factor is 0.1 (1 NZD/MWh = 0.1 c/kWh)
3. Compare manual calculation with displayed value
4. Check entity attributes for `prices_array` conversion

### Missing Sensor Entities
1. Verify sensors are configured in options flow
2. Check that `CONF_SENSORS` list is not empty
3. Restart Home Assistant to reload config
4. Monitor logs for entity creation errors

## Success Criteria Checklist

- [ ] Multiple sensors can be configured with different parameters
- [ ] Prices display in configured units (NZD/MWh or c/kWh)
- [ ] Sensors update every 30 minutes with new data
- [ ] Prices persist across Home Assistant restarts
- [ ] Entity IDs follow naming convention: `sensor.electricityinfo_nz_{node}_{schedule_type}_{market_type}_{unit}`
- [ ] No sensitive data (credentials, tokens) in logs
- [ ] Error recovery works: sensor marks unavailable after 2 failures, recovers on success
- [ ] Unit conversion accuracy verified (±0.01 c/kWh)
- [ ] All 31 automated tests pass
- [ ] Type checking passes (mypy clean)

## Performance Notes

- Coordinator update cycle: 30 minutes (configurable via `UPDATE_INTERVAL_MINUTES`)
- First retry interval: 1 minute
- Max retries before marking unavailable: 2
- Exponential backoff: `retry_interval × 2^(attempt-1)`

## Additional Resources

- [Specification](specs/002-price-schedules-sensor/spec.md) - Feature requirements and user stories
- [Technical Plan](specs/002-price-schedules-sensor/plan.md) - Architecture and implementation details
- [Research & Decisions](specs/002-price-schedules-sensor/research.md) - Technology choices and rationale
- [API Contract](specs/002-price-schedules-sensor/contracts/config-flow.md) - Config flow UI/UX
- [Data Model](specs/002-price-schedules-sensor/data-model.md) - Entity definitions
