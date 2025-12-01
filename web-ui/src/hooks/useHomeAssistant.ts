import { useState, useEffect, useCallback, useRef } from 'react';
import { SystemState, HeatPumpState, PoolHeatingState, ValveState, ScheduleState, PriceBlock } from '@/types/heating';
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
  brinePumpSpeed: 'sensor.brine_circulation_pump_speed',
  heatPumpMode: 'sensor.heat_pump_mode',

  // Pool heating
  poolEnabled: 'input_boolean.pool_heating_enabled',
  poolActive: 'binary_sensor.pool_heating_active',
  inHeatingWindow: 'binary_sensor.pool_in_heating_window',
  poolTargetTemp: 'input_number.pool_target_temperature',
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
} as const;

// Block entities (1-4)
const getBlockEntities = (n: number) => ({
  start: `input_datetime.pool_heat_block_${n}_start`,
  end: `input_datetime.pool_heat_block_${n}_end`,
  price: `input_number.pool_heat_block_${n}_price`,
});

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
  },
  poolHeating: {
    enabled: false,
    active: false,
    inHeatingWindow: false,
    targetTemp: 27.5,
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

// Helper to parse time from input_datetime
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
      compressorGear: 0, // Not tracked
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
    };

    // Pool heating state
    const poolHeating: PoolHeatingState = {
      enabled: parseBoolean(get(ENTITIES.poolEnabled)),
      active: parseBoolean(get(ENTITIES.poolActive)),
      inHeatingWindow: parseBoolean(get(ENTITIES.inHeatingWindow)),
      targetTemp: parseNumber(get(ENTITIES.poolTargetTemp)) || 27.5,
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

    // Schedule blocks
    const blocks: PriceBlock[] = [];
    for (let n = 1; n <= 4; n++) {
      const blockEntities = getBlockEntities(n);
      const start = parseTime(get(blockEntities.start));
      const end = parseTime(get(blockEntities.end));
      const price = parseNumber(get(blockEntities.price));
      const duration = calculateBlockDuration(start, end);

      // Only include blocks with valid times (non-empty start/end and valid duration)
      if (start && end && duration > 0) {
        blocks.push({
          start,
          end,
          price,
          duration,
        });
      }
    }

    const schedule: ScheduleState = {
      blocks,
      nordpoolAvailable: parseBoolean(get(ENTITIES.nordpoolAvailable)),
      currentPrice: parseNumber(get(ENTITIES.nordpoolPrice)),
      scheduledMinutes: blocks.reduce((sum, b) => sum + b.duration, 0),
    };

    return { heatPump, poolHeating, valve, schedule };
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
  };
}
