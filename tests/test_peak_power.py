#!/usr/bin/env python3
"""
Tests for Peak Power Avoidance configuration.

Tests the peak_power.yaml Home Assistant package that adjusts
Thermia heat pump additional heater settings to avoid Helen peak power costs.

Peak hours: 7:00-21:00
Daytime settings (6:40-21:00): start=-10, stop=0 (effectively disables additional heater)
Nighttime settings (21:00-6:40): start=-6, stop=4 (normal operation)

All settings are now configurable via input_number and input_datetime entities.

Run with: pytest tests/test_peak_power.py -v
"""

import pytest
import yaml
from pathlib import Path


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


@pytest.fixture
def peak_power_config():
    """Load the peak_power.yaml configuration."""
    yaml_path = Path(__file__).parent.parent / 'homeassistant' / 'packages' / 'peak_power.yaml'
    return load_ha_yaml(str(yaml_path))


class TestPeakPowerYAMLStructure:
    """Test peak_power.yaml file structure."""

    def test_yaml_loads_successfully(self, peak_power_config):
        """YAML should load without errors."""
        assert peak_power_config is not None

    def test_has_automation_section(self, peak_power_config):
        """Should have automation section."""
        assert 'automation' in peak_power_config

    def test_has_input_number_section(self, peak_power_config):
        """Should have input_number section for configurable thresholds."""
        assert 'input_number' in peak_power_config

    def test_has_input_datetime_section(self, peak_power_config):
        """Should have input_datetime section for configurable times."""
        assert 'input_datetime' in peak_power_config


class TestInputNumberEntities:
    """Test input_number entities for temperature thresholds."""

    def test_has_daytime_heater_start(self, peak_power_config):
        """Should have input_number for daytime heater start threshold."""
        assert 'peak_power_daytime_heater_start' in peak_power_config['input_number']

    def test_has_daytime_heater_stop(self, peak_power_config):
        """Should have input_number for daytime heater stop threshold."""
        assert 'peak_power_daytime_heater_stop' in peak_power_config['input_number']

    def test_has_nighttime_heater_start(self, peak_power_config):
        """Should have input_number for nighttime heater start threshold."""
        assert 'peak_power_nighttime_heater_start' in peak_power_config['input_number']

    def test_has_nighttime_heater_stop(self, peak_power_config):
        """Should have input_number for nighttime heater stop threshold."""
        assert 'peak_power_nighttime_heater_stop' in peak_power_config['input_number']

    def test_daytime_heater_start_defaults_to_minus_10(self, peak_power_config):
        """Daytime heater start should default to -10°C."""
        entity = peak_power_config['input_number']['peak_power_daytime_heater_start']
        assert entity['initial'] == -10

    def test_daytime_heater_stop_defaults_to_0(self, peak_power_config):
        """Daytime heater stop should default to 0°C."""
        entity = peak_power_config['input_number']['peak_power_daytime_heater_stop']
        assert entity['initial'] == 0

    def test_nighttime_heater_start_defaults_to_minus_6(self, peak_power_config):
        """Nighttime heater start should default to -6°C."""
        entity = peak_power_config['input_number']['peak_power_nighttime_heater_start']
        assert entity['initial'] == -6

    def test_nighttime_heater_stop_defaults_to_4(self, peak_power_config):
        """Nighttime heater stop should default to 4°C."""
        entity = peak_power_config['input_number']['peak_power_nighttime_heater_stop']
        assert entity['initial'] == 4

    def test_all_have_unit_of_measurement(self, peak_power_config):
        """All temperature inputs should have °C unit."""
        for entity_id in ['peak_power_daytime_heater_start', 'peak_power_daytime_heater_stop',
                          'peak_power_nighttime_heater_start', 'peak_power_nighttime_heater_stop']:
            entity = peak_power_config['input_number'][entity_id]
            assert entity['unit_of_measurement'] == '°C'


class TestInputDatetimeEntities:
    """Test input_datetime entities for time settings."""

    def test_has_daytime_start(self, peak_power_config):
        """Should have input_datetime for daytime start time."""
        assert 'peak_power_daytime_start' in peak_power_config['input_datetime']

    def test_has_nighttime_start(self, peak_power_config):
        """Should have input_datetime for nighttime start time."""
        assert 'peak_power_nighttime_start' in peak_power_config['input_datetime']

    def test_daytime_start_is_time_only(self, peak_power_config):
        """Daytime start should be time-only (no date)."""
        entity = peak_power_config['input_datetime']['peak_power_daytime_start']
        assert entity['has_time'] is True
        assert entity['has_date'] is False

    def test_nighttime_start_is_time_only(self, peak_power_config):
        """Nighttime start should be time-only (no date)."""
        entity = peak_power_config['input_datetime']['peak_power_nighttime_start']
        assert entity['has_time'] is True
        assert entity['has_date'] is False


class TestDaytimeAutomation:
    """Test the daytime (peak hours) automation."""

    def test_has_daytime_automation(self, peak_power_config):
        """Should have automation for daytime settings."""
        automations = peak_power_config['automation']
        automation_ids = [a['id'] for a in automations]
        assert 'peak_power_daytime_settings' in automation_ids

    def test_daytime_trigger_uses_input_datetime(self, peak_power_config):
        """Daytime automation should trigger from input_datetime entity."""
        automations = peak_power_config['automation']
        daytime_auto = next(a for a in automations if a['id'] == 'peak_power_daytime_settings')

        trigger = daytime_auto['trigger'][0]
        assert trigger['platform'] == 'time'
        assert trigger['at'] == 'input_datetime.peak_power_daytime_start'

    def test_daytime_sets_heater_start_from_input(self, peak_power_config):
        """Daytime should set external_additional_heater_start from input_number."""
        automations = peak_power_config['automation']
        daytime_auto = next(a for a in automations if a['id'] == 'peak_power_daytime_settings')

        actions = daytime_auto['action']
        heater_start_action = next(
            a for a in actions
            if a.get('target', {}).get('entity_id') == 'number.external_additional_heater_start'
        )

        assert heater_start_action['service'] == 'number.set_value'
        # Value should be a template referencing the input_number
        value = heater_start_action['data']['value']
        assert 'input_number.peak_power_daytime_heater_start' in value

    def test_daytime_sets_heater_stop_from_input(self, peak_power_config):
        """Daytime should set external_additional_heater_stop from input_number."""
        automations = peak_power_config['automation']
        daytime_auto = next(a for a in automations if a['id'] == 'peak_power_daytime_settings')

        actions = daytime_auto['action']
        heater_stop_action = next(
            a for a in actions
            if a.get('target', {}).get('entity_id') == 'number.external_additional_heater_stop'
        )

        assert heater_stop_action['service'] == 'number.set_value'
        # Value should be a template referencing the input_number
        value = heater_stop_action['data']['value']
        assert 'input_number.peak_power_daytime_heater_stop' in value


class TestNighttimeAutomation:
    """Test the nighttime (off-peak hours) automation."""

    def test_has_nighttime_automation(self, peak_power_config):
        """Should have automation for nighttime settings."""
        automations = peak_power_config['automation']
        automation_ids = [a['id'] for a in automations]
        assert 'peak_power_nighttime_settings' in automation_ids

    def test_nighttime_trigger_uses_input_datetime(self, peak_power_config):
        """Nighttime automation should trigger from input_datetime entity."""
        automations = peak_power_config['automation']
        nighttime_auto = next(a for a in automations if a['id'] == 'peak_power_nighttime_settings')

        trigger = nighttime_auto['trigger'][0]
        assert trigger['platform'] == 'time'
        assert trigger['at'] == 'input_datetime.peak_power_nighttime_start'

    def test_nighttime_sets_heater_start_from_input(self, peak_power_config):
        """Nighttime should set external_additional_heater_start from input_number."""
        automations = peak_power_config['automation']
        nighttime_auto = next(a for a in automations if a['id'] == 'peak_power_nighttime_settings')

        actions = nighttime_auto['action']
        heater_start_action = next(
            a for a in actions
            if a.get('target', {}).get('entity_id') == 'number.external_additional_heater_start'
        )

        assert heater_start_action['service'] == 'number.set_value'
        # Value should be a template referencing the input_number
        value = heater_start_action['data']['value']
        assert 'input_number.peak_power_nighttime_heater_start' in value

    def test_nighttime_sets_heater_stop_from_input(self, peak_power_config):
        """Nighttime should set external_additional_heater_stop from input_number."""
        automations = peak_power_config['automation']
        nighttime_auto = next(a for a in automations if a['id'] == 'peak_power_nighttime_settings')

        actions = nighttime_auto['action']
        heater_stop_action = next(
            a for a in actions
            if a.get('target', {}).get('entity_id') == 'number.external_additional_heater_stop'
        )

        assert heater_stop_action['service'] == 'number.set_value'
        # Value should be a template referencing the input_number
        value = heater_stop_action['data']['value']
        assert 'input_number.peak_power_nighttime_heater_stop' in value


class TestInitAutomation:
    """Test the initialization automation for default times."""

    def test_has_init_automation(self, peak_power_config):
        """Should have automation to initialize default times."""
        automations = peak_power_config['automation']
        automation_ids = [a['id'] for a in automations]
        assert 'peak_power_init_times' in automation_ids

    def test_init_triggers_on_ha_start(self, peak_power_config):
        """Init automation should trigger on Home Assistant start."""
        automations = peak_power_config['automation']
        init_auto = next(a for a in automations if a['id'] == 'peak_power_init_times')

        trigger = init_auto['trigger'][0]
        assert trigger['platform'] == 'homeassistant'
        assert trigger['event'] == 'start'

    def test_init_sets_daytime_start_to_0640(self, peak_power_config):
        """Init should set daytime start to 06:40:00."""
        automations = peak_power_config['automation']
        init_auto = next(a for a in automations if a['id'] == 'peak_power_init_times')

        actions = init_auto['action']
        daytime_action = next(
            a for a in actions
            if a.get('target', {}).get('entity_id') == 'input_datetime.peak_power_daytime_start'
        )

        assert daytime_action['data']['time'] == '06:40:00'

    def test_init_sets_nighttime_start_to_2100(self, peak_power_config):
        """Init should set nighttime start to 21:00:00."""
        automations = peak_power_config['automation']
        init_auto = next(a for a in automations if a['id'] == 'peak_power_init_times')

        actions = init_auto['action']
        nighttime_action = next(
            a for a in actions
            if a.get('target', {}).get('entity_id') == 'input_datetime.peak_power_nighttime_start'
        )

        assert nighttime_action['data']['time'] == '21:00:00'


class TestAutomationCompleteness:
    """Test that automations are properly configured."""

    def test_automations_have_aliases(self, peak_power_config):
        """All automations should have human-readable aliases."""
        for automation in peak_power_config['automation']:
            assert 'alias' in automation, f"Automation {automation['id']} missing alias"

    def test_automations_have_descriptions(self, peak_power_config):
        """All automations should have descriptions."""
        for automation in peak_power_config['automation']:
            assert 'description' in automation, f"Automation {automation['id']} missing description"

    def test_daytime_automation_mode(self, peak_power_config):
        """Daytime automation should use single mode."""
        automations = peak_power_config['automation']
        daytime_auto = next(a for a in automations if a['id'] == 'peak_power_daytime_settings')
        assert daytime_auto.get('mode', 'single') == 'single'

    def test_nighttime_automation_mode(self, peak_power_config):
        """Nighttime automation should use single mode."""
        automations = peak_power_config['automation']
        nighttime_auto = next(a for a in automations if a['id'] == 'peak_power_nighttime_settings')
        assert nighttime_auto.get('mode', 'single') == 'single'

    def test_total_automation_count(self, peak_power_config):
        """Should have exactly 3 automations (init, daytime, nighttime)."""
        assert len(peak_power_config['automation']) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
