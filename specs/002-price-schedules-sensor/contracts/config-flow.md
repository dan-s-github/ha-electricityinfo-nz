# Contract: Config Flow Options UI/UX

**Feature**: Electricity Price Schedules Sensor Platform
**Component**: Home Assistant Options Flow (sensor configuration UI)
**Date**: 2026-05-05

## Overview

This contract defines the user interface and user experience for the Options Flow that allows users to add, edit, and remove price sensors. Users access this via:

**Settings > Devices & Services > Electricity Info NZ > Options**

---

## User Flows

### Flow 1: Add New Sensor

**Entry**: User clicks "Options" button on Electricity Info NZ device card

**Steps**:

1. **Step: `configure_sensors`** (List existing sensors)
   - Display heading: "Electricity Price Sensors"
   - Display list of currently configured sensors (if any):
     ```
     ✓ auckland_daily (NEA, daily_spot, energy, NZD/MWh)
     ✓ wellington_forward (MID, forward_market, energy, c/kWh)
     ```
   - Display two action buttons:
     - `+ Add Sensor` (link to `add_sensor` step)
     - `Done` (exit and save)
   - If no sensors exist: display "No sensors configured yet. Click 'Add Sensor' to create one."

2. **Step: `add_sensor`** (Add new sensor)
   - Display form with fields:
     ```
     Sensor ID* [text input, e.g., "auckland_daily"]
     Schedule Type* [dropdown: "daily_spot", "forward_market", "generation_forecast"]
     Market Type* [dropdown: "energy", "ancillary", "reserve"]
     Market Node* [dropdown: "NEA", "MID", "SOU", "West"]
     Forward Prices Count* [number input, default=24, range 1-168]
     Price Unit* [radio: "NZD/MWh" | "c/kWh", default="NZD/MWh"]
     ```
   - Display validation errors inline if user enters invalid values:
     ```
     ⚠ Sensor ID: Required and must be unique
     ⚠ Forward Prices Count: Must be between 1 and 168
     ⚠ Market Node: Invalid node selected
     ```
   - Display two action buttons:
     - `Create` (save and return to configure_sensors)
     - `Cancel` (discard and return to configure_sensors)

3. **Step: `configure_sensors`** (Return to list)
   - New sensor added to list
   - Display confirmation: "Sensor 'auckland_daily' created successfully"
   - User can add more or click `Done` to exit

### Flow 2: Edit Existing Sensor

**Entry**: User clicks on a sensor in the list (or an `Edit` button next to it)

**Steps**:

1. **Step: `configure_sensors`** (List existing sensors)
   - Same as Add Flow step 1
   - Each sensor has `Edit` link (e.g., "✎ auckland_daily")

2. **Step: `edit_sensor`** (Edit sensor properties)
   - Display same form as `add_sensor`, but pre-populated with current values
   - Display form fields:
     ```
     Sensor ID: auckland_daily [readonly - cannot change ID]
     Schedule Type: daily_spot [dropdown]
     Market Type: energy [dropdown]
     Market Node: NEA [dropdown]
     Forward Prices Count: 24 [number input]
     Price Unit: NZD/MWh [radio]
     ```
   - Display two action buttons:
     - `Update` (save and return to configure_sensors)
     - `Cancel` (discard and return to configure_sensors)

3. **Step: `configure_sensors`** (Return to list)
   - Sensor updated in list
   - Display confirmation: "Sensor 'auckland_daily' updated successfully"

### Flow 3: Delete Sensor

**Entry**: User clicks `Delete` button next to a sensor

**Steps**:

1. **Confirmation Dialog**:
   - Display warning: "Are you sure you want to delete sensor 'auckland_daily'?"
   - Display two action buttons:
     - `Delete` (confirm deletion)
     - `Cancel` (discard, stay in list)

2. **Step: `configure_sensors`** (Return to list)
   - Sensor removed from list
   - Display confirmation: "Sensor 'auckland_daily' deleted successfully"

---

## Validation Rules

### Sensor ID
- Required
- Must be unique within this config entry (no duplicates)
- Alphanumeric characters + underscore only
- Max 64 characters
- Suggested pattern: `{node}_{schedule_type}` (e.g., "nea_daily_spot")

**Error messages**:
- "Sensor ID is required"
- "Sensor ID must be unique (already have a sensor with this name)"
- "Sensor ID must contain only letters, numbers, and underscores"
- "Sensor ID must be 64 characters or fewer"

### Schedule Type
- Required
- Must be in Electricityinfo API allowed values
- Options: "daily_spot", "forward_market", "generation_forecast" (or as returned by API)

**Error messages**:
- "Schedule type is required"
- "Invalid schedule type selected"

### Market Type
- Required
- Must be in Electricityinfo API allowed values
- Options: "energy", "ancillary", "reserve" (or as returned by API)

**Error messages**:
- "Market type is required"
- "Invalid market type selected"

### Market Node
- Required
- Must be in Electricityinfo API allowed nodes
- Options: "NEA", "MID", "SOU", "West" (or as returned by API)

**Error messages**:
- "Market node is required"
- "Invalid node selected"

### Forward Prices Count
- Required
- Must be positive integer
- Must be <= 168 (7 days * 24 hours)
- Typically 24 (1 day) or 168 (1 week)

**Error messages**:
- "Forward prices count is required"
- "Must be a positive number"
- "Cannot exceed 168 (7 days of hourly prices)"

### Price Unit
- Required
- Must be exactly "NZD/MWh" or "c/kWh"

**Error messages**:
- "Price unit is required"
- "Invalid price unit selected"

---

## Data Contract

### Input (User provides)

```python
{
    "id": "auckland_daily",           # str, unique within entry
    "schedule_type": "daily_spot",    # str, from API-allowed values
    "market_type": "energy",          # str, from API-allowed values
    "node": "NEA",                    # str, from API-allowed nodes
    "forward_prices_count": 24,       # int, 1-168
    "unit_preference": "NZD/MWh"      # str, "NZD/MWh" or "c/kWh"
}
```

### Output (Saved to config entry)

```python
config_entry.options = {
    "sensors": [
        {
            "id": "auckland_daily",
            "schedule_type": "daily_spot",
            "market_type": "energy",
            "node": "NEA",
            "forward_prices_count": 24,
            "unit_preference": "NZD/MWh"
        },
        {
            "id": "wellington_forward",
            "schedule_type": "forward_market",
            "market_type": "energy",
            "node": "MID",
            "forward_prices_count": 168,
            "unit_preference": "c/kWh"
        }
    ]
}
```

---

## Error Handling

### Network/API Errors

If config validation step needs to call Electricityinfo API (e.g., to fetch allowed nodes/schedules), handle gracefully:

- **API timeout**: Display message "Could not reach Electricityinfo API. Please check your internet connection and try again."
- **Token expired**: Display message "Your OAuth token has expired. Please re-authenticate in the main integration settings."
- **Invalid config**: Display message "The configuration you provided is not valid. Please double-check and try again."

### Success Messages

Display clear confirmation messages:
- "Sensor 'auckland_daily' created successfully"
- "Sensor 'auckland_daily' updated successfully"
- "Sensor 'auckland_daily' deleted successfully"

---

## Accessibility & Localization

### Accessibility
- All form fields have clear labels
- Required fields marked with asterisk `*`
- Error messages displayed prominently (red text, icon)
- Radio buttons and dropdowns keyboard navigable
- Confirmation dialogs require explicit action (no "delete on Enter")

### Localization
- All UI strings are localized via Home Assistant's `strings.json` translation system
- String keys: `options.step.configure_sensors.*`, `options.step.add_sensor.*`, `options.step.edit_sensor.*`
- Support for multiple languages (at least English)

---

## UI Component Examples

### Dropdown (Schedule Type)
```
Label: "Schedule Type*"
Options:
  - daily_spot
  - forward_market
  - generation_forecast
Default: daily_spot
Required: Yes
```

### Radio Buttons (Price Unit)
```
Label: "Price Unit*"
Options:
  ◉ NZD/MWh (wholesale market prices)
  ○ c/kWh (retail equivalent in cents per kilowatt hour)
Default: NZD/MWh
Required: Yes
```

### Number Input (Forward Prices Count)
```
Label: "Forward Prices Count*"
Hint: "Number of hourly prices to retrieve (1-168, typically 24 for daily or 168 for weekly)"
Input: Number field
Min: 1
Max: 168
Default: 24
Required: Yes
```

---

## Post-Save Behavior

After user clicks `Done` and Options Flow closes:

1. **Config entry updated**: `config_entry.options["sensors"]` contains the new/updated list
2. **Coordinator notified**: Integration async update listeners triggered
3. **Sensor platform reloaded**: All price sensors recreated from updated SensorConfiguration list
4. **New entities appear**: Home Assistant UI refreshes; new sensors visible in device card

---

## Summary

The Options Flow provides a user-friendly interface for managing electricity price sensors without requiring manual YAML editing. Validation ensures only valid configurations are saved. Clear error messages guide users through the process. Changes take effect immediately after saving.
