# Contract: Config Flow Options UI/UX

**Feature**: Electricity Price Schedules Sensor Platform
**Component**: Home Assistant Options Flow (sensor configuration UI)
**Date**: 2026-05-05

## Overview

This contract defines the user interface for managing electricity price sensors via Home Assistant's **Config Subentry Flow** — HA's native mechanism for adding child items to a config entry.

> **Architecture note**: This contract was originally written for a multi-step Options Flow (`configure_sensors` → `add_sensor`). The shipped implementation uses `ConfigSubentryFlow` instead. HA natively manages the sensor list and handles deletion; the flow only provides `user` (add) and `reconfigure` (edit) steps. The `unit_preference` field was never built — both units are always created as separate entities.

Users access sensor management via:

**Settings > Devices & Services > Electricityinfo NZ > + Add sensor** (to add)
**Settings > Devices & Services > Electricityinfo NZ > [sensor] > ⋮ > Reconfigure** (to edit)
**Settings > Devices & Services > Electricityinfo NZ > [sensor] > ⋮ > Delete** (to remove)

---

## User Flows

### Flow 1: Add New Sensor (`async_step_user`)

**Entry**: User clicks **+ Add sensor** on the Electricityinfo NZ integration card.

**Step: `user`**

Displays a form with these fields:

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| Display Name | text | No | — | any string, stripped |
| Schedule Type | select | Yes | — | must be in `SCHEDULE_TYPES` |
| Market Type | select | Yes | — | must be in `MARKET_TYPES` |
| Market Node | select | Yes | — | must be in `MARKET_NODES` |
| Forward Hours | slider (1–84) | Yes | 24 | 1 ≤ n ≤ 84 |

On valid submit: subentry created, title derived as `"{name} · {node} {schedule} ({market})"` (or `"{node} {schedule} ({market})"` if no name). Two entities are automatically created — one NZD/MWh, one c/kWh.

On invalid submit: form re-shown with inline error messages.

---

### Flow 2: Edit Existing Sensor (`async_step_reconfigure`)

**Entry**: User selects **Reconfigure** on an existing sensor subentry.

**Step: `reconfigure`**

Same form as `user`, pre-populated with the current subentry values. On valid submit, `async_update_and_abort` persists the updated data and aborts the flow with reason `reconfigure_successful`.

---

### Flow 3: Delete Sensor

Handled entirely by HA's built-in subentry deletion UI. No custom flow step required. Full integration reload is triggered after deletion.

---

## Validation Rules

Validation is two-layered: HA's `SelectSelector` rejects values not in the option list at the schema level; `_validate_sensor_fields()` provides an explicit Python check with user-facing error keys.

### Display Name
- Optional
- Stripped of leading/trailing whitespace before storage
- Omitted from subentry data if empty

### Schedule Type
- Required
- Must be one of the values in `SCHEDULE_TYPES` (e.g., "Final", "Interim", "RTD", "WDS", …)

**Error key**: `schedule_type_invalid`

### Market Type
- Required
- Must be one of the values in `MARKET_TYPES` (currently `"E"` or `"R"`)

**Error key**: `market_type_invalid`

### Market Node
- Required
- Must be one of the values in `MARKET_NODES` (e.g., "HAY2201", "BEN2201", …)

**Error key**: `node_invalid`

### Forward Hours (`forward_prices_count`)
- Optional (defaults to 24)
- Must be between 1 and 84 (enforced by `NumberSelector` slider)
- Stored as int; coordinator multiplies × 2 for 30-min trading periods

---

## Data Contract

### Input (User provides via form)

```python
{
    "name": "Auckland RTD Prices",  # str, optional — omitted if empty
    "schedule_type": "RTD",         # str, from SCHEDULE_TYPES
    "market_type": "E",             # str, from MARKET_TYPES
    "node": "HAY2201",              # str, from MARKET_NODES
    "forward_prices_count": 24,     # int, 1–84
}
```

### Output (Saved to config subentry)

```python
subentry.data = {
    "schedule_type": "RTD",
    "market_type": "E",
    "node": "HAY2201",
    "forward_prices_count": 24,
    "name": "Auckland RTD Prices",  # only present if non-empty
}
subentry.title = "Auckland RTD Prices · HAY2201 RTD (E)"
# or without name:
subentry.title = "HAY2201 RTD (E)"
```

Two entities are created automatically from each subentry — one NZD/MWh, one c/kWh. There is no `unit_preference` field.

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
Hint: "Number of hourly prices to retrieve (1-84, typically 24 for daily or 84 for extended)"
Input: Number field
Min: 1
Max: 84
Default: 24
Required: Yes
```

---

## Post-Save Behavior

After a subentry is created or reconfigured:

1. **Subentry stored**: HA persists the subentry data in config entry storage
2. **`add_update_listener` callback fires** in `__init__.py`
3. **Full integration reload** triggered (`async_reload`) — coordinator and all entities reinitialise
4. **Two entities appear**: NZD/MWh and c/kWh entities for the subentry become visible in the device card within ~2 minutes (SC-007)

---

## Summary

The config flow uses HA's `ConfigSubentryFlow` system. Each sensor subentry stores `schedule_type`, `market_type`, `node`, `forward_prices_count`, and optionally `name`. Validation is two-layered (SelectSelector schema + explicit Python checks). Two entities are always created per subentry — one per price unit. `unit_preference` does not exist as a user-configurable field.

### Revision: Gap Report Sync 2026-05-09
- Reason: Replaced pre-subentry Options-list UX description (configure_sensors/add_sensor multi-step flow, unit_preference field, Sensor ID uniqueness) with the shipped ConfigSubentryFlow architecture. Removed obsolete validation rules for Sensor ID and Price Unit. Updated Data Contract to remove unit_preference and the sensors[] options list.
