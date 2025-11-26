"""
Pytest configuration and fixtures for pool heating tests.
"""

import pytest
import json
from pathlib import Path
from datetime import date, datetime, timedelta


@pytest.fixture
def mock_prices_path():
    """Path to mock price data."""
    return Path(__file__).parent / "mock_data" / "sample_prices.json"


@pytest.fixture
def mock_prices(mock_prices_path):
    """Load mock price data."""
    with open(mock_prices_path) as f:
        return json.load(f)


@pytest.fixture
def typical_winter_prices(mock_prices):
    """Typical winter night pricing scenario."""
    scenario = mock_prices["scenarios"]["typical_winter_night"]
    return {
        "today": scenario["today"],
        "tomorrow": scenario["tomorrow"]
    }


@pytest.fixture
def negative_prices(mock_prices):
    """Negative price scenario (high renewable generation)."""
    scenario = mock_prices["scenarios"]["negative_prices"]
    return {
        "today": scenario["today"],
        "tomorrow": scenario["tomorrow"]
    }


@pytest.fixture
def flat_prices(mock_prices):
    """Flat pricing scenario."""
    scenario = mock_prices["scenarios"]["flat_prices"]
    return {
        "today": scenario["today"],
        "tomorrow": scenario["tomorrow"]
    }


@pytest.fixture
def today():
    """Current date."""
    return date.today()


@pytest.fixture
def tomorrow(today):
    """Tomorrow's date."""
    return today + timedelta(days=1)


@pytest.fixture
def mock_heating_session():
    """Sample heating session data."""
    return {
        'start_time': datetime.now().isoformat(),
        'end_time': (datetime.now() + timedelta(hours=1)).isoformat(),
        'duration_hours': 1.0,
        'electricity_price': 0.0523,
        'start_supply_temp': 45.2,
        'start_return_temp': 38.1,
        'end_supply_temp': 44.8,
        'end_return_temp': 37.9,
        'avg_delta_t': 7.0,
        'pool_temp_before': 28.5,
        'pool_temp_after': 29.1,
        'pool_temp_change': 0.6,
        'estimated_kwh': 3.5,
        'temperature_readings': [
            {'timestamp': datetime.now().isoformat(), 'supply_temp': 45.2, 'return_temp': 38.1, 'delta_t': 7.1},
            {'timestamp': (datetime.now() + timedelta(minutes=5)).isoformat(), 'supply_temp': 45.0, 'return_temp': 38.0, 'delta_t': 7.0},
        ]
    }


class MockHomeAssistant:
    """Mock Home Assistant state for testing."""

    def __init__(self):
        self.states = {}
        self.attributes = {}

    def set_state(self, entity_id, state, attributes=None):
        self.states[entity_id] = state
        if attributes:
            self.attributes[entity_id] = attributes

    def get_state(self, entity_id):
        return self.states.get(entity_id)

    def get_attributes(self, entity_id):
        return self.attributes.get(entity_id, {})


@pytest.fixture
def mock_ha():
    """Mock Home Assistant instance."""
    ha = MockHomeAssistant()

    # Set up default states
    ha.set_state('sensor.thermia_supply_temperature', '45.2')
    ha.set_state('sensor.thermia_return_temperature', '38.1')
    ha.set_state('sensor.nordpool_kwh_fi_eur_3_10_024', '0.0523', {
        'today': [0.05] * 24,
        'tomorrow': [0.03] * 24,
        'tomorrow_valid': True
    })
    ha.set_state('switch.shelly_pool_heating', 'off')
    ha.set_state('input_boolean.pool_heating_enabled', 'on')

    return ha
