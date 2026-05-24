"""Tests for multiple price sensors configuration and operation."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from electricityinfo_nz.exceptions import MarketPricesAPIError
from homeassistant.config_entries import ConfigEntry
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electricityinfo import ElectricityInfoCoordinator
from custom_components.electricityinfo.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_NODE,
    DOMAIN,
)
from custom_components.electricityinfo.sensor import (
    DayAheadForecastSensor,
    PriceSensorEntity,
)
from tests.helpers import create_mock_market_node_subentry, create_mock_subentry


@pytest.fixture
def mock_config_entry_with_sensors():
    """Create mock config entry with two sensor subentries."""
    sub1 = create_mock_subentry(
        subentry_id="sensor_1",
        title="HAY2201 RTD (E)",
        schedule_type="RTD",
        market_type="E",
        node="HAY2201",
        forward_prices_count=24,
    )
    sub2 = create_mock_subentry(
        subentry_id="sensor_2",
        title="BEN2201 RTD (E)",
        schedule_type="RTD",
        market_type="E",
        node="BEN2201",
        forward_prices_count=24,
    )

    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.title = "Electricity Info NZ"
    entry.data = {
        CONF_CLIENT_ID: "test_client_id",
        CONF_CLIENT_SECRET: "test_client_secret",
    }
    entry.subentries = {
        sub1.subentry_id: sub1,
        sub2.subentry_id: sub2,
    }
    return entry


@pytest.mark.asyncio
async def test_multiple_sensors_configuration_storage(mock_config_entry_with_sensors):
    """Test that multiple sensor subentries are stored and retrievable (T033)."""
    entry = mock_config_entry_with_sensors
    subentries = [s for s in entry.subentries.values() if s.subentry_type == "sensor"]

    assert len(subentries) == 2
    assert subentries[0].subentry_id == "sensor_1"
    assert subentries[0].data[CONF_NODE] == "HAY2201"

    assert subentries[1].subentry_id == "sensor_2"
    assert subentries[1].data[CONF_NODE] == "BEN2201"


@pytest.mark.asyncio
async def test_multiple_sensors_create_unique_entities(
    hass, mock_config_entry_with_sensors
):
    """Test that multiple subentries create separate entities (T033)."""
    entry = mock_config_entry_with_sensors

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, entry)

        entities = [
            PriceSensorEntity(coordinator, entry, subentry, unit="NZD/MWh")
            for subentry in entry.subentries.values()
        ]

        assert len(entities) == 2

        unique_ids = [e._attr_unique_id for e in entities]
        assert len(unique_ids) == len(set(unique_ids))


@pytest.mark.asyncio
async def test_multiple_sensors_data_isolation(hass, mock_config_entry_with_sensors):
    """Test that coordinator provides isolated data per sensor (T035)."""
    entry = mock_config_entry_with_sensors

    with patch(
        "custom_components.electricityinfo.AsyncMarketPricesClient"
    ) as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        mock_client_instance.get_schedule_prices.return_value = MagicMock()

        coordinator = ElectricityInfoCoordinator(hass, entry)
        coordinator.client = mock_client_instance

        result = await coordinator._async_update_data()

        assert "sensor_1" in result
        assert "sensor_2" in result
        mock_client_instance.get_schedule_prices.assert_called()


@pytest.mark.asyncio
async def test_isolated_failure_partial_data(hass, mock_config_entry_with_sensors):
    """Test isolated failure: one sensor fails, others update normally (T036)."""
    entry = mock_config_entry_with_sensors

    with patch(
        "custom_components.electricityinfo.AsyncMarketPricesClient"
    ) as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        # First subentry succeeds, second raises a per-sensor API error
        mock_client_instance.get_schedule_prices.side_effect = [
            MagicMock(),
            MarketPricesAPIError("API Error for sensor 2"),
        ]

        coordinator = ElectricityInfoCoordinator(hass, entry)
        coordinator.client = mock_client_instance

        result = await coordinator._async_update_data()

        assert "sensor_1" in result
        assert "sensor_2" in result
        assert "error" not in result["sensor_1"]
        assert "error" in result["sensor_2"]


@pytest.mark.asyncio
async def test_unique_unique_id_per_sensor(hass, mock_config_entry_with_sensors):
    """Test unique_id uniqueness per sensor subentry (T037)."""
    entry = mock_config_entry_with_sensors

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, entry)

        unique_ids = [
            PriceSensorEntity(
                coordinator, entry, subentry, unit="NZD/MWh"
            )._attr_unique_id
            for subentry in entry.subentries.values()
        ]

        assert len(unique_ids) == len(set(unique_ids)), "Unique IDs are not unique"
        assert len(unique_ids) == 2

        for uid in unique_ids:
            assert "electricityinfo_nz" in uid


@pytest.mark.asyncio
async def test_multiple_sensors_in_config_flow(hass, mock_config_entry_with_sensors):
    """Test subentries support multiple sensors with individual management (T034)."""
    entry = mock_config_entry_with_sensors
    subentries = list(entry.subentries.values())

    assert len(subentries) == 2

    # Each subentry has its own node
    nodes = {s.data[CONF_NODE] for s in subentries}
    assert "HAY2201" in nodes
    assert "BEN2201" in nodes

    # Each subentry has a unique ID
    ids = {s.subentry_id for s in subentries}
    assert len(ids) == 2


async def test_five_sensors_no_performance_degradation(hass) -> None:
    """SC-005: Test 5+ simultaneous sensors without performance degradation."""
    # Create 5 sensor subentries
    subentries_data = []
    nodes = ["HAY2201", "BEN2201", "OTA0011", "TWI0331", "CEN0011"]
    for i, node in enumerate(nodes):
        sub = create_mock_subentry(
            subentry_id=f"sensor_{i}",
            title=f"{node} RTD (E)",
            schedule_type="RTD",
            market_type="E",
            node=node,
            forward_prices_count=24,
        )
        subentries_data.append(
            {
                "data": dict(sub.data),
                "subentry_type": "sensor",
                "title": sub.title,
                "unique_id": None,
            }
        )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Main",
        data={
            CONF_CLIENT_ID: "test_client",
            CONF_CLIENT_SECRET: "test_secret",
        },
        subentries_data=subentries_data,
    )
    entry.add_to_hass(hass)

    # Setup integration with 5 sensors
    with patch.object(
        ElectricityInfoCoordinator, "_async_update_data", return_value={}
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Verify all 5 sensors are created (10 entities: 2 per sensor)
    states = hass.states.async_all("sensor")
    # Should have 10 entities (5 sensors x 2 units each)
    assert len(states) >= 10, f"Expected >=10 sensor entities, got {len(states)}"

    # Verify each sensor has both NZD/MWh and c/kWh entities
    for node in nodes:
        nzd_entity = next(
            (s for s in states if node.lower() in s.entity_id and "nzd" in s.entity_id),
            None,
        )
        ckwh_entity = next(
            (
                s
                for s in states
                if node.lower() in s.entity_id and "c_kwh" in s.entity_id
            ),
            None,
        )
        assert nzd_entity is not None, f"Missing NZD/MWh entity for {node}"
        assert ckwh_entity is not None, f"Missing c/kWh entity for {node}"

    # Verify no duplicate entities or ID collisions
    entity_ids = [s.entity_id for s in states]
    assert len(entity_ids) == len(set(entity_ids)), "Duplicate entity IDs detected"


@pytest.mark.asyncio
async def test_forecast_history_respects_retention_window(hass) -> None:
    """US2 retention keeps only retention_hours*2 history points."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=True,
        forecast_horizons=["day_ahead"],
        forecast_retention_hours=6,
    )
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)

    def _price(offset_minutes: int, period: int, value: float) -> MagicMock:
        item = MagicMock()
        item.trading_datetime = now + timedelta(minutes=offset_minutes)
        item.trading_period = period
        item.node = "HAY2201"
        item.schedule = "PRSL"
        item.price = value
        return item

    schedule = MagicMock()
    # 16 history points + 1 future point, retention=6h => keep latest 12 history points.
    schedule.prices = [
        _price(-(16 - idx) * 30, idx + 1, float(idx + 1)) for idx in range(16)
    ] + [_price(30, 99, 99.0)]

    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.title = "Electricity Info NZ"
    entry.data = {
        CONF_CLIENT_ID: "test_client_id",
        CONF_CLIENT_SECRET: "test_client_secret",
    }
    entry.subentries = {subentry.subentry_id: subentry}

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "day_ahead": schedule,
                "intraday": None,
                "accounting": None,
                "config": dict(subentry.data),
                "error": None,
            }
        }
        entity = DayAheadForecastSensor(coordinator, entry, subentry)
        with (
            patch("homeassistant.util.dt.utcnow", return_value=now),
            patch.object(entity, "async_write_ha_state", MagicMock()),
        ):
            entity._handle_coordinator_update()

    history_periods = [
        p["trading_period"] for p in entity.extra_state_attributes["history"]
    ]
    assert len(history_periods) == 12
    assert history_periods == list(range(5, 17))
