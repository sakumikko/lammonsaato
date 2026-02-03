import { useState, useEffect, useCallback, useRef } from 'react';
import {
  SystemState,
  HeatPumpState,
  PoolHeatingState,
  ValveState,
  ScheduleState,
  ScheduleParameters,
  PriceBlock,
  GearSettings,
  TapWaterState,
  HotGasSettings,
  HeatingCurveSettings,
  PeakPowerSettings,
  SystemSupplyState,
  ExternalHeaterSettings,
} from '@/types/heating';
import { getHAWebSocket, HAEntityState } from '@/lib/ha-websocket';

/**
 * Entity mappings from Home Assistant to UI state
 *
 * Heat Pump entities (Thermia Genesis):
 * - sensor.condenser_out_temperature -> condenserOutTemp
 * - sensor.condenser_in_temperature -> condenserInTemp
 * - sensor.brine_in_temperature -> brineInTemp
 * - sensor.brine_out_temperature -> brineOutTemp
 * - sensor.outdoor_temperature -> outdoorTemp
 * - sensor.compressor_speed -> compressorRpm
 * - sensor.brine_circulation_pump_speed -> brineCirculationSpeed
 * - sensor.heat_pump_mode -> heatpumpMode
 *
 * Pool heating entities:
 * - input_boolean.pool_heating_enabled -> poolHeating.enabled
 * - binary_sensor.pool_heating_active -> poolHeating.active
 * - binary_sensor.pool_in_heating_window -> poolHeating.inHeatingWindow
 * - input_number.pool_target_temperature -> poolHeating.targetTemp
 * - sensor.pool_heat_exchanger_delta_t -> poolHeating.heatExchangerDeltaT
 * - sensor.pool_heating_electrical_power -> poolHeating.electricalPower
 * - sensor.pool_heating_electricity_daily -> poolHeating.dailyEnergy
 * - sensor.pool_heating_cost_daily -> poolHeating.dailyCost
 * - sensor.pool_heating_cost_monthly -> poolHeating.monthlyCost
 * - sensor.pool_heating_average_price -> poolHeating.averagePrice
 *
 * Valve entities (Shelly):
 * - switch.altaan_lammityksen_esto -> valve prevention (inverted: OFF = allow heating)
 * - switch.altaan_kiertovesipumppu -> circulation pump
 *
 * Schedule entities:
 * - input_datetime.pool_heat_block_N_start -> schedule.blocks[N].start
 * - input_datetime.pool_heat_block_N_end -> schedule.blocks[N].end
 * - input_number.pool_heat_block_N_price -> schedule.blocks[N].price
 * - input_boolean.pool_heat_block_N_enabled -> schedule.blocks[N].enabled
 * - input_boolean.pool_heating_night_complete -> poolHeating.nightComplete
 * - binary_sensor.nordpool_tomorrow_available -> schedule.nordpoolAvailable
 * - sensor.nordpool_kwh_fi_eur_3_10_0255 -> schedule.currentPrice
 */

// Entity IDs
const ENTITIES = {
  // Heat pump
  condenserOut: 'sensor.condenser_out_temperature',
  condenserIn: 'sensor.condenser_in_temperature',
  brineIn: 'sensor.brine_in_temperature',
  brineOut: 'sensor.brine_out_temperature',
  outdoor: 'sensor.outdoor_temperature',
  compressorSpeed: 'sensor.compressor_speed_rpm',
  compressorGear: 'sensor.compressor_current_gear',
  brinePumpSpeed: 'sensor.brine_circulation_pump_speed',
  heatPumpMode: 'sensor.heat_pump_mode',

  // Pool heating
  poolEnabled: 'input_boolean.pool_heating_enabled',
  poolActive: 'binary_sensor.pool_heating_active',
  inHeatingWindow: 'binary_sensor.pool_in_heating_window',
  poolTargetTemp: 'input_number.pool_target_temperature',
  nightComplete: 'input_boolean.pool_heating_night_complete',
  deltaT: 'sensor.pool_heat_exchanger_delta_t',
  electricalPower: 'sensor.pool_heating_electrical_power',
  dailyEnergy: 'sensor.pool_heating_electricity_daily',
  dailyCost: 'sensor.pool_heating_cost_daily',
  monthlyCost: 'sensor.pool_heating_cost_monthly',
  avgPrice: 'sensor.pool_heating_average_price',
  returnLineTemp: 'sensor.pool_return_line_temperature_corrected',

  // Valve (Shelly)
  heatingPrevention: 'switch.altaan_lammityksen_esto',
  circulationPump: 'switch.altaan_kiertovesipumppu',

  // Schedule
  nordpoolAvailable: 'binary_sensor.nordpool_tomorrow_available',
  nordpoolPrice: 'sensor.nordpool_kwh_fi_eur_3_10_0255',
  scheduleJson: 'input_text.pool_heating_schedule_json',

  // Schedule parameters
  minBlockDuration: 'input_number.pool_heating_min_block_duration',
  maxBlockDuration: 'input_number.pool_heating_max_block_duration',
  totalHours: 'input_number.pool_heating_total_hours',
  maxCostEur: 'input_number.pool_heating_max_cost_eur',
  minBreakDuration: 'input_number.pool_heating_min_break_duration',
  totalCost: 'input_number.pool_heating_total_cost',
  costLimitApplied: 'input_boolean.pool_heating_cost_limit_applied',

  // Gear settings (Thermia Genesis)
  minGearHeating: 'number.minimum_allowed_gear_in_heating',
  maxGearHeating: 'number.maximum_allowed_gear_in_heating',
  minGearPool: 'number.minimum_allowed_gear_in_pool',
  maxGearPool: 'number.maximum_allowed_gear_in_pool',
  minGearTapWater: 'number.minimum_allowed_gear_in_tap_water',
  maxGearTapWater: 'number.maximum_allowed_gear_in_tap_water',

  // Hot gas / refrigerant temperatures (Thermia Genesis)
  dischargePipeTemp: 'sensor.discharge_pipe_temperature',
  suctionGasTemp: 'sensor.suction_gas_temperature',
  liquidLineTemp: 'sensor.liquid_line_temperature',

  // Tap water temperatures (Thermia Genesis)
  tapWaterTop: 'sensor.tap_water_top_temperature',
  tapWaterLower: 'sensor.tap_water_lower_temperature',
  tapWaterWeighted: 'sensor.tap_water_weighted_temperature',
  tapWaterStartTemp: 'number.start_temperature_tap_water',
  tapWaterStopTemp: 'number.stop_temperature_tap_water',

  // Hot gas pump control (Thermia Genesis)
  hotGasPumpStartTemp: 'number.hot_gas_pump_start_temperature_discharge_pipe',
  hotGasLowerStopLimit: 'number.hot_gas_pump_lower_stop_limit_temperature_discharge_pipe',
  hotGasUpperStopLimit: 'number.hot_gas_pump_upper_stop_limit_temperature_discharge_pipe',

  // Heating curve settings (Thermia Genesis)
  heatingCurveMax: 'number.max_limitation',
  heatingCurveMin: 'number.min_limitation',

  // Peak power avoidance settings
  peakPowerDaytimeHeaterStart: 'input_number.peak_power_daytime_heater_start',
  peakPowerDaytimeHeaterStop: 'input_number.peak_power_daytime_heater_stop',
  peakPowerNighttimeHeaterStart: 'input_number.peak_power_nighttime_heater_start',
  peakPowerNighttimeHeaterStop: 'input_number.peak_power_nighttime_heater_stop',
  peakPowerDaytimeStart: 'input_datetime.peak_power_daytime_start',
  peakPowerNighttimeStart: 'input_datetime.peak_power_nighttime_start',

  // System supply temperatures (Thermia Genesis)
  systemSupplyTemp: 'sensor.system_supply_line_temperature',
  systemSupplyCurveTarget: 'sensor.system_supply_line_calculated_set_point',
  systemSupplyFixedTarget: 'number.fixed_system_supply_set_point',
  systemSupplyFixedEnabled: 'switch.enable_fixed_system_supply_set_point',
  comfortWheel: 'number.comfort_wheel_setting',

  // External heater control
  extHeaterAlwaysEnableTemp: 'input_number.ext_heater_always_enable_temp',
  extHeaterAlwaysDisableTemp: 'input_number.ext_heater_always_disable_temp',
  extHeaterOffpeakEnableTemp: 'input_number.ext_heater_offpeak_enable_temp',
  extHeaterOffpeakDisableTemp: 'input_number.ext_heater_offpeak_disable_temp',
  extHeaterDuration: 'input_number.ext_heater_duration_minutes',
  extHeaterManualControl: 'input_boolean.ext_heater_manual_control',

  // Cold weather mode
  coldWeatherMode: 'input_boolean.pool_heating_cold_weather_mode',
  coldEnabledHours: 'input_text.pool_heating_cold_enabled_hours',
  coldBlockDuration: 'input_number.pool_heating_cold_block_duration',
  coldPreCirculation: 'input_number.pool_heating_cold_pre_circulation',
  coldPostCirculation: 'input_number.pool_heating_cold_post_circulation',
} as const;

// Block entities (1-10)
const getBlockEntities = (n: number) => ({
  start: `input_datetime.pool_heat_block_${n}_start`,
  heatingStart: `input_datetime.pool_heat_block_${n}_heating_start`,
  end: `input_datetime.pool_heat_block_${n}_end`,
  price: `input_number.pool_heat_block_${n}_price`,
  cost: `input_number.pool_heat_block_${n}_cost`,
  enabled: `input_boolean.pool_heat_block_${n}_enabled`,
  costExceeded: `input_boolean.pool_heat_block_${n}_cost_exceeded`,
});

// Fixed preheat duration (15 minutes before heating starts)
const PREHEAT_DURATION = 15;

// Default state when disconnected or entities unavailable
const defaultState: SystemState = {
  heatPump: {
    heatEnabled: false,
    tapWaterEnabled: false,
    compressorGear: 0,
    compressorRpm: 0,
    brineInTemp: 0,
    brineOutTemp: 0,
    brineCirculationSpeed: 0,
    condenserInTemp: 0,
    condenserOutTemp: 0,
    condenserDeltaT: 0,
    outdoorTemp: 0,
    heatpumpMode: 'Off',
    dischargePipeTemp: 0,
    suctionGasTemp: 0,
    liquidLineTemp: 0,
  },
  poolHeating: {
    enabled: false,
    active: false,
    inHeatingWindow: false,
    targetTemp: 27.5,
    nightComplete: false,
    returnLineTemp: 0,
    heatExchangerDeltaT: 0,
    electricalPower: 0,
    dailyEnergy: 0,
    dailyCost: 0,
    monthlyCost: 0,
    averagePrice: 0,
  },
  valve: {
    position: 'radiators',
    transitioning: false,
  },
  schedule: {
    blocks: [],
    nordpoolAvailable: false,
    currentPrice: 0,
    scheduledMinutes: 0,
    totalCost: 0,
    costLimitApplied: false,
    parameters: {
      minBlockDuration: 30,
      maxBlockDuration: 45,
      totalHours: 2,
      maxCostEur: null,
      minBreakDuration: 60,
      coldWeatherMode: false,
      coldEnabledHours: '21,22,23,0,1,2,3,4,5,6',
      coldBlockDuration: 5,
      coldPreCirculation: 5,
      coldPostCirculation: 5,
    },
  },
  gearSettings: {
    heating: { min: 1, max: 10 },
    pool: { min: 1, max: 10 },
    tapWater: { min: 1, max: 10 },
  },
  tapWater: {
    topTemp: 0,
    lowerTemp: 0,
    weightedTemp: 0,
    startTemp: 45,
    stopTemp: 55,
  },
  hotGasSettings: {
    pumpStartTemp: 70,
    lowerStopLimit: 60,
    upperStopLimit: 95,
  },
  heatingCurve: {
    maxLimitation: 55,
    minLimitation: 20,
  },
  peakPower: {
    daytimeHeaterStart: -10,
    daytimeHeaterStop: 0,
    nighttimeHeaterStart: -6,
    nighttimeHeaterStop: 4,
    daytimeStartTime: '06:40',
    nighttimeStartTime: '21:00',
  },
  systemSupply: {
    supplyTemp: 0,
    curveTarget: 0,
    fixedTarget: 30,
    fixedModeEnabled: false,
    comfortWheel: 20,
  },
  externalHeater: {
    alwaysEnableTemp: -15,
    alwaysDisableTemp: -10,
    offpeakEnableTemp: -5,
    offpeakDisableTemp: -2,
    durationMinutes: 30,
    manualControl: false,
  },
};

// Helper to parse numeric state
function parseNumber(state: HAEntityState | undefined): number {
  if (!state || state.state === 'unknown' || state.state === 'unavailable') {
    return 0;
  }
  const num = parseFloat(state.state);
  return isNaN(num) ? 0 : num;
}

// Helper to parse boolean state
function parseBoolean(state: HAEntityState | undefined): boolean {
  if (!state) return false;
  return state.state === 'on' || state.state === 'true';
}

// Helper to parse heat pump mode
function parseHeatPumpMode(state: HAEntityState | undefined): 'Heat' | 'Cool' | 'Off' {
  if (!state) return 'Off';
  const mode = state.state.toLowerCase();
  if (mode === 'heat' || mode === 'heating') return 'Heat';
  if (mode === 'cool' || mode === 'cooling') return 'Cool';
  return 'Off';
}

// Helper to parse time from input_datetime (returns HH:MM for display)
function parseTime(state: HAEntityState | undefined): string {
  if (!state || state.state === 'unknown' || state.state === 'unavailable') return '';
  const timeStr = state.state;

  // ISO format: 2025-11-30T22:00:00+00:00
  if (timeStr.includes('T')) {
    const match = timeStr.match(/T(\d{2}:\d{2})/);
    return match ? match[1] : '';
  }

  // Time-only format: HH:MM:SS or HH:MM
  if (/^\d{2}:\d{2}/.test(timeStr)) {
    return timeStr.substring(0, 5);
  }

  // input_datetime with has_time only stores time in attributes
  if (state.attributes?.hour !== undefined && state.attributes?.minute !== undefined) {
    const h = String(state.attributes.hour).padStart(2, '0');
    const m = String(state.attributes.minute).padStart(2, '0');
    return `${h}:${m}`;
  }

  return '';
}

// Helper to get full ISO datetime string for comparison
function parseDateTime(state: HAEntityState | undefined): string {
  if (!state || state.state === 'unknown' || state.state === 'unavailable') return '';
  return state.state;
}

// Helper to calculate block duration in minutes
function calculateBlockDuration(start: string, end: string): number {
  if (!start || !end || !start.includes(':') || !end.includes(':')) return 0;

  const [startH, startM] = start.split(':').map(Number);
  const [endH, endM] = end.split(':').map(Number);

  if (isNaN(startH) || isNaN(startM) || isNaN(endH) || isNaN(endM)) return 0;

  let startMins = startH * 60 + startM;
  let endMins = endH * 60 + endM;
  // Handle midnight crossing
  if (endMins < startMins) {
    endMins += 24 * 60;
  }
  return endMins - startMins;
}

export type GearCircuit = 'heating' | 'pool' | 'tapWater';
export type GearLimitType = 'min' | 'max';
export type TapWaterSetting = 'startTemp' | 'stopTemp';
export type HotGasSetting = 'pumpStartTemp' | 'lowerStopLimit' | 'upperStopLimit';
export type HeatingCurveSetting = 'maxLimitation' | 'minLimitation';
export type PeakPowerSetting = 'daytimeHeaterStart' | 'daytimeHeaterStop' | 'nighttimeHeaterStart' | 'nighttimeHeaterStop';
export type PeakPowerTime = 'daytimeStart' | 'nighttimeStart';
export type ExternalHeaterSetting = 'alwaysEnableTemp' | 'alwaysDisableTemp' | 'offpeakEnableTemp' | 'offpeakDisableTemp' | 'durationMinutes';

export interface UseHomeAssistantReturn {
  state: SystemState;
  connected: boolean;
  error: string | null;
  setHeatEnabled: (enabled: boolean) => Promise<void>;
  setTapWaterEnabled: (enabled: boolean) => Promise<void>;
  setPoolHeatingEnabled: (enabled: boolean) => Promise<void>;
  setPoolTargetTemp: (temp: number) => Promise<void>;
  toggleValve: () => Promise<void>;
  setPoolActive: (active: boolean) => Promise<void>;
  setBlockEnabled: (blockNumber: number, enabled: boolean) => Promise<void>;
  setGearLimit: (circuit: GearCircuit, type: GearLimitType, value: number) => Promise<void>;
  setTapWaterSetting: (setting: TapWaterSetting, value: number) => Promise<void>;
  setHotGasSetting: (setting: HotGasSetting, value: number) => Promise<void>;
  setHeatingCurveSetting: (setting: HeatingCurveSetting, value: number) => Promise<void>;
  // Schedule parameter controls
  setScheduleParameters: (params: Partial<ScheduleParameters>) => Promise<void>;
  recalculateSchedule: () => Promise<boolean>;
  isInHeatingWindow: () => boolean;
  // Peak power avoidance controls
  setPeakPowerSetting: (setting: PeakPowerSetting, value: number) => Promise<void>;
  setPeakPowerTime: (setting: PeakPowerTime, time: string) => Promise<void>;
  // Fixed supply and comfort wheel controls
  setFixedSupplyEnabled: (enabled: boolean) => Promise<void>;
  setFixedSupplyTarget: (value: number) => Promise<void>;
  setComfortWheel: (value: number) => Promise<void>;
  // External heater controls
  setExternalHeaterSetting: (setting: ExternalHeaterSetting, value: number) => Promise<void>;
  setExternalHeaterManualControl: (enabled: boolean) => Promise<void>;
}

export function useHomeAssistant(): UseHomeAssistantReturn {
  const [state, setState] = useState<SystemState>(defaultState);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const entityStates = useRef<Map<string, HAEntityState>>(new Map());
  const ws = useRef(getHAWebSocket());

  // Build state from entity states
  const buildState = useCallback((): SystemState => {
    const get = (id: string) => entityStates.current.get(id);

    // Heat pump state
    const compressorSpeed = parseNumber(get(ENTITIES.compressorSpeed));
    const condenserOut = parseNumber(get(ENTITIES.condenserOut));
    const condenserIn = parseNumber(get(ENTITIES.condenserIn));
    // Derive running state from temperatures if compressor entity not found
    const isRunning = compressorSpeed > 0 || (condenserOut > 30 && condenserOut > condenserIn);

    const heatPump: HeatPumpState = {
      heatEnabled: isRunning,
      tapWaterEnabled: false, // Not tracked in current setup
      compressorGear: parseNumber(get(ENTITIES.compressorGear)),
      compressorRpm: compressorSpeed,
      brineInTemp: parseNumber(get(ENTITIES.brineIn)),
      brineOutTemp: parseNumber(get(ENTITIES.brineOut)),
      brineCirculationSpeed: parseNumber(get(ENTITIES.brinePumpSpeed)),
      condenserInTemp: condenserIn,
      condenserOutTemp: condenserOut,
      condenserDeltaT: parseNumber(get(ENTITIES.deltaT)),
      outdoorTemp: parseNumber(get(ENTITIES.outdoor)),
      // Derive mode: if running with heat (condenserOut > condenserIn), it's heating
      heatpumpMode: isRunning ? (condenserOut > condenserIn ? 'Heat' : 'Cool') : parseHeatPumpMode(get(ENTITIES.heatPumpMode)),
      // Hot gas / refrigerant temps
      dischargePipeTemp: parseNumber(get(ENTITIES.dischargePipeTemp)),
      suctionGasTemp: parseNumber(get(ENTITIES.suctionGasTemp)),
      liquidLineTemp: parseNumber(get(ENTITIES.liquidLineTemp)),
    };

    // Pool heating state
    const poolHeating: PoolHeatingState = {
      enabled: parseBoolean(get(ENTITIES.poolEnabled)),
      active: parseBoolean(get(ENTITIES.poolActive)),
      inHeatingWindow: parseBoolean(get(ENTITIES.inHeatingWindow)),
      targetTemp: parseNumber(get(ENTITIES.poolTargetTemp)) || 27.5,
      nightComplete: parseBoolean(get(ENTITIES.nightComplete)),
      returnLineTemp: parseNumber(get(ENTITIES.returnLineTemp)),
      heatExchangerDeltaT: parseNumber(get(ENTITIES.deltaT)),
      electricalPower: parseNumber(get(ENTITIES.electricalPower)),
      dailyEnergy: parseNumber(get(ENTITIES.dailyEnergy)),
      dailyCost: parseNumber(get(ENTITIES.dailyCost)),
      monthlyCost: parseNumber(get(ENTITIES.monthlyCost)),
      averagePrice: parseNumber(get(ENTITIES.avgPrice)),
    };

    // Valve state - prevention OFF and pump ON means heating pool
    const preventionOff = !parseBoolean(get(ENTITIES.heatingPrevention));
    const pumpOn = parseBoolean(get(ENTITIES.circulationPump));
    const valve: ValveState = {
      position: preventionOff && pumpOn ? 'pool' : 'radiators',
      transitioning: false,
    };

    // Schedule blocks (1-10)
    const blocks: PriceBlock[] = [];
    for (let n = 1; n <= 10; n++) {
      const blockEntities = getBlockEntities(n);
      const start = parseTime(get(blockEntities.start));  // Preheat start time
      const heatingStart = parseTime(get(blockEntities.heatingStart));  // Actual heating start
      const end = parseTime(get(blockEntities.end));
      const endDateTime = parseDateTime(get(blockEntities.end));
      const price = parseNumber(get(blockEntities.price));
      const costEur = parseNumber(get(blockEntities.cost));
      const enabled = parseBoolean(get(blockEntities.enabled));
      const costExceeded = parseBoolean(get(blockEntities.costExceeded));
      // Duration is heating time only (heatingStart to end), preheat is separate
      const duration = heatingStart && end ? calculateBlockDuration(heatingStart, end) : calculateBlockDuration(start, end);

      // Only include blocks with valid times (non-empty start/end and valid duration)
      if (start && end && duration > 0) {
        blocks.push({
          start,
          heatingStart: heatingStart || start,  // Fallback to start if heatingStart not available
          end,
          endDateTime,
          price,
          costEur,
          duration,
          preheatDuration: PREHEAT_DURATION,
          enabled,
          costExceeded,
        });
      }
    }

    // Schedule parameters
    const maxCostVal = parseNumber(get(ENTITIES.maxCostEur));
    const parameters: ScheduleParameters = {
      minBlockDuration: parseNumber(get(ENTITIES.minBlockDuration)) || 30,
      maxBlockDuration: parseNumber(get(ENTITIES.maxBlockDuration)) || 45,
      totalHours: parseNumber(get(ENTITIES.totalHours)) || 2,
      maxCostEur: maxCostVal > 0 ? maxCostVal : null,
      minBreakDuration: parseNumber(get(ENTITIES.minBreakDuration)) || 60,
      // Cold weather mode
      coldWeatherMode: parseBoolean(get(ENTITIES.coldWeatherMode)),
      coldEnabledHours: get(ENTITIES.coldEnabledHours) || '21,22,23,0,1,2,3,4,5,6',
      coldBlockDuration: parseNumber(get(ENTITIES.coldBlockDuration)) || 5,
      coldPreCirculation: parseNumber(get(ENTITIES.coldPreCirculation)) || 5,
      coldPostCirculation: parseNumber(get(ENTITIES.coldPostCirculation)) || 5,
    };

    const schedule: ScheduleState = {
      blocks,
      nordpoolAvailable: parseBoolean(get(ENTITIES.nordpoolAvailable)),
      // Nordpool returns EUR/kWh, convert to cents/kWh for display
      currentPrice: parseNumber(get(ENTITIES.nordpoolPrice)) * 100,
      scheduledMinutes: blocks.reduce((sum, b) => sum + b.duration, 0),
      totalCost: parseNumber(get(ENTITIES.totalCost)),
      costLimitApplied: parseBoolean(get(ENTITIES.costLimitApplied)),
      parameters,
    };

    // Gear settings from Thermia Genesis
    const gearSettings: GearSettings = {
      heating: {
        min: parseNumber(get(ENTITIES.minGearHeating)) || 1,
        max: parseNumber(get(ENTITIES.maxGearHeating)) || 10,
      },
      pool: {
        min: parseNumber(get(ENTITIES.minGearPool)) || 1,
        max: parseNumber(get(ENTITIES.maxGearPool)) || 10,
      },
      tapWater: {
        min: parseNumber(get(ENTITIES.minGearTapWater)) || 1,
        max: parseNumber(get(ENTITIES.maxGearTapWater)) || 10,
      },
    };

    // Tap water state
    const tapWater: TapWaterState = {
      topTemp: parseNumber(get(ENTITIES.tapWaterTop)),
      lowerTemp: parseNumber(get(ENTITIES.tapWaterLower)),
      weightedTemp: parseNumber(get(ENTITIES.tapWaterWeighted)),
      startTemp: parseNumber(get(ENTITIES.tapWaterStartTemp)) || 45,
      stopTemp: parseNumber(get(ENTITIES.tapWaterStopTemp)) || 55,
    };

    // Hot gas pump settings
    const hotGasSettings: HotGasSettings = {
      pumpStartTemp: parseNumber(get(ENTITIES.hotGasPumpStartTemp)) || 70,
      lowerStopLimit: parseNumber(get(ENTITIES.hotGasLowerStopLimit)) || 60,
      upperStopLimit: parseNumber(get(ENTITIES.hotGasUpperStopLimit)) || 95,
    };

    // Heating curve settings
    const heatingCurve: HeatingCurveSettings = {
      maxLimitation: parseNumber(get(ENTITIES.heatingCurveMax)) || 55,
      minLimitation: parseNumber(get(ENTITIES.heatingCurveMin)) || 20,
    };

    // Peak power avoidance settings
    const peakPower: PeakPowerSettings = {
      daytimeHeaterStart: parseNumber(get(ENTITIES.peakPowerDaytimeHeaterStart)) || -10,
      daytimeHeaterStop: parseNumber(get(ENTITIES.peakPowerDaytimeHeaterStop)) || 0,
      nighttimeHeaterStart: parseNumber(get(ENTITIES.peakPowerNighttimeHeaterStart)) || -6,
      nighttimeHeaterStop: parseNumber(get(ENTITIES.peakPowerNighttimeHeaterStop)) || 4,
      daytimeStartTime: parseTime(get(ENTITIES.peakPowerDaytimeStart)) || '06:40',
      nighttimeStartTime: parseTime(get(ENTITIES.peakPowerNighttimeStart)) || '21:00',
    };

    // System supply temperatures
    const systemSupply: SystemSupplyState = {
      supplyTemp: parseNumber(get(ENTITIES.systemSupplyTemp)),
      curveTarget: parseNumber(get(ENTITIES.systemSupplyCurveTarget)),
      fixedTarget: parseNumber(get(ENTITIES.systemSupplyFixedTarget)) || 30,
      fixedModeEnabled: parseBoolean(get(ENTITIES.systemSupplyFixedEnabled)),
      comfortWheel: parseNumber(get(ENTITIES.comfortWheel)) || 20,
    };

    // External heater settings
    const externalHeater: ExternalHeaterSettings = {
      alwaysEnableTemp: parseNumber(get(ENTITIES.extHeaterAlwaysEnableTemp)) || -15,
      alwaysDisableTemp: parseNumber(get(ENTITIES.extHeaterAlwaysDisableTemp)) || -10,
      offpeakEnableTemp: parseNumber(get(ENTITIES.extHeaterOffpeakEnableTemp)) || -5,
      offpeakDisableTemp: parseNumber(get(ENTITIES.extHeaterOffpeakDisableTemp)) || -2,
      durationMinutes: parseNumber(get(ENTITIES.extHeaterDuration)) || 30,
      manualControl: parseBoolean(get(ENTITIES.extHeaterManualControl)),
    };

    return { heatPump, poolHeating, valve, schedule, gearSettings, tapWater, hotGasSettings, heatingCurve, peakPower, systemSupply, externalHeater };
  }, []);

  // Initial connection and state fetch
  useEffect(() => {
    const connect = async () => {
      try {
        await ws.current.connect();
        setConnected(true);
        setError(null);

        // Fetch initial states
        const states = await ws.current.getStates();
        states.forEach(s => entityStates.current.set(s.entity_id, s));

        // Debug: log relevant entities
        if (import.meta.env.DEV) {
          console.log('[HA] Connected, found entities:');
          const patterns = ['thermia', 'genesis', 'compressor', 'brine', 'condenser', 'pool', 'nordpool', 'heat_block', 'outdoor'];
          const relevant = states.filter(s =>
            patterns.some(p => s.entity_id.toLowerCase().includes(p))
          );
          relevant.forEach(s => {
            console.log(`  ${s.entity_id}: ${s.state}`, s.attributes);
          });
        }

        setState(buildState());
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Connection failed');
        setConnected(false);
      }
    };

    connect();

    // Subscribe to state changes
    const unsubscribeState = ws.current.onStateChange((entityId, newState) => {
      entityStates.current.set(entityId, newState);
      setState(buildState());
    });

    // Subscribe to connection changes
    const unsubscribeConnection = ws.current.onConnectionChange((isConnected) => {
      setConnected(isConnected);
      if (!isConnected) {
        setError('Disconnected from Home Assistant');
      } else {
        setError(null);
      }
    });

    return () => {
      unsubscribeState();
      unsubscribeConnection();
    };
  }, [buildState]);

  // Control functions
  const setHeatEnabled = useCallback(async (_enabled: boolean) => {
    // Heat pump enable/disable not directly controllable via this setup
    // This would need Thermia integration service calls
    console.warn('Heat pump enable/disable not implemented');
  }, []);

  const setTapWaterEnabled = useCallback(async (_enabled: boolean) => {
    // Tap water enable/disable not directly controllable
    console.warn('Tap water enable/disable not implemented');
  }, []);

  const setPoolHeatingEnabled = useCallback(async (enabled: boolean) => {
    await ws.current.callService('input_boolean', enabled ? 'turn_on' : 'turn_off', {
      entity_id: ENTITIES.poolEnabled,
    });
  }, []);

  const setPoolTargetTemp = useCallback(async (temp: number) => {
    await ws.current.callService('input_number', 'set_value', {
      entity_id: ENTITIES.poolTargetTemp,
      value: temp,
    });
  }, []);

  const toggleValve = useCallback(async () => {
    // Toggle pool heating by controlling both Shelly switches
    // Prevention OFF + Pump ON = Pool heating active
    // Prevention ON + Pump OFF = Radiators (normal heating)
    const currentPrevention = parseBoolean(entityStates.current.get(ENTITIES.heatingPrevention));
    const goingToPool = currentPrevention; // If prevention is ON, we're switching TO pool

    if (goingToPool) {
      // Switch to pool: turn OFF prevention, turn ON pump
      await ws.current.callService('switch', 'turn_off', {
        entity_id: ENTITIES.heatingPrevention,
      });
      await ws.current.callService('switch', 'turn_on', {
        entity_id: ENTITIES.circulationPump,
      });
    } else {
      // Switch to radiators: turn ON prevention, turn OFF pump
      await ws.current.callService('switch', 'turn_on', {
        entity_id: ENTITIES.heatingPrevention,
      });
      await ws.current.callService('switch', 'turn_off', {
        entity_id: ENTITIES.circulationPump,
      });
    }
  }, []);

  const setPoolActive = useCallback(async (active: boolean) => {
    // Directly set pool heating state
    if (active) {
      await ws.current.callService('switch', 'turn_off', {
        entity_id: ENTITIES.heatingPrevention,
      });
      await ws.current.callService('switch', 'turn_on', {
        entity_id: ENTITIES.circulationPump,
      });
    } else {
      await ws.current.callService('switch', 'turn_on', {
        entity_id: ENTITIES.heatingPrevention,
      });
      await ws.current.callService('switch', 'turn_off', {
        entity_id: ENTITIES.circulationPump,
      });
    }
  }, []);

  const setBlockEnabled = useCallback(async (blockNumber: number, enabled: boolean) => {
    const entityId = `input_boolean.pool_heat_block_${blockNumber}_enabled`;
    await ws.current.callService('input_boolean', enabled ? 'turn_on' : 'turn_off', {
      entity_id: entityId,
    });
  }, []);

  const setGearLimit = useCallback(async (circuit: GearCircuit, type: GearLimitType, value: number) => {
    // Map circuit and type to entity ID
    const entityMap: Record<GearCircuit, Record<GearLimitType, string>> = {
      heating: {
        min: ENTITIES.minGearHeating,
        max: ENTITIES.maxGearHeating,
      },
      pool: {
        min: ENTITIES.minGearPool,
        max: ENTITIES.maxGearPool,
      },
      tapWater: {
        min: ENTITIES.minGearTapWater,
        max: ENTITIES.maxGearTapWater,
      },
    };

    const entityId = entityMap[circuit][type];
    await ws.current.callService('number', 'set_value', {
      entity_id: entityId,
      value: value,
    });
  }, []);

  const setTapWaterSetting = useCallback(async (setting: TapWaterSetting, value: number) => {
    const entityMap: Record<TapWaterSetting, string> = {
      startTemp: ENTITIES.tapWaterStartTemp,
      stopTemp: ENTITIES.tapWaterStopTemp,
    };
    await ws.current.callService('number', 'set_value', {
      entity_id: entityMap[setting],
      value: value,
    });
  }, []);

  const setHotGasSetting = useCallback(async (setting: HotGasSetting, value: number) => {
    const entityMap: Record<HotGasSetting, string> = {
      pumpStartTemp: ENTITIES.hotGasPumpStartTemp,
      lowerStopLimit: ENTITIES.hotGasLowerStopLimit,
      upperStopLimit: ENTITIES.hotGasUpperStopLimit,
    };
    await ws.current.callService('number', 'set_value', {
      entity_id: entityMap[setting],
      value: value,
    });
  }, []);

  const setHeatingCurveSetting = useCallback(async (setting: HeatingCurveSetting, value: number) => {
    const entityMap: Record<HeatingCurveSetting, string> = {
      maxLimitation: ENTITIES.heatingCurveMax,
      minLimitation: ENTITIES.heatingCurveMin,
    };
    await ws.current.callService('number', 'set_value', {
      entity_id: entityMap[setting],
      value: value,
    });
  }, []);

  const setScheduleParameters = useCallback(async (params: Partial<ScheduleParameters>) => {
    const calls: Promise<void>[] = [];

    if (params.minBlockDuration !== undefined) {
      calls.push(
        ws.current.callService('input_number', 'set_value', {
          entity_id: ENTITIES.minBlockDuration,
          value: params.minBlockDuration,
        })
      );
    }

    if (params.maxBlockDuration !== undefined) {
      calls.push(
        ws.current.callService('input_number', 'set_value', {
          entity_id: ENTITIES.maxBlockDuration,
          value: params.maxBlockDuration,
        })
      );
    }

    if (params.totalHours !== undefined) {
      calls.push(
        ws.current.callService('input_number', 'set_value', {
          entity_id: ENTITIES.totalHours,
          value: params.totalHours,
        })
      );
    }

    // maxCostEur: undefined means "no limit" = set to 0
    if (params.maxCostEur !== undefined || 'maxCostEur' in params) {
      calls.push(
        ws.current.callService('input_number', 'set_value', {
          entity_id: ENTITIES.maxCostEur,
          value: params.maxCostEur ?? 0,
        })
      );
    }

    // Cold weather mode parameters
    if (params.coldWeatherMode !== undefined) {
      calls.push(
        ws.current.callService('input_boolean', params.coldWeatherMode ? 'turn_on' : 'turn_off', {
          entity_id: ENTITIES.coldWeatherMode,
        })
      );
    }

    if (params.coldEnabledHours !== undefined) {
      calls.push(
        ws.current.callService('input_text', 'set_value', {
          entity_id: ENTITIES.coldEnabledHours,
          value: params.coldEnabledHours,
        })
      );
    }

    if (params.coldBlockDuration !== undefined) {
      calls.push(
        ws.current.callService('input_number', 'set_value', {
          entity_id: ENTITIES.coldBlockDuration,
          value: params.coldBlockDuration,
        })
      );
    }

    if (params.coldPreCirculation !== undefined) {
      calls.push(
        ws.current.callService('input_number', 'set_value', {
          entity_id: ENTITIES.coldPreCirculation,
          value: params.coldPreCirculation,
        })
      );
    }

    if (params.coldPostCirculation !== undefined) {
      calls.push(
        ws.current.callService('input_number', 'set_value', {
          entity_id: ENTITIES.coldPostCirculation,
          value: params.coldPostCirculation,
        })
      );
    }

    await Promise.all(calls);
  }, []);

  const recalculateSchedule = useCallback(async (): Promise<boolean> => {
    // Try to calculate a new schedule (may fail if tomorrow's prices not available)
    // Duration is handled at schedule creation time, cost constraint is applied internally.
    // If calculation fails (no prices), parameters are saved for next calculation.
    try {
      await ws.current.callService('pyscript', 'calculate_pool_heating_schedule', {});
      return true; // Schedule recalculated successfully
    } catch (e) {
      console.warn('calculate_pool_heating_schedule failed (prices not available?):', e);
      return false; // Parameters saved, will apply at next calculation
    }
  }, []);

  const isInHeatingWindow = useCallback(() => {
    const now = new Date();
    const hour = now.getHours();
    // Heating window is 21:00-07:00
    return hour >= 21 || hour < 7;
  }, []);

  const setPeakPowerSetting = useCallback(async (setting: PeakPowerSetting, value: number) => {
    const entityMap: Record<PeakPowerSetting, string> = {
      daytimeHeaterStart: ENTITIES.peakPowerDaytimeHeaterStart,
      daytimeHeaterStop: ENTITIES.peakPowerDaytimeHeaterStop,
      nighttimeHeaterStart: ENTITIES.peakPowerNighttimeHeaterStart,
      nighttimeHeaterStop: ENTITIES.peakPowerNighttimeHeaterStop,
    };
    await ws.current.callService('input_number', 'set_value', {
      entity_id: entityMap[setting],
      value: value,
    });
  }, []);

  const setPeakPowerTime = useCallback(async (setting: PeakPowerTime, time: string) => {
    const entityMap: Record<PeakPowerTime, string> = {
      daytimeStart: ENTITIES.peakPowerDaytimeStart,
      nighttimeStart: ENTITIES.peakPowerNighttimeStart,
    };
    await ws.current.callService('input_datetime', 'set_datetime', {
      entity_id: entityMap[setting],
      time: time + ':00', // Add seconds for HA format
    });
  }, []);

  const setFixedSupplyEnabled = useCallback(async (enabled: boolean) => {
    await ws.current.callService('switch', enabled ? 'turn_on' : 'turn_off', {
      entity_id: ENTITIES.systemSupplyFixedEnabled,
    });
  }, []);

  const setFixedSupplyTarget = useCallback(async (value: number) => {
    await ws.current.callService('number', 'set_value', {
      entity_id: ENTITIES.systemSupplyFixedTarget,
      value: value,
    });
  }, []);

  const setComfortWheel = useCallback(async (value: number) => {
    await ws.current.callService('number', 'set_value', {
      entity_id: ENTITIES.comfortWheel,
      value: value,
    });
  }, []);

  const setExternalHeaterSetting = useCallback(async (setting: ExternalHeaterSetting, value: number) => {
    const entityMap: Record<ExternalHeaterSetting, string> = {
      alwaysEnableTemp: ENTITIES.extHeaterAlwaysEnableTemp,
      alwaysDisableTemp: ENTITIES.extHeaterAlwaysDisableTemp,
      offpeakEnableTemp: ENTITIES.extHeaterOffpeakEnableTemp,
      offpeakDisableTemp: ENTITIES.extHeaterOffpeakDisableTemp,
      durationMinutes: ENTITIES.extHeaterDuration,
    };
    await ws.current.callService('input_number', 'set_value', {
      entity_id: entityMap[setting],
      value: value,
    });
  }, []);

  const setExternalHeaterManualControl = useCallback(async (enabled: boolean) => {
    await ws.current.callService('input_boolean', enabled ? 'turn_on' : 'turn_off', {
      entity_id: ENTITIES.extHeaterManualControl,
    });
  }, []);

  return {
    state,
    connected,
    error,
    setHeatEnabled,
    setTapWaterEnabled,
    setPoolHeatingEnabled,
    setPoolTargetTemp,
    toggleValve,
    setPoolActive,
    setBlockEnabled,
    setGearLimit,
    setTapWaterSetting,
    setHotGasSetting,
    setHeatingCurveSetting,
    setScheduleParameters,
    recalculateSchedule,
    isInHeatingWindow,
    setPeakPowerSetting,
    setPeakPowerTime,
    setFixedSupplyEnabled,
    setFixedSupplyTarget,
    setComfortWheel,
    setExternalHeaterSetting,
    setExternalHeaterManualControl,
  };
}
