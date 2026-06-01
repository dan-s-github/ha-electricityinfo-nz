"""Tests for accounting sensor entities (US3)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from electricityinfo_nz.exceptions import MarketPricesAPIError
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed

from custom_components.electricityinfo.coordinator import ElectricityInfoCoordinator
from custom_components.electricityinfo.sensor import (
    DailyExportRevenueSensor,
    DailyImportCostSensor,
    ExportRevenueSensor,
    ImportCostSensor,
    PreviousDayExportRevenueSensor,
    PreviousDayImportCostSensor,
    SettledPriceSensor,
)
from tests.helpers import create_mock_market_node_subentry


def _make_accounting_schedule(prices: list[tuple[datetime, int, float]]) -> MagicMock:
    """Create accounting schedule object from datetime/period/price tuples."""
    schedule = MagicMock()
    schedule.prices = []
    for dt_val, period, price in prices:
        row = MagicMock()
        row.trading_datetime = dt_val
        row.trading_period = period
        row.node = "HAY2201"
        row.schedule = "Interim"
        row.price = price
        schedule.prices.append(row)
    return schedule


async def test_settled_price_sensor_uses_latest_and_history_retention(
    hass, mock_entry
) -> None:
    """Settled sensor chooses latest settled point and exposes retained history."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=False,
        enable_accounting=True,
        accounting_retention_hours=24,
    )
    t1 = datetime(2026, 5, 24, 9, 0, tzinfo=UTC)
    t2 = datetime(2026, 5, 24, 9, 30, tzinfo=UTC)
    schedule = _make_accounting_schedule([(t1, 19, 0.23), (t2, 20, 0.25)])

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "accounting": schedule,
                "settled_price": 0.25,
                "settled_timestamp": t2,
                "settled_trading_period": 20,
                "config": dict(subentry.data),
                "error": None,
            }
        }
        entity = SettledPriceSensor(coordinator, mock_entry, subentry)
        with patch.object(entity, "async_write_ha_state", MagicMock()):
            entity._handle_coordinator_update()

    assert entity.native_value == pytest.approx(0.25, abs=1e-6)
    attrs = entity.extra_state_attributes
    assert attrs["trading_period"] == 20
    assert len(attrs["history"]) == 2


async def test_settled_price_sensor_uses_current_period_and_excludes_from_history(
    hass, mock_entry
) -> None:
    """Settled state uses current period; history includes only completed periods."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=False,
        enable_accounting=True,
        accounting_retention_hours=24,
    )
    current_start = datetime(2026, 5, 24, 9, 30, tzinfo=UTC)
    now = current_start + timedelta(minutes=10)
    t_prev = current_start - timedelta(minutes=30)
    t_next = current_start + timedelta(minutes=30)
    schedule = _make_accounting_schedule(
        [(t_prev, 19, 0.23), (current_start, 20, 0.25), (t_next, 21, 0.27)]
    )

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "accounting": schedule,
                "config": dict(subentry.data),
                "error": None,
            }
        }
        entity = SettledPriceSensor(coordinator, mock_entry, subentry)
        with (
            patch("homeassistant.util.dt.utcnow", return_value=now),
            patch.object(entity, "async_write_ha_state", MagicMock()),
        ):
            entity._handle_coordinator_update()

    assert entity.native_value == pytest.approx(0.25, abs=1e-6)
    attrs = entity.extra_state_attributes
    assert attrs["trading_period"] == 20
    assert [p["trading_period"] for p in attrs["history"]] == [19]


async def test_import_and_export_sensors_use_coordinator_deltas(
    hass, mock_entry
) -> None:
    """Import/export sensors expose computed value and meter attrs."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=False,
        enable_accounting=True,
        import_meter_entity_id="sensor.import_meter",
        export_meter_entity_id="sensor.export_meter",
    )
    settled_time = datetime(2026, 5, 24, 9, 30, tzinfo=UTC)
    node_data = {
        "settled_price": 0.30,
        "settled_timestamp": settled_time,
        "settled_trading_period": 20,
        "import_energy_delta": 1.2,
        "export_energy_delta": 0.5,
        "import_cost_delta": 0.36,
        "export_revenue_delta": 0.15,
        "config": dict(subentry.data),
        "error": None,
    }

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {subentry.subentry_id: node_data}
        import_entity = ImportCostSensor(coordinator, mock_entry, subentry)
        export_entity = ExportRevenueSensor(coordinator, mock_entry, subentry)
        with (
            patch.object(import_entity, "async_write_ha_state", MagicMock()),
            patch.object(export_entity, "async_write_ha_state", MagicMock()),
        ):
            import_entity._handle_coordinator_update()
            export_entity._handle_coordinator_update()

    assert import_entity.native_value == pytest.approx(0.36, abs=1e-6)
    assert export_entity.native_value == pytest.approx(0.15, abs=1e-6)
    assert import_entity.extra_state_attributes["energy_kwh"] == pytest.approx(
        1.2, abs=1e-6
    )
    assert export_entity.extra_state_attributes["energy_kwh"] == pytest.approx(
        0.5, abs=1e-6
    )


async def test_daily_import_cost_restore_and_date_reset(hass, mock_entry) -> None:
    """Daily import sensor restores and resets when accounting day advances."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=False,
        enable_accounting=True,
        import_meter_entity_id="sensor.import_meter",
    )

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {}
        entity = DailyImportCostSensor(coordinator, mock_entry, subentry)

        restored = MagicMock()
        restored.state = "1.5"
        restored.attributes = {"accumulation_date": "2026-05-24"}
        with (
            patch.object(CoordinatorEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                entity,
                "async_get_last_state",
                AsyncMock(return_value=restored),
            ),
        ):
            await entity.async_added_to_hass()

        coordinator.data = {
            subentry.subentry_id: {
                "accounting_date_nzt": date(2026, 5, 25),
                "import_cost_delta": 0.4,
                "config": dict(subentry.data),
                "error": None,
            }
        }
        with patch.object(entity, "async_write_ha_state", MagicMock()):
            entity._handle_coordinator_update()

    assert entity.native_value == pytest.approx(0.4, abs=1e-6)
    assert entity.extra_state_attributes["accumulation_date"] == "2026-05-25"


async def test_daily_export_revenue_accumulates(hass, mock_entry) -> None:
    """Daily export revenue accumulates deltas across updates."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=False,
        enable_accounting=True,
        import_meter_entity_id="sensor.grid_meter",
        export_meter_entity_id="sensor.grid_meter",
    )

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        entity = DailyExportRevenueSensor(coordinator, mock_entry, subentry)
        entity._accumulation_date = date(2026, 5, 24)

        coordinator.data = {
            subentry.subentry_id: {
                "accounting_date_nzt": date(2026, 5, 24),
                "export_revenue_delta": 0.2,
                "config": dict(subentry.data),
                "error": None,
            }
        }
        with patch.object(entity, "async_write_ha_state", MagicMock()):
            entity._handle_coordinator_update()

        coordinator.data[subentry.subentry_id]["export_revenue_delta"] = 0.1
        with patch.object(entity, "async_write_ha_state", MagicMock()):
            entity._handle_coordinator_update()

    assert entity.native_value == pytest.approx(0.3, abs=1e-6)


async def test_coordinator_live_routing_and_c_kwh_conversion(hass, mock_entry) -> None:
    """Coordinator routes live fetch to RTD and converts at ingest."""
    subentry = create_mock_market_node_subentry(
        subentry_id="market_node_1",
        node="HAY2201",
        price_unit="c/kWh",
        enable_live_price=True,
        enable_forecast=False,
        enable_accounting=False,
    )
    mock_entry.subentries = {subentry.subentry_id: subentry}
    coordinator = ElectricityInfoCoordinator(hass, mock_entry)

    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    mock_schedule = SimpleNamespace(
        prices=[
            SimpleNamespace(
                trading_datetime=now,
                trading_period=24,
                node="HAY2201",
                price=100.0,
                schedule="RTD",
                run_type="A",
            )
        ]
    )

    client = AsyncMock()
    client.get_schedule_prices.return_value = mock_schedule
    coordinator.client = client
    data = await coordinator._async_update_data()

    kwargs = client.get_schedule_prices.call_args.kwargs
    assert kwargs["schedule"] == "RTD"
    assert "forward" not in kwargs
    assert data[subentry.subentry_id]["live_current"]["schedule"] == "RTD"
    assert data[subentry.subentry_id]["live_current"]["price"] == pytest.approx(10.0)


async def test_coordinator_retry_backoff_on_client_error(hass, mock_entry) -> None:
    """Coordinator applies retry backoff interval after client-level errors."""
    subentry = create_mock_market_node_subentry(
        subentry_id="market_node_1",
        node="HAY2201",
        price_unit="NZD/kWh",
        enable_live_price=True,
        enable_forecast=False,
        enable_accounting=False,
    )
    mock_entry.subentries = {subentry.subentry_id: subentry}
    coordinator = ElectricityInfoCoordinator(hass, mock_entry)

    with (
        patch.object(
            coordinator, "_ensure_client", side_effect=MarketPricesAPIError("boom")
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()

    assert coordinator._retry_count == 1
    assert coordinator.update_interval == timedelta(minutes=1)


# ── Phase 5: Previous-day sensor tests ──────────────────────────────────────


async def test_daily_sensor_snapshots_previous_day_on_rollover(
    hass, mock_entry
) -> None:
    """Daily sensor saves previous-day snapshot when accounting date rolls over."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=False,
        enable_accounting=True,
        import_meter_entity_id="sensor.import_meter",
    )

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        entity = DailyImportCostSensor(coordinator, mock_entry, subentry)
        entity._accumulation_date = date(2026, 5, 24)
        entity._accumulated_total = 1.5
        entity.previous_day_total = None

        coordinator.data = {
            subentry.subentry_id: {
                "accounting_date_nzt": date(2026, 5, 25),
                "import_cost_delta": 0.3,
                "config": dict(subentry.data),
                "error": None,
            }
        }
        with patch.object(entity, "async_write_ha_state", MagicMock()):
            entity._handle_coordinator_update()

    assert entity.previous_day_total == pytest.approx(1.5, abs=1e-9)
    assert entity._accumulated_total == pytest.approx(0.3, abs=1e-9)
    assert entity._accumulation_date == date(2026, 5, 25)


async def test_daily_sensor_no_snapshot_before_first_rollover(hass, mock_entry) -> None:
    """Daily sensor has no previous_day_total until the first day rollover."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=False,
        enable_accounting=True,
        import_meter_entity_id="sensor.import_meter",
    )

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        entity = DailyImportCostSensor(coordinator, mock_entry, subentry)
        entity._accumulation_date = date(2026, 5, 24)

        coordinator.data = {
            subentry.subentry_id: {
                "accounting_date_nzt": date(2026, 5, 24),
                "import_cost_delta": 0.5,
                "config": dict(subentry.data),
                "error": None,
            }
        }
        with patch.object(entity, "async_write_ha_state", MagicMock()):
            entity._handle_coordinator_update()

    assert entity.previous_day_total is None
    assert entity.extra_state_attributes.get("previous_day_total") is None


async def test_daily_sensor_previous_day_persisted_in_attributes(
    hass, mock_entry
) -> None:
    """previous_day_total appears in extra_state_attributes after rollover."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=False,
        enable_accounting=True,
        import_meter_entity_id="sensor.import_meter",
    )

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        entity = DailyImportCostSensor(coordinator, mock_entry, subentry)
        entity._accumulation_date = date(2026, 5, 24)
        entity._accumulated_total = 2.0

        coordinator.data = {
            subentry.subentry_id: {
                "accounting_date_nzt": date(2026, 5, 25),
                "import_cost_delta": 0.1,
                "config": dict(subentry.data),
                "error": None,
            }
        }
        with patch.object(entity, "async_write_ha_state", MagicMock()):
            entity._handle_coordinator_update()

    attrs = entity.extra_state_attributes
    assert attrs.get("previous_day_total") == pytest.approx(2.0, abs=1e-9)


async def test_daily_import_restore_restores_previous_day_total(
    hass, mock_entry
) -> None:
    """RestoreEntity restores previous_day_total from last state attributes."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=False,
        enable_accounting=True,
        import_meter_entity_id="sensor.import_meter",
    )

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {}
        entity = DailyImportCostSensor(coordinator, mock_entry, subentry)

        restored = MagicMock()
        restored.state = "1.5"
        restored.attributes = {
            "accumulation_date": "2026-05-25",
            "previous_day_total": "1.2",
        }
        with (
            patch.object(CoordinatorEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                entity, "async_get_last_state", AsyncMock(return_value=restored)
            ),
        ):
            await entity.async_added_to_hass()

    assert entity.previous_day_total == pytest.approx(1.2, abs=1e-9)


async def test_previous_day_import_cost_reflects_daily_snapshot(
    hass, mock_entry
) -> None:
    """PreviousDayImportCostSensor reads previous_day_total from its daily sensor."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=False,
        enable_accounting=True,
        import_meter_entity_id="sensor.import_meter",
    )

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        daily = DailyImportCostSensor(coordinator, mock_entry, subentry)
        daily.previous_day_total = 3.5
        prev_day = PreviousDayImportCostSensor(
            coordinator, mock_entry, subentry, daily_sensor=daily
        )
        prev_day._native_value = 0.0

        with patch.object(prev_day, "async_write_ha_state", MagicMock()):
            prev_day._handle_coordinator_update()

    assert prev_day.native_value == pytest.approx(3.5, abs=1e-9)


async def test_previous_day_export_revenue_reflects_daily_snapshot(
    hass, mock_entry
) -> None:
    """PreviousDayExportRevenueSensor reads previous_day_total from its daily sensor."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=False,
        enable_accounting=True,
        export_meter_entity_id="sensor.export_meter",
    )

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        daily = DailyExportRevenueSensor(coordinator, mock_entry, subentry)
        daily.previous_day_total = 1.8
        prev_day = PreviousDayExportRevenueSensor(
            coordinator, mock_entry, subentry, daily_sensor=daily
        )
        prev_day._native_value = 0.0

        with patch.object(prev_day, "async_write_ha_state", MagicMock()):
            prev_day._handle_coordinator_update()

    assert prev_day.native_value == pytest.approx(1.8, abs=1e-9)


async def test_previous_day_sensor_seeds_daily_if_no_prior_restore(
    hass, mock_entry
) -> None:
    """PreviousDay sensor seeds daily sensor's previous_day_total if daily has none."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=False,
        enable_accounting=True,
        import_meter_entity_id="sensor.import_meter",
    )

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        daily = DailyImportCostSensor(coordinator, mock_entry, subentry)
        daily.previous_day_total = None
        prev_day = PreviousDayImportCostSensor(
            coordinator, mock_entry, subentry, daily_sensor=daily
        )

        restored = MagicMock()
        restored.state = "2.7"
        restored.attributes = {}
        with (
            patch.object(CoordinatorEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                prev_day, "async_get_last_state", AsyncMock(return_value=restored)
            ),
        ):
            await prev_day.async_added_to_hass()

    assert daily.previous_day_total == pytest.approx(2.7, abs=1e-9)
    assert prev_day.native_value == pytest.approx(2.7, abs=1e-9)


async def test_previous_day_sensor_does_not_overwrite_daily_restored_value(
    hass, mock_entry
) -> None:
    """PreviousDay sensor does not overwrite previous_day_total from daily."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=False,
        enable_accounting=True,
        import_meter_entity_id="sensor.import_meter",
    )

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        daily = DailyImportCostSensor(coordinator, mock_entry, subentry)
        daily.previous_day_total = 5.0
        prev_day = PreviousDayImportCostSensor(
            coordinator, mock_entry, subentry, daily_sensor=daily
        )

        restored = MagicMock()
        restored.state = "9.9"
        restored.attributes = {}
        with (
            patch.object(CoordinatorEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                prev_day, "async_get_last_state", AsyncMock(return_value=restored)
            ),
        ):
            await prev_day.async_added_to_hass()

    assert daily.previous_day_total == pytest.approx(5.0, abs=1e-9)


async def test_previous_day_sensor_unavailable_before_first_rollover(
    hass, mock_entry
) -> None:
    """PreviousDay sensor native_value is None until first rollover occurs."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=False,
        enable_accounting=True,
        import_meter_entity_id="sensor.import_meter",
    )

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        daily = DailyImportCostSensor(coordinator, mock_entry, subentry)
        daily.previous_day_total = None
        prev_day = PreviousDayImportCostSensor(
            coordinator, mock_entry, subentry, daily_sensor=daily
        )

        with (
            patch.object(CoordinatorEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                prev_day, "async_get_last_state", AsyncMock(return_value=None)
            ),
        ):
            await prev_day.async_added_to_hass()

    assert prev_day.native_value is None


# ── Phase 6: SC-005 API error path ──────────────────────────────────────────


async def test_settled_price_none_when_only_future_periods_present(
    hass, mock_entry
) -> None:
    """settled_price not set when all accounting periods are in the future."""
    future_time = datetime.now(UTC) + timedelta(hours=1)
    schedule = _make_accounting_schedule([(future_time, 50, 0.30)])

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        node_data: dict = {"accounting": schedule}
        coordinator._populate_accounting_metrics(
            subentry_id="market_node_1",
            config={
                "import_meter_entity_id": None,
                "export_meter_entity_id": None,
            },
            node_data=node_data,
        )

    assert node_data.get("settled_price") is None
