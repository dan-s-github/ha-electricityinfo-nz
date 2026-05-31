# Research: RTD-Based Live Price Sensor

**Branch**: `004-rtd-live-price` | **Date**: 2026-05-31

---

## 1. RTD Schedule Identifier

**Decision**: Use `schedule="RTD"` in `get_schedule_prices()`.

**Rationale**:
- `"RTD"` is already defined in the `electricityinfo-nz` library's `schedule_names.py` as `"Real-time dispatch"`.
- It is already listed in `const.py`'s `SCHEDULE_TYPE_OPTIONS` for UI display.
- The existing `get_schedule_prices()` method accepts any valid schedule string; no library changes needed.

**Alternatives considered**:
- Dedicated RTD endpoint (rejected: not exposed; same endpoint handles all schedules)

---

## 2. RTD API Call Parameters

**Decision**: `schedule="RTD"`, `market_type="E"`, `nodes=[node]`, `back=3`, `forward` omitted (None).

**Rationale**:
- `back=3`: Covers last 3 × 30-minute trading periods (~90 min). Guarantees the most recently dispatched RTD period is present even if the poll lands mid-period before the latest dispatch is published. Library validates `1 ≤ back ≤ 48`.
- `forward=None`: RTD is back-looking by definition. The library validates `1 ≤ forward ≤ 48` — zero is invalid — so `forward` must be entirely omitted (not set to 0) for RTD calls.
- `market_type="E"`: Consistent with all existing schedule calls in the integration.

**Alternatives considered**:
- `back=1` (rejected: risk of missing latest dispatch if RTD publication is delayed)
- `back=6` (rejected: fetches 3 hours of unnecessary history)
- `forward=1` (rejected: RTD has no meaningful forward prices; wastes bandwidth)

---

## 3. Live Price / Day-Ahead Fetch Decoupling

**Decision**: The RTD call is always a separate, dedicated API call. The existing PRSL/NRSL day-ahead call is decoupled and now fires only when `enable_forecast=True` and `"day_ahead"` is in `forecast_horizons`.

**Rationale**:
- In 003, the day-ahead PRSL/NRSL call served double duty: live price extraction *and* forecast data. This coupling is eliminated in 004.
- Clean separation: RTD fires when `enable_live_price=True`; day-ahead fires when forecast day-ahead is enabled. When both are enabled, two independent calls are made — no data sharing.
- Eliminates a subtle regression risk: previously, disabling forecast would have broken live price extraction; the new decoupling makes each sensor type independently self-sufficient.

**Impact on coordinator logic**:
```python
# 004 fetch structure (per subentry):
if config.get(CONF_ENABLE_LIVE_PRICE):
    rtd_data = get_schedule_prices(schedule="RTD", back=3, ...)
    node_data["live_current"] = _extract_live_price_payload(rtd_data)

if config.get(CONF_ENABLE_FORECAST) and "day_ahead" in horizons:
    day_ahead = get_schedule_prices(schedule=PRSL/NRSL, forward=48, ...)
    node_data["day_ahead"] = day_ahead

# (intraday and accounting unchanged)
```

**Alternatives considered**:
- RTD replaces day-ahead for live price, PRSL/NRSL still fetched for forecast (rejected: same as chosen approach; wording clarified)
- Share RTD data for both live price and forecast sensors (rejected: RTD has no forward window; forecast sensors require forward periods)

---

## 4. Coordinator Poll Interval

**Decision**: `UPDATE_INTERVAL_MINUTES = 5` (changed from 30). Applied unconditionally to all config entries with any configured market-node subentry.

**Rationale**:
- RTD prices are published approximately every 5 minutes. A 30-minute interval would render RTD data up to 25 minutes stale.
- Unconditional 5-minute interval is simpler than dynamic interval switching (which would require inspecting all subentry configs on every `async_setup_entry` and reacting to subentry add/remove/reconfigure events).
- The increased poll frequency is harmless for forecast and accounting sensors (FR-006, Assumption: "new cadence is harmless for those sensor types").
- On API error, the existing exponential backoff logic (`RETRY_INTERVAL_MINUTES`, `MAX_RETRIES`) already handles graceful degradation; the normal interval of 5 min is restored on recovery (FR-008).

**Alternatives considered**:
- Dynamic interval: 5 min when live price enabled, 30 min otherwise (rejected: complex runtime detection; live price is the primary use case for this integration)

---

## 5. RTD Price Field Selection

**Decision**: Use `PriceDetail.price` (the standard dispatch price field).

**Rationale**:
- `PriceDetail` exposes `price`, `price6s`, and `price60s` for RTD responses. The `price` field is the standard dispatch price consistent with all other schedule types (PRSL, NRSL, Interim).
- The existing `_extract_live_price_payload` already reads `p.price`; no change needed to the extraction logic.
- `price6s` and `price60s` are 6-second and 60-second averages respectively — not the primary dispatch price used for settlement.

**Alternatives considered**:
- `price6s` / `price60s` (rejected: not the primary dispatch price; inconsistent with other sensor types)

---

## 6. Version Bump Strategy

**Decision**: MINOR version bump (e.g. `2.0.0` → `2.1.0`).

**Rationale**:
- No config schema changes; no subentry field additions or removals.
- New behaviour (RTD source, 5-min poll) is additive and non-breaking from a user perspective.
- Constitution Principle V: MAJOR only for breaking changes (config schema, sensor removal, OAuth scope).
- Users will see the `schedule` attribute change from `"PRSL"`/`"NRSL"` to `"RTD"` in HA entity history — this is a data-source transition HA handles naturally; no migration handler required.

**Alternatives considered**:
- MAJOR bump (rejected: no config schema breaks; existing subentry data continues to work without migration)

---

## 7. Test Coverage Strategy

**Decision**: Extend existing `test_coordinator.py` and `conftest.py`; no new test files required.

**Rationale**:
- Add RTD mock fixture (`mock_rtd_response`) alongside existing day-ahead/intraday/accounting fixtures.
- Add test: `enable_live_price=True` → RTD API call made; `node_data["live_current"]` populated with RTD schedule.
- Add test: `enable_live_price=False` → no RTD API call.
- Add test: `enable_live_price=True` + `enable_forecast=True` with day-ahead → two separate API calls made (RTD + PRSL/NRSL).
- Update: any existing assertion that `coordinator.update_interval == timedelta(minutes=30)` → `timedelta(minutes=5)`.
- Update: existing live price tests that assert `schedule="PRSL"` in `live_current` → `schedule="RTD"`.

**Alternatives considered**:
- Separate `test_rtd_live_price.py` (rejected: existing coordinator tests already cover the update cycle; RTD is a new branch in the same flow)
