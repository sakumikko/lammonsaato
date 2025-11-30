#!/usr/bin/env python3
"""
Tests for Home Assistant YAML configuration.

Tests the Jinja2 templates and automation logic outside of HAOS.
Validates that conditions evaluate correctly for various scenarios.

Run with: pytest tests/test_ha_yaml.py -v
"""

import pytest
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
from unittest.mock import MagicMock

# Jinja2 for template testing
try:
    from jinja2 import Environment, BaseLoader, Undefined
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False


# ============================================
# YAML LOADING WITH HA CUSTOM TAGS
# ============================================

def load_ha_yaml(filepath: str) -> dict:
    """Load HA YAML file, handling !secret and !include tags."""

    def secret_constructor(loader, node):
        return f"<secret:{node.value}>"

    def include_constructor(loader, node):
        return f"<include:{node.value}>"

    yaml.add_constructor('!secret', secret_constructor, Loader=yaml.SafeLoader)
    yaml.add_constructor('!include', include_constructor, Loader=yaml.SafeLoader)

    with open(filepath, 'r') as f:
        return yaml.safe_load(f)


# ============================================
# JINJA2 TEMPLATE TESTING HELPERS
# ============================================

class MockHAStates:
    """Mock Home Assistant states for template testing."""

    def __init__(self):
        self._states: Dict[str, Dict[str, Any]] = {}

    def set(self, entity_id: str, state: str, attributes: Dict = None):
        """Set an entity's state."""
        self._states[entity_id] = {
            'state': state,
            'attributes': attributes or {}
        }

    def get(self, entity_id: str) -> str:
        """Get entity state (like states('entity_id'))."""
        if entity_id in self._states:
            return self._states[entity_id]['state']
        return 'unknown'

    def get_attr(self, entity_id: str, attr: str = None):
        """Get entity attributes."""
        if entity_id in self._states:
            attrs = self._states[entity_id]['attributes']
            if attr:
                return attrs.get(attr)
            return attrs
        return {} if attr is None else None


def create_ha_jinja_env(mock_states: MockHAStates) -> 'Environment':
    """Create a Jinja2 environment with HA-like functions."""

    if not JINJA2_AVAILABLE:
        pytest.skip("jinja2 not installed")

    env = Environment(loader=BaseLoader())

    # Add HA-like functions
    env.globals['states'] = mock_states.get
    env.globals['state_attr'] = mock_states.get_attr
    env.globals['is_state'] = lambda e, s: mock_states.get(e) == s
    env.globals['now'] = datetime.now
    env.globals['today_at'] = lambda t: datetime.combine(datetime.now().date(), datetime.strptime(t, '%H:%M').time())
    env.globals['timedelta'] = timedelta

    def as_datetime(val):
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            try:
                return datetime.fromisoformat(val)
            except:
                return datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
        return None

    env.globals['as_datetime'] = as_datetime

    # Add filters
    env.filters['float'] = lambda x, default=0: float(x) if x not in ['unknown', 'unavailable', ''] else default
    env.filters['int'] = lambda x, default=0: int(float(x)) if x not in ['unknown', 'unavailable', ''] else default
    env.filters['round'] = lambda x, p=0: round(x, p)
    env.filters['default'] = lambda x, d: x if x is not None else d

    return env


def eval_template(template_str: str, mock_states: MockHAStates) -> Any:
    """Evaluate a Jinja2 template string with mock states."""
    env = create_ha_jinja_env(mock_states)

    # Clean up HA template syntax for Jinja2
    # HA uses {{ }} for templates, which Jinja2 also uses
    template = env.from_string(template_str)
    result = template.render()

    # Convert string results to appropriate types
    result = result.strip()
    if result.lower() == 'true':
        return True
    elif result.lower() == 'false':
        return False
    elif result == 'unknown':
        return None

    try:
        return float(result)
    except:
        return result


# ============================================
# TEST FIXTURES
# ============================================

@pytest.fixture
def yaml_config():
    """Load the pool_heating.yaml configuration."""
    yaml_path = Path(__file__).parent.parent / 'homeassistant' / 'packages' / 'pool_heating.yaml'
    return load_ha_yaml(str(yaml_path))


@pytest.fixture
def mock_states():
    """Create mock HA states."""
    states = MockHAStates()

    # Set up default states
    states.set('input_boolean.pool_heating_enabled', 'on')
    # Pool heating switches - prevention ON (not heating), circulation OFF
    states.set('switch.altaan_lammityksen_esto', 'on')  # Prevention ON = not heating
    states.set('switch.altaan_kiertovesipumppu', 'off')  # Circulation OFF = not heating
    states.set('sensor.thermia_supply_temperature', '40.5')
    states.set('sensor.thermia_return_temperature', '35.2')
    states.set('sensor.nordpool_kwh_fi_eur_3_10_024', '0.05', {
        'tomorrow_valid': True,
        'today': [0.05] * 96,
        'tomorrow': [0.03] * 96
    })

    return states


# ============================================
# YAML STRUCTURE TESTS
# ============================================

class TestYAMLStructure:
    """Test YAML file structure and required sections."""

    def test_yaml_loads_successfully(self, yaml_config):
        """YAML should load without errors."""
        assert yaml_config is not None

    def test_has_input_boolean(self, yaml_config):
        """Should have input_boolean section."""
        assert 'input_boolean' in yaml_config
        assert 'pool_heating_enabled' in yaml_config['input_boolean']

    def test_has_all_block_datetimes(self, yaml_config):
        """Should have input_datetime for all 4 blocks."""
        assert 'input_datetime' in yaml_config

        for i in range(1, 5):
            assert f'pool_heat_block_{i}_start' in yaml_config['input_datetime']
            assert f'pool_heat_block_{i}_end' in yaml_config['input_datetime']

    def test_has_all_block_prices(self, yaml_config):
        """Should have input_number for all 4 block prices."""
        assert 'input_number' in yaml_config

        for i in range(1, 5):
            assert f'pool_heat_block_{i}_price' in yaml_config['input_number']

    def test_has_automations(self, yaml_config):
        """Should have automation section with start/stop for each block."""
        assert 'automation' in yaml_config

        automation_ids = [a['id'] for a in yaml_config['automation']]

        # Check start automations
        for i in range(1, 5):
            assert f'pool_start_heating_block_{i}' in automation_ids

        # Check stop automations
        for i in range(1, 5):
            assert f'pool_stop_heating_block_{i}' in automation_ids

    def test_has_scripts(self, yaml_config):
        """Should have required scripts."""
        assert 'script' in yaml_config
        assert 'pool_heating_block_start' in yaml_config['script']
        assert 'pool_heating_block_stop' in yaml_config['script']
        assert 'pool_heating_stop' in yaml_config['script']

    def test_automations_have_conditions(self, yaml_config):
        """All start and stop automations should have conditions."""
        for automation in yaml_config['automation']:
            if 'start_heating_block' in automation['id'] or 'stop_heating_block' in automation['id']:
                assert 'condition' in automation, f"Automation {automation['id']} missing conditions"


# ============================================
# TEMPLATE SENSOR TESTS
# ============================================

@pytest.mark.skipif(not JINJA2_AVAILABLE, reason="jinja2 not installed")
class TestTemplateSensors:
    """Test template sensor logic."""

    def test_delta_t_calculation(self, mock_states):
        """Delta-T should be supply - return temperature."""
        template = """
        {% set supply = states('sensor.thermia_supply_temperature') | float(0) %}
        {% set return = states('sensor.thermia_return_temperature') | float(0) %}
        {{ (supply - return) | round(1) }}
        """

        result = eval_template(template, mock_states)
        assert result == 5.3  # 40.5 - 35.2

    def test_delta_t_with_unavailable(self, mock_states):
        """Delta-T should handle unavailable sensors."""
        mock_states.set('sensor.thermia_supply_temperature', 'unavailable')

        template = """
        {% set supply = states('sensor.thermia_supply_temperature') | float(0) %}
        {% set return = states('sensor.thermia_return_temperature') | float(0) %}
        {{ (supply - return) | round(1) }}
        """

        result = eval_template(template, mock_states)
        assert result == -35.2  # 0 - 35.2

    def test_pool_heating_active(self, mock_states):
        """Pool heating active when prevention OFF and circulation ON."""
        template = """{{ is_state('switch.altaan_lammityksen_esto', 'off') and
             is_state('switch.altaan_kiertovesipumppu', 'on') }}"""

        # Default: prevention ON, circulation OFF = not heating
        assert eval_template(template, mock_states) == False

        # Start heating: prevention OFF, circulation ON
        mock_states.set('switch.altaan_lammityksen_esto', 'off')
        mock_states.set('switch.altaan_kiertovesipumppu', 'on')
        assert eval_template(template, mock_states) == True

        # Only prevention OFF but circulation still OFF = not heating
        mock_states.set('switch.altaan_lammityksen_esto', 'off')
        mock_states.set('switch.altaan_kiertovesipumppu', 'off')
        assert eval_template(template, mock_states) == False

    def test_nordpool_tomorrow_available(self, mock_states):
        """Should detect when tomorrow's prices are available."""
        template = "{{ state_attr('sensor.nordpool_kwh_fi_eur_3_10_024', 'tomorrow_valid') | default(false) }}"

        assert eval_template(template, mock_states) == True

        mock_states.set('sensor.nordpool_kwh_fi_eur_3_10_024', '0.05', {'tomorrow_valid': False})
        assert eval_template(template, mock_states) == False


# ============================================
# AUTOMATION CONDITION TESTS
# ============================================

@pytest.mark.skipif(not JINJA2_AVAILABLE, reason="jinja2 not installed")
class TestAutomationConditions:
    """Test automation condition templates."""

    def test_start_condition_valid_block(self, mock_states):
        """Start condition should pass for valid recent block."""
        # Set up a valid block for tonight
        now = datetime.now()
        block_start = now.replace(hour=22, minute=0, second=0, microsecond=0)
        block_end = now.replace(hour=22, minute=30, second=0, microsecond=0)

        mock_states.set('input_datetime.pool_heat_block_1_start', block_start.isoformat())
        mock_states.set('input_datetime.pool_heat_block_1_end', block_end.isoformat())

        template = """
        {% set block_start = as_datetime(states('input_datetime.pool_heat_block_1_start')) %}
        {% set block_end = as_datetime(states('input_datetime.pool_heat_block_1_end')) %}
        {{ block_start.date() >= (now() - timedelta(days=1)).date() and block_end > block_start }}
        """

        assert eval_template(template, mock_states) == True

    def test_start_condition_old_block(self, mock_states):
        """Start condition should fail for old block."""
        # Set up a block from a week ago
        old_date = datetime.now() - timedelta(days=7)
        block_start = old_date.replace(hour=22, minute=0)
        block_end = old_date.replace(hour=22, minute=30)

        mock_states.set('input_datetime.pool_heat_block_1_start', block_start.isoformat())
        mock_states.set('input_datetime.pool_heat_block_1_end', block_end.isoformat())

        template = """
        {% set block_start = as_datetime(states('input_datetime.pool_heat_block_1_start')) %}
        {% set block_end = as_datetime(states('input_datetime.pool_heat_block_1_end')) %}
        {{ block_start.date() >= (now() - timedelta(days=1)).date() and block_end > block_start }}
        """

        assert eval_template(template, mock_states) == False

    def test_stop_condition_valid_block(self, mock_states):
        """Stop condition should pass for valid block (end > start)."""
        now = datetime.now()
        block_start = now.replace(hour=22, minute=0, second=0, microsecond=0)
        block_end = now.replace(hour=22, minute=30, second=0, microsecond=0)

        mock_states.set('input_datetime.pool_heat_block_1_start', block_start.isoformat())
        mock_states.set('input_datetime.pool_heat_block_1_end', block_end.isoformat())

        template = """
        {% set start = as_datetime(states('input_datetime.pool_heat_block_1_start')) %}
        {% set end = as_datetime(states('input_datetime.pool_heat_block_1_end')) %}
        {{ end > start and end.date() >= (now() - timedelta(days=1)).date() }}
        """

        assert eval_template(template, mock_states) == True

    def test_stop_condition_invalid_block_same_time(self, mock_states):
        """Stop condition should fail when start == end (unused block)."""
        now = datetime.now()
        same_time = now.replace(hour=0, minute=0, second=0, microsecond=0)

        mock_states.set('input_datetime.pool_heat_block_4_start', same_time.isoformat())
        mock_states.set('input_datetime.pool_heat_block_4_end', same_time.isoformat())

        template = """
        {% set start = as_datetime(states('input_datetime.pool_heat_block_4_start')) %}
        {% set end = as_datetime(states('input_datetime.pool_heat_block_4_end')) %}
        {{ end > start and end.date() >= (now() - timedelta(days=1)).date() }}
        """

        assert eval_template(template, mock_states) == False

    def test_stop_condition_old_block(self, mock_states):
        """Stop condition should fail for old block dates."""
        old_date = datetime.now() - timedelta(days=7)

        mock_states.set('input_datetime.pool_heat_block_4_start', old_date.isoformat())
        mock_states.set('input_datetime.pool_heat_block_4_end', old_date.isoformat())

        template = """
        {% set start = as_datetime(states('input_datetime.pool_heat_block_4_start')) %}
        {% set end = as_datetime(states('input_datetime.pool_heat_block_4_end')) %}
        {{ end > start and end.date() >= (now() - timedelta(days=1)).date() }}
        """

        assert eval_template(template, mock_states) == False


# ============================================
# SCENARIO TESTS
# ============================================

@pytest.mark.skipif(not JINJA2_AVAILABLE, reason="jinja2 not installed")
class TestScenarios:
    """Test realistic scenarios."""

    def test_scenario_3_blocks_scheduled(self, mock_states):
        """With 3 blocks scheduled, block 4 should not trigger."""
        now = datetime.now()
        today = now.date()

        # Set up 3 valid blocks for tonight
        for i, (start_hour, end_hour) in enumerate([(22, 22.5), (23, 23.75), (0.5, 1.25)], 1):
            if start_hour >= 22:
                start_dt = datetime.combine(today, datetime.min.time().replace(
                    hour=int(start_hour), minute=int((start_hour % 1) * 60)))
            else:
                start_dt = datetime.combine(today + timedelta(days=1), datetime.min.time().replace(
                    hour=int(start_hour), minute=int((start_hour % 1) * 60)))

            if end_hour >= 22:
                end_dt = datetime.combine(today, datetime.min.time().replace(
                    hour=int(end_hour), minute=int((end_hour % 1) * 60)))
            else:
                end_dt = datetime.combine(today + timedelta(days=1), datetime.min.time().replace(
                    hour=int(end_hour), minute=int((end_hour % 1) * 60)))

            mock_states.set(f'input_datetime.pool_heat_block_{i}_start', start_dt.isoformat())
            mock_states.set(f'input_datetime.pool_heat_block_{i}_end', end_dt.isoformat())

        # Block 4 is unused - set to past date with start=end
        past = datetime.combine(today - timedelta(days=7), datetime.min.time())
        mock_states.set('input_datetime.pool_heat_block_4_start', past.isoformat())
        mock_states.set('input_datetime.pool_heat_block_4_end', past.isoformat())

        # Check that blocks 1-3 pass the stop condition
        for i in range(1, 4):
            template = f"""
            {{% set start = as_datetime(states('input_datetime.pool_heat_block_{i}_start')) %}}
            {{% set end = as_datetime(states('input_datetime.pool_heat_block_{i}_end')) %}}
            {{{{ end > start and end.date() >= (now() - timedelta(days=1)).date() }}}}
            """
            assert eval_template(template, mock_states) == True, f"Block {i} should be valid"

        # Block 4 should fail the stop condition
        template = """
        {% set start = as_datetime(states('input_datetime.pool_heat_block_4_start')) %}
        {% set end = as_datetime(states('input_datetime.pool_heat_block_4_end')) %}
        {{ end > start and end.date() >= (now() - timedelta(days=1)).date() }}
        """
        assert eval_template(template, mock_states) == False, "Block 4 should be invalid"

    def test_scenario_heating_disabled(self, mock_states):
        """Heating should not start when master switch is off."""
        mock_states.set('input_boolean.pool_heating_enabled', 'off')

        template = "{{ is_state('input_boolean.pool_heating_enabled', 'on') }}"
        assert eval_template(template, mock_states) == False

    def test_scenario_midnight_block(self, mock_states):
        """Block spanning midnight should work correctly."""
        now = datetime.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)

        # Block from 23:30 today to 00:15 tomorrow
        start_dt = datetime.combine(today, datetime.min.time().replace(hour=23, minute=30))
        end_dt = datetime.combine(tomorrow, datetime.min.time().replace(hour=0, minute=15))

        mock_states.set('input_datetime.pool_heat_block_1_start', start_dt.isoformat())
        mock_states.set('input_datetime.pool_heat_block_1_end', end_dt.isoformat())

        # Should be valid
        template = """
        {% set start = as_datetime(states('input_datetime.pool_heat_block_1_start')) %}
        {% set end = as_datetime(states('input_datetime.pool_heat_block_1_end')) %}
        {{ end > start and end.date() >= (now() - timedelta(days=1)).date() }}
        """
        assert eval_template(template, mock_states) == True


# ============================================
# PRICE CALCULATION TESTS
# ============================================

@pytest.mark.skipif(not JINJA2_AVAILABLE, reason="jinja2 not installed")
class TestPriceCalculations:
    """Test price-related template calculations."""

    def test_average_price_all_blocks(self, mock_states):
        """Should calculate average of all non-zero block prices."""
        mock_states.set('input_number.pool_heat_block_1_price', '3.5')
        mock_states.set('input_number.pool_heat_block_2_price', '4.0')
        mock_states.set('input_number.pool_heat_block_3_price', '2.5')
        mock_states.set('input_number.pool_heat_block_4_price', '0')  # Unused

        template = """
        {% set prices = [
          states('input_number.pool_heat_block_1_price') | float(0),
          states('input_number.pool_heat_block_2_price') | float(0),
          states('input_number.pool_heat_block_3_price') | float(0),
          states('input_number.pool_heat_block_4_price') | float(0)
        ] %}
        {% set valid_prices = prices | select('gt', 0) | list %}
        {% if valid_prices | length > 0 %}
          {{ (valid_prices | sum / valid_prices | length) | round(2) }}
        {% else %}
          0
        {% endif %}
        """

        result = eval_template(template, mock_states)
        expected = (3.5 + 4.0 + 2.5) / 3
        assert abs(result - expected) < 0.01

    def test_average_price_no_blocks(self, mock_states):
        """Should return 0 when no valid prices."""
        for i in range(1, 5):
            mock_states.set(f'input_number.pool_heat_block_{i}_price', '0')

        template = """
        {% set prices = [
          states('input_number.pool_heat_block_1_price') | float(0),
          states('input_number.pool_heat_block_2_price') | float(0),
          states('input_number.pool_heat_block_3_price') | float(0),
          states('input_number.pool_heat_block_4_price') | float(0)
        ] %}
        {% set valid_prices = prices | select('gt', 0) | list %}
        {% if valid_prices | length > 0 %}
          {{ (valid_prices | sum / valid_prices | length) | round(2) }}
        {% else %}
          0
        {% endif %}
        """

        assert eval_template(template, mock_states) == 0


# ============================================
# RUN TESTS
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
