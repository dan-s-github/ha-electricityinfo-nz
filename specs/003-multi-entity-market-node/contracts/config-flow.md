# Contract: Config Flow — MarketNodeSubentryFlow

**Branch**: `003-multi-entity-market-node` | **Date**: 2026-05-20

---

## Overview

The `MarketNodeSubentryFlow` replaces the 002 `SensorSubentryFlowHandler`. It configures a complete market node with independent toggles for live price, forecast, and accounting sensor sections. One subentry per market node; each subentry can create 1–8 sensor entities.

**Subentry type key**: `"market_node"` (changed from `"sensor"` in 002)

---

## Steps

### `user` step — Create market node

Presented when the user selects "Add market node" from the integration options.

**Schema**:

```python
vol.Schema({
    # Core
    vol.Required("node"): SelectSelector(SelectSelectorConfig(options=MARKET_NODE_OPTIONS)),
    vol.Required("price_unit"): SelectSelector(SelectSelectorConfig(
        options=[
            {"value": "c/kWh",    "label": "c/kWh (cents per kilowatt-hour)"},
            {"value": "NZD/kWh",  "label": "NZD/kWh (dollars per kilowatt-hour)"},
        ]
    )),

    # Live price section
    vol.Optional("enable_live_price", default=True): BooleanSelector(),

    # Forecast section
    vol.Optional("enable_forecast", default=False): BooleanSelector(),
    vol.Optional("forecast_type", default="price_responsive"): SelectSelector(
        SelectSelectorConfig(options=[
            {"value": "price_responsive", "label": "Price-responsive (PRSL/PRSS)"},
            {"value": "non_responsive",   "label": "Non-responsive (NRSL/NRSS)"},
        ])
    ),
    vol.Optional("forecast_horizons", default=["day_ahead"]): SelectSelector(
        SelectSelectorConfig(
            options=[
                {"value": "day_ahead", "label": "Day-ahead (24h / 48 periods)"},
                {"value": "intraday",  "label": "Intraday (4h / 8 periods)"},
            ],
            multiple=True,
        )
    ),
    vol.Optional("forecast_retention_hours", default=24): SelectSelector(
        SelectSelectorConfig(options=[
            {"value": 6,  "label": "6 hours"},
            {"value": 12, "label": "12 hours"},
            {"value": 24, "label": "24 hours"},
        ])
    ),

    # Accounting section
    vol.Optional("enable_accounting", default=False): BooleanSelector(),
    vol.Optional("accounting_retention_hours", default=24): SelectSelector(
        SelectSelectorConfig(options=[
            {"value": 24, "label": "24 hours (minimum)"},
            {"value": 48, "label": "48 hours"},
        ])
    ),
    vol.Optional("import_meter_entity_id"): EntitySelector(
        EntitySelectorConfig(domain="sensor", device_class="energy")
    ),
    vol.Optional("export_meter_entity_id"): EntitySelector(
        EntitySelectorConfig(domain="sensor", device_class="energy")
    ),
})
```

**Validation** (Python, after schema parse):

| Check | Error Key | FR |
|-------|-----------|-----|
| At least one of `enable_live_price`, `enable_forecast`, `enable_accounting` is `True` | `"no_sensor_type_enabled"` | FR-016 |
| If `enable_forecast=True`, `forecast_horizons` is non-empty | `"forecast_horizons_empty"` | FR-006 |
| If `import_meter_entity_id` provided, entity exists with `device_class: energy` | `"entity_not_energy_import"` | FR-018 |
| If `export_meter_entity_id` provided, entity exists with `device_class: energy` | `"entity_not_energy_export"` | FR-018 |
| `node` is a member of `MARKET_NODES` | `"node_invalid"` | FR-001 |

**On success**: `async_create_entry(title=_node_title(data), data=_build_node_data(user_input))`

**Subentry title format**: `"{NODE_LABEL} [{unit}]"` e.g., `"BRB0331 Bream Bay [c/kWh]"`

---

### `reconfigure` step — Edit market node

Same schema as `user` step, pre-filled with current subentry data.

**On success**: `async_update_and_abort(entry, subentry, title=..., data=...)`

**Sensor delta on reconfigure**:
- Newly enabled sensor types → entities created by HA on next platform reload
- Newly disabled sensor types → entities removed (FR-015) — handled by `sensor.async_setup_entry` comparing enabled config vs existing entities
- `node` change → entity unique IDs change; old entities become orphaned (user must manually remove from entity registry if desired)

---

## Data Builder

```python
def _build_node_data(user_input: dict) -> dict:
    """Build normalized subentry data dict from user input."""
    data = {
        "node": user_input["node"],
        "price_unit": user_input["price_unit"],
        "enable_live_price": user_input.get("enable_live_price", False),
        "enable_forecast": user_input.get("enable_forecast", False),
        "enable_accounting": user_input.get("enable_accounting", False),
    }
    if data["enable_forecast"]:
        data["forecast_type"] = user_input.get("forecast_type", "price_responsive")
        data["forecast_horizons"] = user_input.get("forecast_horizons", ["day_ahead"])
        data["forecast_retention_hours"] = int(user_input.get("forecast_retention_hours", 24))
    if data["enable_accounting"]:
        data["accounting_retention_hours"] = int(user_input.get("accounting_retention_hours", 24))
        data["import_meter_entity_id"] = user_input.get("import_meter_entity_id") or None
        data["export_meter_entity_id"] = user_input.get("export_meter_entity_id") or None
    return data
```

---

## Error String Keys (for `translations/en.json`)

| Key | Message |
|-----|---------|
| `no_sensor_type_enabled` | "At least one sensor type must be enabled." |
| `forecast_horizons_empty` | "Select at least one forecast horizon when forecasting is enabled." |
| `entity_not_energy_import` | "The selected import meter is not an energy meter (device_class: energy)." |
| `entity_not_energy_export` | "The selected export meter is not an energy meter (device_class: energy)." |
| `node_invalid` | "The selected market node is not valid." |

---

## Subentry Type Registration

In `ElectricityInfoConfigFlow`:

```python
@classmethod
def async_get_supported_subentry_types(cls, config_entry) -> dict:
    return {"market_node": MarketNodeSubentryFlow}
```

Note: The 002 `"sensor"` subentry type key is no longer registered after migration. Any remaining `"sensor"` subentries are converted to `"market_node"` by `async_migrate_entry`.
