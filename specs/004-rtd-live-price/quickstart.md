# Quickstart: RTD-Based Live Price Sensor

**Branch**: `004-rtd-live-price` | **Date**: 2026-05-31

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

### Phase 1 — Constants (no tests yet)

Update `custom_components/electricityinfo/const.py`:

- Change `UPDATE_INTERVAL_MINUTES = 30` → `UPDATE_INTERVAL_MINUTES = 5`
- Add `RTD_BACK_PERIODS = 3`

Export `RTD_BACK_PERIODS` from `const.py` (add to `__all__` if used, or just ensure it is importable).

---

### Phase 2 — Coordinator refactor (test-first)

Write tests **before** modifying `coordinator.py`:

**In `tests/conftest.py`**:
- Add `mock_rtd_response` fixture: a `ScheduleDetails` object with `schedule="RTD"` and 3–4 `PriceDetail` entries spanning the last 90 minutes, with `price` values set (not `price6s`/`price60s`).

**In `tests/test_coordinator.py`** (add new test cases):
- `test_live_price_fetches_rtd`: given `enable_live_price=True`, assert `get_schedule_prices` is called with `schedule="RTD"`, `back=3`, and no `forward` kwarg; assert `node_data["live_current"]["schedule"] == "RTD"`.
- `test_live_price_disabled_no_rtd_call`: given `enable_live_price=False`, assert no call with `schedule="RTD"` is made.
- `test_live_price_and_forecast_day_ahead_two_calls`: given `enable_live_price=True` and `enable_forecast=True` with `forecast_horizons=["day_ahead"]`, assert two separate `get_schedule_prices` calls are made — one with `schedule="RTD"` and one with `schedule="PRSL"` (or `"NRSL"`).
- `test_coordinator_interval_is_5_minutes`: assert `coordinator.update_interval == timedelta(minutes=5)`.

**Update existing tests**:
- Any assertion `coordinator.update_interval == timedelta(minutes=30)` → `timedelta(minutes=5)`.
- Any assertion that `live_current["schedule"] == "PRSL"` or `"NRSL"` → `"RTD"`.
- If the day-ahead fixture was returned for live price extraction, update the test setup so live price uses the RTD fixture instead.

**Then implement in `coordinator.py`**:
1. Import `RTD_BACK_PERIODS` from `.const`.
2. Replace the existing `if config.get(CONF_ENABLE_LIVE_PRICE) or (...)` block:
   - New separate block: `if config.get(CONF_ENABLE_LIVE_PRICE):` → RTD fetch → `node_data["live_current"]`.
   - Day-ahead block: `if config.get(CONF_ENABLE_FORECAST) and "day_ahead" in horizons:` → PRSL/NRSL fetch → `node_data["day_ahead"]`.
3. Remove the `or config.get(CONF_ENABLE_LIVE_PRICE)` condition from the day-ahead fetch guard.
4. `_extract_live_price_payload` is unchanged — it already handles any `ScheduleDetails` input.

---

### Phase 3 — Version bump & validation

Update `custom_components/electricityinfo/manifest.json`:
- Bump `version` field: MINOR increment (e.g. `"2.0.0"` → `"2.1.0"`).

Run full validation:

```bash
pytest tests/ -v           # All tests green
ruff check custom_components/ tests/   # No lint errors
mypy custom_components/    # No type errors
```

---

## Key Design Invariants

- `RTD_BACK_PERIODS = 3` is a constant — do not inline the literal `3` in `coordinator.py`.
- `forward` is **never passed** to the RTD `get_schedule_prices` call (omit, do not pass `None` explicitly or `0`).
- The `_extract_live_price_payload` function is **reused unchanged** — it is schedule-agnostic.
- The `day_ahead` coordinator key is now **forecast-only**. Do not read it for live price anywhere.
- The `live_current` dict structure (`timestamp`, `trading_period`, `node`, `schedule`, `price`) is **unchanged** — sensors read it identically.
