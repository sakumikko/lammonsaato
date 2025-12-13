/**
 * Entity presets and default graph configurations for multi-entity graph
 *
 * IMPORTANT: When adding new entities to thermia_required_entities.yaml or
 * pool_heating.yaml, also add them here. Run `make validate-entities` to check.
 */

import { EntityPreset, GraphConfig } from '@/types/graphs';

// Color palette for entities
const COLORS = {
  red: '#ef4444',
  red600: '#dc2626',
  orange: '#f97316',
  amber: '#f59e0b',
  yellow: '#eab308',
  lime: '#84cc16',
  green: '#22c55e',
  green600: '#16a34a',
  emerald: '#10b981',
  teal: '#14b8a6',
  cyan: '#06b6d4',
  sky: '#0ea5e9',
  blue: '#3b82f6',
  blue600: '#2563eb',
  indigo: '#6366f1',
  violet: '#8b5cf6',
  purple: '#a855f7',
  fuchsia: '#d946ef',
  pink: '#ec4899',
  rose: '#f43f5e',
  slate: '#64748b',
  gray: '#6b7280',
};

export const ENTITY_PRESETS: Record<string, EntityPreset> = {
  // ============================================
  // EXTERNAL HEATER ANALYSIS
  // ============================================
  'sensor.external_heater_pid_sum': {
    entityId: 'sensor.external_heater_pid_sum',
    label: 'PID Sum',
    color: COLORS.red,
    minValue: -20,
    maxValue: 20,
    axisGroup: 'control',
    unit: '',
  },
  'sensor.heating_season_integral_value': {
    entityId: 'sensor.heating_season_integral_value',
    label: 'Heating Integral',
    color: COLORS.orange,
    minValue: -300,
    maxValue: 100,
    axisGroup: 'control',
    unit: '°min',
  },
  'sensor.cooling_season_integral_value': {
    entityId: 'sensor.cooling_season_integral_value',
    label: 'Cooling Integral',
    color: COLORS.cyan,
    minValue: -300,
    maxValue: 100,
    axisGroup: 'control',
    unit: '°min',
  },
  'sensor.p_value_for_gear_shifting_and_demand_calculation': {
    entityId: 'sensor.p_value_for_gear_shifting_and_demand_calculation',
    label: 'PID P-Value',
    color: COLORS.red600,
    minValue: -10,
    maxValue: 10,
    axisGroup: 'control',
    unit: '',
  },
  'sensor.i_value_for_gear_shifting_and_demand_calculation': {
    entityId: 'sensor.i_value_for_gear_shifting_and_demand_calculation',
    label: 'PID I-Value',
    color: COLORS.amber,
    minValue: -10,
    maxValue: 10,
    axisGroup: 'control',
    unit: '',
  },
  'sensor.d_value_for_gear_shifting_and_demand_calculation': {
    entityId: 'sensor.d_value_for_gear_shifting_and_demand_calculation',
    label: 'PID D-Value',
    color: COLORS.yellow,
    minValue: -10,
    maxValue: 10,
    axisGroup: 'control',
    unit: '',
  },
  'number.external_additional_heater_start': {
    entityId: 'number.external_additional_heater_start',
    label: 'Heater Start Threshold',
    color: COLORS.red600,
    minValue: -20,
    maxValue: 20,
    axisGroup: 'control',
    unit: '',
  },
  'number.external_additional_heater_stop': {
    entityId: 'number.external_additional_heater_stop',
    label: 'Heater Stop Threshold',
    color: COLORS.green600,
    minValue: -20,
    maxValue: 20,
    axisGroup: 'control',
    unit: '',
  },
  'number.external_heater_outdoor_temp_limit': {
    entityId: 'number.external_heater_outdoor_temp_limit',
    label: 'Heater Outdoor Limit',
    color: COLORS.slate,
    minValue: -30,
    maxValue: 10,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.external_additional_heater_current_demand': {
    entityId: 'sensor.external_additional_heater_current_demand',
    label: 'Heater Demand',
    color: COLORS.purple,
    minValue: 0,
    maxValue: 100,
    axisGroup: 'percent',
    unit: '%',
  },

  // ============================================
  // SUPPLY LINE TEMPERATURES
  // ============================================
  'sensor.system_supply_line_temperature': {
    entityId: 'sensor.system_supply_line_temperature',
    label: 'Supply Actual',
    color: COLORS.blue,
    minValue: 20,
    maxValue: 65,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.system_supply_line_calculated_set_point': {
    entityId: 'sensor.system_supply_line_calculated_set_point',
    label: 'Supply Target',
    color: COLORS.cyan,
    minValue: 20,
    maxValue: 65,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.supply_line_temperature_difference': {
    entityId: 'sensor.supply_line_temperature_difference',
    label: 'Supply ΔT',
    color: COLORS.green,
    minValue: -10,
    maxValue: 10,
    axisGroup: 'delta',
    unit: '°C',
  },
  'sensor.mix_valve_1_supply_line_temperature': {
    entityId: 'sensor.mix_valve_1_supply_line_temperature',
    label: 'Mix Valve 1 Supply',
    color: COLORS.sky,
    minValue: 20,
    maxValue: 55,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.desired_temperature_distribution_circuit_mix_valve_1': {
    entityId: 'sensor.desired_temperature_distribution_circuit_mix_valve_1',
    label: 'Mix Valve 1 Target',
    color: COLORS.teal,
    minValue: 20,
    maxValue: 55,
    axisGroup: 'right',
    unit: '°C',
  },

  // ============================================
  // CONDENSER (POOL HEAT EXCHANGER)
  // ============================================
  'sensor.condenser_out_temperature': {
    entityId: 'sensor.condenser_out_temperature',
    label: 'Condenser Out',
    color: COLORS.red600,
    minValue: 20,
    maxValue: 70,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.condenser_in_temperature': {
    entityId: 'sensor.condenser_in_temperature',
    label: 'Condenser In',
    color: COLORS.blue600,
    minValue: 20,
    maxValue: 60,
    axisGroup: 'right',
    unit: '°C',
  },
  'sensor.pool_heat_exchanger_delta_t': {
    entityId: 'sensor.pool_heat_exchanger_delta_t',
    label: 'Condenser ΔT',
    color: COLORS.amber,
    minValue: -10,
    maxValue: 10,
    axisGroup: 'delta',
    unit: '°C',
  },
  'sensor.condenser_circulation_pump_speed': {
    entityId: 'sensor.condenser_circulation_pump_speed',
    label: 'Condenser Pump Speed',
    color: COLORS.indigo,
    minValue: 0,
    maxValue: 100,
    axisGroup: 'percent',
    unit: '%',
  },

  // ============================================
  // BRINE CIRCUIT (GROUND LOOP)
  // ============================================
  'sensor.brine_in_temperature': {
    entityId: 'sensor.brine_in_temperature',
    label: 'Brine In',
    color: COLORS.emerald,
    minValue: -5,
    maxValue: 15,
    axisGroup: 'brine',
    unit: '°C',
  },
  'sensor.brine_out_temperature': {
    entityId: 'sensor.brine_out_temperature',
    label: 'Brine Out',
    color: COLORS.teal,
    minValue: -5,
    maxValue: 15,
    axisGroup: 'brine',
    unit: '°C',
  },
  'sensor.brine_circulation_pump_speed': {
    entityId: 'sensor.brine_circulation_pump_speed',
    label: 'Brine Pump Speed',
    color: COLORS.green,
    minValue: 0,
    maxValue: 100,
    axisGroup: 'percent',
    unit: '%',
  },

  // ============================================
  // COMPRESSOR
  // ============================================
  'sensor.compressor_speed_rpm': {
    entityId: 'sensor.compressor_speed_rpm',
    label: 'Compressor RPM',
    color: COLORS.violet,
    minValue: 0,
    maxValue: 6000,
    axisGroup: 'rpm',
    unit: 'rpm',
  },
  'sensor.compressor_current_gear': {
    entityId: 'sensor.compressor_current_gear',
    label: 'Compressor Gear',
    color: COLORS.fuchsia,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'gear',
    unit: '',
  },
  'sensor.compressor_available_gears': {
    entityId: 'sensor.compressor_available_gears',
    label: 'Available Gears',
    color: COLORS.pink,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'gear',
    unit: '',
  },
  'sensor.desired_gear_for_heating': {
    entityId: 'sensor.desired_gear_for_heating',
    label: 'Desired Gear (Heating)',
    color: COLORS.rose,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'gear',
    unit: '',
  },
  'sensor.desired_gear_for_pool': {
    entityId: 'sensor.desired_gear_for_pool',
    label: 'Desired Gear (Pool)',
    color: COLORS.cyan,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'gear',
    unit: '',
  },
  'sensor.desired_gear_for_tap_water': {
    entityId: 'sensor.desired_gear_for_tap_water',
    label: 'Desired Gear (DHW)',
    color: COLORS.amber,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'gear',
    unit: '',
  },
  'sensor.maximum_gear_out_of_all_the_currently_requested_gears': {
    entityId: 'sensor.maximum_gear_out_of_all_the_currently_requested_gears',
    label: 'Max Requested Gear',
    color: COLORS.purple,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'gear',
    unit: '',
  },

  // ============================================
  // REFRIGERANT CYCLE
  // ============================================
  'sensor.discharge_pipe_temperature': {
    entityId: 'sensor.discharge_pipe_temperature',
    label: 'Discharge Temp',
    color: COLORS.red,
    minValue: 40,
    maxValue: 120,
    axisGroup: 'refrigerant',
    unit: '°C',
  },
  'sensor.suction_gas_temperature': {
    entityId: 'sensor.suction_gas_temperature',
    label: 'Suction Gas Temp',
    color: COLORS.blue,
    minValue: -10,
    maxValue: 30,
    axisGroup: 'refrigerant',
    unit: '°C',
  },
  'sensor.liquid_line_temperature': {
    entityId: 'sensor.liquid_line_temperature',
    label: 'Liquid Line Temp',
    color: COLORS.cyan,
    minValue: 20,
    maxValue: 60,
    axisGroup: 'refrigerant',
    unit: '°C',
  },
  'sensor.superheat_temperature': {
    entityId: 'sensor.superheat_temperature',
    label: 'Superheat',
    color: COLORS.orange,
    minValue: 0,
    maxValue: 30,
    axisGroup: 'delta',
    unit: '°C',
  },
  'sensor.sub_cooling_temperature': {
    entityId: 'sensor.sub_cooling_temperature',
    label: 'Subcooling',
    color: COLORS.sky,
    minValue: 0,
    maxValue: 20,
    axisGroup: 'delta',
    unit: '°C',
  },
  'sensor.high_pressure_side': {
    entityId: 'sensor.high_pressure_side',
    label: 'High Pressure',
    color: COLORS.red,
    minValue: 0,
    maxValue: 40,
    axisGroup: 'pressure',
    unit: 'bar',
  },
  'sensor.low_pressure_side': {
    entityId: 'sensor.low_pressure_side',
    label: 'Low Pressure',
    color: COLORS.blue,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'pressure',
    unit: 'bar',
  },

  // ============================================
  // TAP WATER (DHW)
  // ============================================
  'sensor.tap_water_top_temperature': {
    entityId: 'sensor.tap_water_top_temperature',
    label: 'DHW Top',
    color: COLORS.red,
    minValue: 30,
    maxValue: 65,
    axisGroup: 'dhw',
    unit: '°C',
  },
  'sensor.tap_water_lower_temperature': {
    entityId: 'sensor.tap_water_lower_temperature',
    label: 'DHW Bottom',
    color: COLORS.blue,
    minValue: 20,
    maxValue: 55,
    axisGroup: 'dhw',
    unit: '°C',
  },
  'sensor.tap_water_weighted_temperature': {
    entityId: 'sensor.tap_water_weighted_temperature',
    label: 'DHW Weighted',
    color: COLORS.purple,
    minValue: 25,
    maxValue: 60,
    axisGroup: 'dhw',
    unit: '°C',
  },

  // ============================================
  // OUTDOOR & POOL
  // ============================================
  'sensor.outdoor_temperature': {
    entityId: 'sensor.outdoor_temperature',
    label: 'Outdoor Temp',
    color: COLORS.slate,
    minValue: -30,
    maxValue: 40,
    axisGroup: 'outdoor',
    unit: '°C',
  },
  'sensor.pool_return_line_temperature': {
    entityId: 'sensor.pool_return_line_temperature',
    label: 'Pool Return (raw)',
    color: COLORS.cyan,
    minValue: 2000,
    maxValue: 3500,
    axisGroup: 'raw',
    unit: '',
  },
  'sensor.pool_return_line_temperature_corrected': {
    entityId: 'sensor.pool_return_line_temperature_corrected',
    label: 'Pool Return',
    color: COLORS.cyan,
    minValue: 20,
    maxValue: 35,
    axisGroup: 'pool',
    unit: '°C',
  },
  'sensor.pool_true_temperature': {
    entityId: 'sensor.pool_true_temperature',
    label: 'Pool True Temp',
    color: COLORS.teal,
    minValue: 20,
    maxValue: 35,
    axisGroup: 'pool',
    unit: '°C',
  },

  // ============================================
  // POOL HEATING POWER & ENERGY
  // ============================================
  'sensor.pool_thermal_power': {
    entityId: 'sensor.pool_thermal_power',
    label: 'Thermal Power',
    color: COLORS.orange,
    minValue: 0,
    maxValue: 20,
    axisGroup: 'power',
    unit: 'kW',
  },
  'sensor.pool_heating_electrical_power': {
    entityId: 'sensor.pool_heating_electrical_power',
    label: 'Electrical Power',
    color: COLORS.yellow,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'power',
    unit: 'kW',
  },
  'sensor.pool_heating_cost_rate': {
    entityId: 'sensor.pool_heating_cost_rate',
    label: 'Cost Rate',
    color: COLORS.green,
    minValue: 0,
    maxValue: 2,
    axisGroup: 'cost',
    unit: '€/h',
  },

  // ============================================
  // ELECTRICITY PRICING
  // ============================================
  'sensor.nordpool_kwh_fi_eur_3_10_0255': {
    entityId: 'sensor.nordpool_kwh_fi_eur_3_10_0255',
    label: 'Nordpool Price',
    color: COLORS.green,
    minValue: 0,
    maxValue: 50,
    axisGroup: 'price',
    unit: 'c/kWh',
  },
  'sensor.current_nordpool_price': {
    entityId: 'sensor.current_nordpool_price',
    label: 'Current Price',
    color: COLORS.emerald,
    minValue: 0,
    maxValue: 50,
    axisGroup: 'price',
    unit: 'c/kWh',
  },
  'sensor.pool_heating_avg_price': {
    entityId: 'sensor.pool_heating_avg_price',
    label: 'Avg Scheduled Price',
    color: COLORS.lime,
    minValue: 0,
    maxValue: 50,
    axisGroup: 'price',
    unit: 'c/kWh',
  },

  // ============================================
  // DIAGNOSTIC
  // ============================================
  'sensor.mix_valve_1_position': {
    entityId: 'sensor.mix_valve_1_position',
    label: 'Mix Valve Position',
    color: COLORS.indigo,
    minValue: 0,
    maxValue: 100,
    axisGroup: 'percent',
    unit: '%',
  },
  'sensor.first_prioritised_demand': {
    entityId: 'sensor.first_prioritised_demand',
    label: 'Priority Demand',
    color: COLORS.violet,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'control',
    unit: '',
  },
  'sensor.selected_heat_curve': {
    entityId: 'sensor.selected_heat_curve',
    label: 'Selected Heat Curve',
    color: COLORS.gray,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'control',
    unit: '',
  },

  // ============================================
  // GEAR LIMITS (CONTROL NUMBERS)
  // ============================================
  'number.minimum_allowed_gear_in_heating': {
    entityId: 'number.minimum_allowed_gear_in_heating',
    label: 'Min Gear (Heating)',
    color: COLORS.blue,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'gear',
    unit: '',
  },
  'number.maximum_allowed_gear_in_heating': {
    entityId: 'number.maximum_allowed_gear_in_heating',
    label: 'Max Gear (Heating)',
    color: COLORS.blue600,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'gear',
    unit: '',
  },
  'number.minimum_allowed_gear_in_pool': {
    entityId: 'number.minimum_allowed_gear_in_pool',
    label: 'Min Gear (Pool)',
    color: COLORS.cyan,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'gear',
    unit: '',
  },
  'number.maximum_allowed_gear_in_pool': {
    entityId: 'number.maximum_allowed_gear_in_pool',
    label: 'Max Gear (Pool)',
    color: COLORS.teal,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'gear',
    unit: '',
  },
  'number.minimum_allowed_gear_in_tap_water': {
    entityId: 'number.minimum_allowed_gear_in_tap_water',
    label: 'Min Gear (DHW)',
    color: COLORS.orange,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'gear',
    unit: '',
  },
  'number.maximum_allowed_gear_in_tap_water': {
    entityId: 'number.maximum_allowed_gear_in_tap_water',
    label: 'Max Gear (DHW)',
    color: COLORS.amber,
    minValue: 0,
    maxValue: 10,
    axisGroup: 'gear',
    unit: '',
  },

  // ============================================
  // TAP WATER CONTROL
  // ============================================
  'number.start_temperature_tap_water': {
    entityId: 'number.start_temperature_tap_water',
    label: 'DHW Start Temp',
    color: COLORS.red,
    minValue: 35,
    maxValue: 55,
    axisGroup: 'dhw',
    unit: '°C',
  },
  'number.stop_temperature_tap_water': {
    entityId: 'number.stop_temperature_tap_water',
    label: 'DHW Stop Temp',
    color: COLORS.green,
    minValue: 40,
    maxValue: 60,
    axisGroup: 'dhw',
    unit: '°C',
  },

  // ============================================
  // HOT GAS PUMP CONTROL
  // ============================================
  'number.hot_gas_pump_start_temperature_discharge_pipe': {
    entityId: 'number.hot_gas_pump_start_temperature_discharge_pipe',
    label: 'Hot Gas Start',
    color: COLORS.red,
    minValue: 80,
    maxValue: 120,
    axisGroup: 'refrigerant',
    unit: '°C',
  },
  'number.hot_gas_pump_lower_stop_limit_temperature_discharge_pipe': {
    entityId: 'number.hot_gas_pump_lower_stop_limit_temperature_discharge_pipe',
    label: 'Hot Gas Lower Stop',
    color: COLORS.orange,
    minValue: 60,
    maxValue: 100,
    axisGroup: 'refrigerant',
    unit: '°C',
  },
  'number.hot_gas_pump_upper_stop_limit_temperature_discharge_pipe': {
    entityId: 'number.hot_gas_pump_upper_stop_limit_temperature_discharge_pipe',
    label: 'Hot Gas Upper Stop',
    color: COLORS.yellow,
    minValue: 80,
    maxValue: 130,
    axisGroup: 'refrigerant',
    unit: '°C',
  },

  // ============================================
  // HEATING CURVE CONTROL
  // ============================================
  'number.max_limitation': {
    entityId: 'number.max_limitation',
    label: 'Max Limitation',
    color: COLORS.red,
    minValue: 30,
    maxValue: 70,
    axisGroup: 'right',
    unit: '°C',
  },
  'number.min_limitation': {
    entityId: 'number.min_limitation',
    label: 'Min Limitation',
    color: COLORS.blue,
    minValue: 15,
    maxValue: 40,
    axisGroup: 'right',
    unit: '°C',
  },
  'number.comfort_wheel_setting': {
    entityId: 'number.comfort_wheel_setting',
    label: 'Comfort Wheel',
    color: COLORS.purple,
    minValue: -10,
    maxValue: 10,
    axisGroup: 'control',
    unit: '',
  },

  // ============================================
  // HEAT CURVE SETPOINTS (Y values)
  // ============================================
  'number.set_point_heat_curve_y_1': {
    entityId: 'number.set_point_heat_curve_y_1',
    label: 'Heat Curve Y1',
    color: COLORS.red,
    minValue: 20,
    maxValue: 70,
    axisGroup: 'right',
    unit: '°C',
  },
  'number.set_point_heat_curve_y_2': {
    entityId: 'number.set_point_heat_curve_y_2',
    label: 'Heat Curve Y2',
    color: COLORS.orange,
    minValue: 20,
    maxValue: 70,
    axisGroup: 'right',
    unit: '°C',
  },
  'number.set_point_heat_curve_y_3': {
    entityId: 'number.set_point_heat_curve_y_3',
    label: 'Heat Curve Y3',
    color: COLORS.amber,
    minValue: 20,
    maxValue: 70,
    axisGroup: 'right',
    unit: '°C',
  },
  'number.set_point_heat_curve_y_4': {
    entityId: 'number.set_point_heat_curve_y_4',
    label: 'Heat Curve Y4',
    color: COLORS.yellow,
    minValue: 20,
    maxValue: 70,
    axisGroup: 'right',
    unit: '°C',
  },
  'number.set_point_heat_curve_y_5': {
    entityId: 'number.set_point_heat_curve_y_5',
    label: 'Heat Curve Y5',
    color: COLORS.lime,
    minValue: 20,
    maxValue: 70,
    axisGroup: 'right',
    unit: '°C',
  },
  'number.set_point_heat_curve_y_6': {
    entityId: 'number.set_point_heat_curve_y_6',
    label: 'Heat Curve Y6',
    color: COLORS.green,
    minValue: 20,
    maxValue: 70,
    axisGroup: 'right',
    unit: '°C',
  },
  'number.set_point_heat_curve_y_7': {
    entityId: 'number.set_point_heat_curve_y_7',
    label: 'Heat Curve Y7',
    color: COLORS.emerald,
    minValue: 20,
    maxValue: 70,
    axisGroup: 'right',
    unit: '°C',
  },

  // ============================================
  // CUMULATIVE SENSORS
  // ============================================
  'sensor.pool_heating_electricity': {
    entityId: 'sensor.pool_heating_electricity',
    label: 'Total Electricity',
    color: COLORS.yellow,
    minValue: 0,
    maxValue: 100,
    axisGroup: 'energy',
    unit: 'kWh',
  },
  'sensor.pool_heating_cumulative_cost': {
    entityId: 'sensor.pool_heating_cumulative_cost',
    label: 'Total Cost',
    color: COLORS.green,
    minValue: 0,
    maxValue: 50,
    axisGroup: 'cost',
    unit: '€',
  },
};

// All entity IDs that should be available for graphing
// Used by validation script to check coverage
export const GRAPHABLE_ENTITIES = Object.keys(ENTITY_PRESETS);

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
  {
    id: 'compressor-analysis',
    name: 'Compressor Analysis',
    entities: [
      { ...ENTITY_PRESETS['sensor.compressor_speed_rpm'], visible: true },
      { ...ENTITY_PRESETS['sensor.compressor_current_gear'], visible: true },
      { ...ENTITY_PRESETS['sensor.discharge_pipe_temperature'], visible: true },
      { ...ENTITY_PRESETS['sensor.high_pressure_side'], visible: true },
      { ...ENTITY_PRESETS['sensor.low_pressure_side'], visible: true },
    ],
    timeRange: '24h',
    mode: 'normalized',
  },
  {
    id: 'pool-heating',
    name: 'Pool Heating',
    entities: [
      { ...ENTITY_PRESETS['sensor.pool_return_line_temperature_corrected'], visible: true },
      { ...ENTITY_PRESETS['sensor.condenser_out_temperature'], visible: true },
      { ...ENTITY_PRESETS['sensor.condenser_in_temperature'], visible: true },
      { ...ENTITY_PRESETS['sensor.pool_thermal_power'], visible: true },
      { ...ENTITY_PRESETS['sensor.pool_heating_electrical_power'], visible: true },
    ],
    timeRange: '24h',
    mode: 'normalized',
  },
  {
    id: 'brine-circuit',
    name: 'Brine Circuit',
    entities: [
      { ...ENTITY_PRESETS['sensor.brine_in_temperature'], visible: true },
      { ...ENTITY_PRESETS['sensor.brine_out_temperature'], visible: true },
      { ...ENTITY_PRESETS['sensor.brine_circulation_pump_speed'], visible: true },
      { ...ENTITY_PRESETS['sensor.outdoor_temperature'], visible: true },
    ],
    timeRange: '24h',
    mode: 'normalized',
  },
  {
    id: 'tap-water',
    name: 'Tap Water (DHW)',
    entities: [
      { ...ENTITY_PRESETS['sensor.tap_water_top_temperature'], visible: true },
      { ...ENTITY_PRESETS['sensor.tap_water_lower_temperature'], visible: true },
      { ...ENTITY_PRESETS['sensor.tap_water_weighted_temperature'], visible: true },
    ],
    timeRange: '24h',
    mode: 'normalized',
  },
  {
    id: 'custom',
    name: 'Custom',
    entities: [], // User selects entities dynamically
    timeRange: '24h',
    mode: 'normalized',
  },
];

/** Get all available entity presets as an array for the entity picker */
export const ALL_ENTITY_PRESETS = Object.values(ENTITY_PRESETS);
