# Quickstart: Multiple Entities for Market Node

**Branch**: `003-multi-entity-market-node` | **Date**: 2026-05-20

---

## Developer Setup

```bash
# Install all dependencies (including dev group)
uv sync

# Run full test suite (mocked API — no credentials needed)
pytest tests/ -v

# Run linter + auto-fix
ruff check --fix custom_components/ tests/

# Run type checker
mypy custom_components/

# Run live API tests (requires .env with ELECTRICITY_CLIENT_ID + ELECTRICITY_CLIENT_SECRET)
pytest tests/live/ -v -m live_api
```

**Prerequisites**: Python 3.14+, `uv` installed.

---

## Implementation Phases

### Phase 1 — Constants & Config (no tests yet)

Update `const.py` with all 003 constants:
- `SUBENTRY_TYPE = "market_node"` (replaces `"sensor"`)
- `PRICE_UNITS`, `FORECAST_TYPES`, `FORECAST_HORIZONS`, `RETENTION_OPTIONS`
- Schedule mapping dicts: `FORECAST_SCHEDULE_MAP` (`price_responsive`/`non_responsive` × day-ahead/intraday)
- Remove `CONF_SCHEDULE_TYPE`, `CONF_MARKET_TYPE`, `CONF_FORWARD_PRICES_COUNT`; add new keys

Update `config_flow.py`:
- Replace `SensorSubentryFlowHandler` with `MarketNodeSubentryFlow`
- Update `async_get_supported_subentry_types` to return `{"market_node": MarketNodeSubentryFlow}`
- Implement `_build_node_data`, `_validate_node_fields`, `_node_title`

Update `manifest.json`: bump version to 2.0.0 (MAJOR)

### Phase 2 — Migration (test-first)

Write `tests/test_migration.py` first:
- Test VERSION 1 `PRSL` subentry migrates to `enable_forecast=True`, `forecast_type="price_responsive"`, `forecast_horizons=["day_ahead"]`
- Test VERSION 1 `PRSS` subentry migrates to intraday
- Test VERSION 1 `NRSL`/`NRSS` subentries migrate with `non_responsive`
- Test that `enable_live_price=True` is always set during migration
- Test duplicate legacy entries for the same node keep first entry and skip later duplicates with warnings
- Test that entity ID change warnings are logged

Implement `async_migrate_entry` in `__init__.py`.

Set `ConfigFlow.VERSION = 2`.

### Phase 3 — Coordinator Refactor (test-first)

Write `tests/test_coordinator.py`:
- Test that day-ahead fetch is dispatched when `enable_live_price=True`
- Test that intraday fetch is dispatched when intraday horizon enabled
- Test that accounting fetch uses `Interim, back=48`
- Test energy delta computation (current − previous meter reading)
- Test bidirectional meter mode (same entity for import and export)
- Test export fallback mode (export meter unset, import meter set)
- Test first-poll skips delta (no previous stored)
- Test per-node error isolation
- Test retry/backoff logic

Refactor `coordinator.py`:
- Change per-subentry fetch dispatch to use `subentry.subentry_type == "market_node"`
- Build `NodeData` dict with `day_ahead`, `intraday`, `accounting` keys
- Apply `_convert_price` on all `PriceDetail.price` values at ingest

### Phase 4 — Sensor Entities (test-first)

Write tests for each sensor class in `tests/test_sensor.py` and `tests/test_accounting.py`:
- `LivePriceSensor`: current period detection, RestoreEntity restore, staleness guard, forecast attribute
- `DayAheadForecastSensor`: next period as native_value, forecast list, history retention
- `IntradayForecastSensor`: same as day-ahead but 8 periods
- `SettledPriceSensor`: most recent back=48 entry, history retention
- `ImportCostSensor`: price × import delta, unavailable when meter state unavailable, separate `import_meter_entity_id`
- `ExportRevenueSensor`: price × export delta, separate `export_meter_entity_id`
- `DailyImportCostSensor`: accumulation across periods, midnight NZT reset, RestoreEntity restore, bidirectional mode
- `DailyExportRevenueSensor`: same shape as DailyImportCostSensor

Implement all eight sensor classes in `sensor.py`. Remove the old `PriceSensorEntity` class.

Update `sensor.async_setup_entry` to use new entity creation logic (see sensor-platform contract).

### Phase 5 — Integration Tests

Write `tests/integration/test_multi_node.py`:
- Configure 2 market nodes; verify independent entity sets with correct prefixed IDs
- Modify one node's config; verify the other node is unaffected
- Disable a sensor type; verify its entity is removed
- End-to-end: coordinator fetch → sensor state → HA state machine

### Phase 6 — UI Strings

Update `translations/en.json`:
- Add strings for new subentry form fields (section labels, option descriptions)
- Add error messages: `no_sensor_type_enabled`, `forecast_horizons_empty`, `entity_not_energy_import`, `entity_not_energy_export`
- Remove 002 string keys that no longer exist

---

## Testing Strategy

| Test Type | Location | Credentials | Speed |
|-----------|----------|-------------|-------|
| Unit (mocked) | `tests/test_*.py` | Not needed | Fast (<5s) |
| Integration (mocked) | `tests/integration/` | Not needed | Fast (<10s) |
| Live API | `tests/live/` | Requires `.env` | Slow (network) |

**Mocking pattern** (example coordinator data fixture):
```python
@pytest.fixture
def mock_day_ahead_data():
    return ScheduleDetails(
        schedule="PRSL",
        schedule_name="Price-responsive long schedule",
        prices=[
            PriceDetail(
                trading_datetime=datetime(2026, 5, 20, 2, 0, tzinfo=timezone.utc),
                trading_period=5,
                node="BRB0331",
                price=85.43,   # NZD/MWh — will be converted at ingest
                ...
            ),
            ...
        ]
    )
```

**Live API socket fix**: `tests/live/conftest.py` already handles `pytest-homeassistant-custom-component` socket blocking via `pytest_socket._remove_restrictions()` autouse fixture.

---

## Key Constants Reference

| Constant | Value | Purpose |
|----------|-------|---------|
| `UPDATE_INTERVAL_MINUTES` | `30` | Coordinator poll interval |
| `RETRY_INTERVAL_MINUTES` | `1` | First backoff interval |
| `MAX_RETRIES` | `2` | Retries before marking unavailable |
| `SUBENTRY_TYPE` | `"market_node"` | Config subentry type key |
| `NZD_MWH_TO_C_KWH` | `0.1` | Conversion: NZD/MWh → c/kWh |
| `NZD_MWH_TO_NZD_KWH` | `0.001` | Conversion: NZD/MWh → NZD/kWh |
| `ACCOUNTING_BACK_PERIODS` | `48` | Interim `back=N` for accounting (24h history) |
| `DAY_AHEAD_FORWARD_PERIODS` | `48` | PRSL/NRSL forward periods |
| `INTRADAY_FORWARD_PERIODS` | `8` | PRSS/NRSS forward periods (4h) |

---

## Acceptance Checklist (before merge)

- [ ] `ruff check --fix` passes with 0 errors
- [ ] `mypy custom_components/` passes with 0 errors
- [ ] All unit + integration tests pass (`pytest tests/ -v`)
- [ ] `ConfigFlow.VERSION = 2` and `async_migrate_entry` implemented
- [ ] Migration test covers all 002 schedule type variants
- [ ] `manifest.json` version bumped to 2.0.0
- [ ] `translations/en.json` updated for all new form fields and errors
- [ ] Entity IDs follow `electricityinfo_<entry_id>_<subentry_id>_<sensor_type>` convention
- [ ] No `NZD/MWh` values stored in sensor state (all converted at ingest)
- [ ] `RestoreEntity` used on `LivePriceSensor`, `DailyImportCostSensor`, and `DailyExportRevenueSensor`
- [ ] Staleness guard (30 min) present on `LivePriceSensor.async_added_to_hass` only
- [ ] Daily total sensors reset accumulated total on midnight NZT date advance
- [ ] Two separate energy meter entity selectors (`import_meter_entity_id`, `export_meter_entity_id`) in config flow
- [ ] Bidirectional meter mode active when both fields point to same entity_id
- [ ] Export fallback mode active when `export_meter_entity_id` is unset and `import_meter_entity_id` is set
