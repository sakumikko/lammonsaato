/**
 * Entity presets and default graph configurations for multi-entity graph
 */

import { EntityPreset, GraphConfig } from '@/types/graphs';

export const ENTITY_PRESETS: Record<string, EntityPreset> = {
  // Control values (left axis - PID and integral)
  'sensor.external_heater_pid_sum': {
    entityId: 'sensor.external_heater_pid_sum',
    label: 'PID Sum',
    color: '#ef4444', // red
    minValue: -20,
    maxValue: 20,
    axisGroup: 'control',
    unit: '',
  },
  'sensor.heating_season_integral_value': {
    entityId: 'sensor.heating_season_integral_value',
    label: 'Heating Integral',
    color: '#f97316', // orange
    minValue: -300,
    maxValue: 100,
    axisGroup: 'control',
    unit: '°min',
  },
  'number.external_additional_heater_start': {
    entityId: 'number.external_additional_heater_start',
    label: 'Start Threshold',
    color: '#dc2626', // red-600
    minValue: -20,
    maxValue: 20,
    axisGroup: 'control',
    unit: '',
  },
  'number.external_additional_heater_stop': {
    entityId: 'number.external_additional_heater_stop',
    label: 'Stop Threshold',
    color: '#16a34a', // green-600
    minValue: -20,
    maxValue: 20,
    axisGroup: 'control',
    unit: '',
  },

  // Delta temperatures (narrow scale -10 to +10)
  'sensor.supply_line_temperature_difference': {
    entityId: 'sensor.supply_line_temperature_difference',
    label: 'Supply ΔT',
    color: '#22c55e', // green
    minValue: -10,
    maxValue: 10,
    axisGroup: 'delta',
    unit: '°C',
  },
  'sensor.pool_heat_exchanger_delta_t': {
    entityId: 'sensor.pool_heat_exchanger_delta_t',
    label: 'Condenser ΔT',
    color: '#f59e0b', // amber
    minValue: -10,
    maxValue: 10,
    axisGroup: 'delta',
    unit: '°C',
  },

  // Temperature values (right axis)
  'sensor.system_supply_line_temperature': {
    entityId: 'sensor.system_supply_line_temperature',
    label: 'Supply Actual',
    color: '#3b82f6', // blue
    minValue: 20,
    maxValue: 65,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.system_supply_line_calculated_set_point': {
    entityId: 'sensor.system_supply_line_calculated_set_point',
    label: 'Supply Target',
    color: '#06b6d4', // cyan
    minValue: 20,
    maxValue: 65,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.condenser_out_temperature': {
    entityId: 'sensor.condenser_out_temperature',
    label: 'Condenser Out',
    color: '#dc2626', // red-600
    minValue: 20,
    maxValue: 70,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.condenser_in_temperature': {
    entityId: 'sensor.condenser_in_temperature',
    label: 'Condenser In',
    color: '#2563eb', // blue-600
    minValue: 20,
    maxValue: 60,
    axisGroup: 'right',
    unit: '°C',
  },

  // Percentage values
  'sensor.external_additional_heater_current_demand': {
    entityId: 'sensor.external_additional_heater_current_demand',
    label: 'Heater Demand',
    color: '#a855f7', // purple
    minValue: 0,
    maxValue: 100,
    axisGroup: 'percent',
    unit: '%',
  },
};

export const DEFAULT_GRAPHS: GraphConfig[] = [
  {
    id: 'external-heater-analysis',
    name: 'External Heater Analysis',
    entities: [
      { ...ENTITY_PRESETS['sensor.external_heater_pid_sum'], visible: true },
      { ...ENTITY_PRESETS['sensor.heating_season_integral_value'], visible: true },
      { ...ENTITY_PRESETS['sensor.supply_line_temperature_difference'], visible: true },
      { ...ENTITY_PRESETS['number.external_additional_heater_start'], visible: true },
      { ...ENTITY_PRESETS['sensor.external_additional_heater_current_demand'], visible: true },
    ],
    timeRange: '24h',
    mode: 'normalized',
  },
  {
    id: 'temperature-analysis',
    name: 'Temperature Analysis',
    entities: [
      { ...ENTITY_PRESETS['sensor.system_supply_line_temperature'], visible: true },
      { ...ENTITY_PRESETS['sensor.system_supply_line_calculated_set_point'], visible: true },
      { ...ENTITY_PRESETS['sensor.supply_line_temperature_difference'], visible: true },
      { ...ENTITY_PRESETS['sensor.condenser_out_temperature'], visible: true },
      { ...ENTITY_PRESETS['sensor.condenser_in_temperature'], visible: true },
    ],
    timeRange: '24h',
    mode: 'normalized',
  },
];
