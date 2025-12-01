import { useState, useCallback } from 'react';
import { SystemState } from '@/types/heating';

// Mock initial state based on the screenshot data
const initialState: SystemState = {
  heatPump: {
    heatEnabled: true,
    tapWaterEnabled: true,
    compressorGear: 2.0,
    compressorRpm: 1999,
    brineInTemp: 3.56,
    brineOutTemp: 0.27,
    brineCirculationSpeed: 55.56,
    condenserInTemp: 36.69,
    condenserOutTemp: 40.16,
    outdoorTemp: 5.75,
    heatpumpMode: 'Heat',
  },
  poolHeating: {
    enabled: true,
    active: false,
    inHeatingWindow: false,
    targetTemp: 27.5,
    returnLineTemp: 24.08,
    heatExchangerDeltaT: 3.5,
    electricalPower: 0,
    dailyEnergy: 0.007,
    dailyCost: 0.002,
    monthlyCost: 0.002,
    averagePrice: 1.86,
  },
  valve: {
    position: 'radiators',
    transitioning: false,
  },
  schedule: {
    blocks: [
      { start: '01:30', end: '02:00', endDateTime: '2025-12-02T02:00:00+02:00', price: 2.05, duration: 30, enabled: true },
      { start: '02:30', end: '03:00', endDateTime: '2025-12-02T03:00:00+02:00', price: 1.8, duration: 30, enabled: true },
      { start: '03:30', end: '04:00', endDateTime: '2025-12-02T04:00:00+02:00', price: 1.8, duration: 30, enabled: true },
      { start: '05:00', end: '05:30', endDateTime: '2025-12-02T05:30:00+02:00', price: 1.8, duration: 30, enabled: true },
    ],
    nordpoolAvailable: true,
    currentPrice: 7.0,
    scheduledMinutes: 120,
  },
};

export function useSystemState() {
  const [state, setState] = useState<SystemState>(initialState);

  const setHeatEnabled = useCallback((enabled: boolean) => {
    setState(prev => ({
      ...prev,
      heatPump: { ...prev.heatPump, heatEnabled: enabled },
    }));
  }, []);

  const setTapWaterEnabled = useCallback((enabled: boolean) => {
    setState(prev => ({
      ...prev,
      heatPump: { ...prev.heatPump, tapWaterEnabled: enabled },
    }));
  }, []);

  const setPoolHeatingEnabled = useCallback((enabled: boolean) => {
    setState(prev => ({
      ...prev,
      poolHeating: { ...prev.poolHeating, enabled },
    }));
  }, []);

  const setPoolTargetTemp = useCallback((temp: number) => {
    setState(prev => ({
      ...prev,
      poolHeating: { ...prev.poolHeating, targetTemp: temp },
    }));
  }, []);

  const toggleValve = useCallback(() => {
    setState(prev => ({
      ...prev,
      valve: {
        ...prev.valve,
        transitioning: true,
      },
    }));

    // Simulate valve transition
    setTimeout(() => {
      setState(prev => ({
        ...prev,
        valve: {
          position: prev.valve.position === 'pool' ? 'radiators' : 'pool',
          transitioning: false,
        },
        poolHeating: {
          ...prev.poolHeating,
          active: prev.valve.position === 'radiators',
        },
      }));
    }, 1500);
  }, []);

  const setPoolActive = useCallback((active: boolean) => {
    setState(prev => ({
      ...prev,
      poolHeating: { ...prev.poolHeating, active },
      valve: { ...prev.valve, position: active ? 'pool' : 'radiators' },
    }));
  }, []);

  return {
    state,
    setHeatEnabled,
    setTapWaterEnabled,
    setPoolHeatingEnabled,
    setPoolTargetTemp,
    toggleValve,
    setPoolActive,
  };
}
