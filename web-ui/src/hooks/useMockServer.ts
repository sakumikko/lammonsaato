/**
 * Hook for connecting to the mock HA server for testing.
 *
 * This hook provides the same interface as useHomeAssistant but connects
 * to the Python mock server instead of a real Home Assistant instance.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { ScheduleState, ScheduleParameters } from '@/types/heating';

const MOCK_SERVER_URL = 'http://localhost:8765';
const MOCK_SERVER_WS = 'ws://localhost:8765/ws';

export type PriceScenario =
  | 'typical_winter'
  | 'cheap_night'
  | 'expensive_night'
  | 'negative_prices'
  | 'flat_prices'
  | 'volatile'
  | 'high_prices'
  | 'mixed_high_low'
  | 'gradual_increase'
  | 'custom';

interface MockServerState {
  parameters: ScheduleParameters;
  scenario: PriceScenario;
  currentPrice: number;
  tomorrowValid: boolean;
  blocks: Array<{
    start: string;
    end: string;
    duration: number;
    price: number;
    enabled: boolean;
    costEur: number;
    costExceeded: boolean;
  }>;
  nightComplete: boolean;
  blockEnabled: Record<number, boolean>;
  isInHeatingWindow: boolean;
  simulatedHour: number | null;
  totalCost: number;
  costLimitApplied: boolean;
}

interface UseMockServerReturn {
  // Connection state
  connected: boolean;
  error: string | null;

  // Schedule state (compatible with SchedulePanel)
  schedule: ScheduleState | null;
  nightComplete: boolean;
  isInHeatingWindow: boolean;

  // Actions
  setScheduleParameters: (params: ScheduleParameters) => Promise<void>;
  recalculateSchedule: () => Promise<void>;
  setBlockEnabled: (blockNumber: number, enabled: boolean) => Promise<void>;

  // Mock server specific
  setScenario: (scenario: PriceScenario) => Promise<void>;
  simulateTime: (hour: number | null) => Promise<void>;
  resetState: () => Promise<void>;
  availableScenarios: PriceScenario[];
  currentScenario: PriceScenario;

  // Raw state for debugging
  rawState: MockServerState | null;
}

export function useMockServer(): UseMockServerReturn {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rawState, setRawState] = useState<MockServerState | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  // Convert mock server state to ScheduleState format
  const schedule: ScheduleState | null = rawState ? {
    blocks: rawState.blocks.map(block => {
      // Parse ISO datetime strings
      return {
        start: block.start.split('T')[1]?.substring(0, 5) || block.start,
        end: block.end.split('T')[1]?.substring(0, 5) || block.end,
        endDateTime: block.end,
        price: block.price,
        duration: block.duration,
        enabled: block.enabled,
        costEur: block.costEur ?? 0,
        costExceeded: block.costExceeded ?? false,
      };
    }),
    nordpoolAvailable: rawState.tomorrowValid,
    currentPrice: rawState.currentPrice * 100, // Convert to cents
    scheduledMinutes: rawState.blocks.reduce((sum, b) => sum + b.duration, 0),
    parameters: rawState.parameters,
    totalCost: rawState.totalCost ?? 0,
    costLimitApplied: rawState.costLimitApplied ?? false,
  } : null;

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(MOCK_SERVER_WS);

      ws.onopen = () => {
        console.log('[MockServer] Connected');
        setConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'connected' || data.type === 'state_changed' || data.type === 'state') {
            setRawState(data.state);
          }
        } catch (e) {
          console.error('[MockServer] Parse error:', e);
        }
      };

      ws.onerror = (event) => {
        console.error('[MockServer] WebSocket error:', event);
        setError('WebSocket connection error');
      };

      ws.onclose = () => {
        console.log('[MockServer] Disconnected');
        setConnected(false);
        wsRef.current = null;

        // Try to reconnect after 2 seconds
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 2000);
      };

      wsRef.current = ws;
    } catch (e) {
      console.error('[MockServer] Connection failed:', e);
      setError('Failed to connect to mock server');
    }
  }, []);

  // Initialize connection
  useEffect(() => {
    // First try to fetch state via REST to check if server is running
    fetch(`${MOCK_SERVER_URL}/api/state`)
      .then(res => res.json())
      .then(data => {
        setRawState(data);
        connect();
      })
      .catch(() => {
        setError('Mock server not running. Start with: python -m scripts.mock_server');
      });

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  // API methods
  const setScheduleParameters = useCallback(async (params: ScheduleParameters) => {
    const response = await fetch(`${MOCK_SERVER_URL}/api/parameters`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        minBlockDuration: params.minBlockDuration,
        maxBlockDuration: params.maxBlockDuration,
        totalHours: params.totalHours,
        maxCostEur: params.maxCostEur,
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to set parameters');
    }
  }, []);

  const recalculateSchedule = useCallback(async () => {
    const response = await fetch(`${MOCK_SERVER_URL}/api/calculate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });

    if (!response.ok) {
      throw new Error('Failed to calculate schedule');
    }

    // Also fetch state to ensure we have the latest
    // (WebSocket might not have delivered yet)
    const stateResponse = await fetch(`${MOCK_SERVER_URL}/api/state`);
    if (stateResponse.ok) {
      const newState = await stateResponse.json();
      setRawState(newState);
    }
  }, []);

  const setBlockEnabled = useCallback(async (blockNumber: number, enabled: boolean) => {
    const response = await fetch(`${MOCK_SERVER_URL}/api/block-enabled`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ blockNumber, enabled }),
    });

    if (!response.ok) {
      throw new Error('Failed to set block enabled');
    }
  }, []);

  const setScenario = useCallback(async (scenario: PriceScenario) => {
    const response = await fetch(`${MOCK_SERVER_URL}/api/scenario`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario }),
    });

    if (!response.ok) {
      throw new Error('Failed to set scenario');
    }

    // Recalculate after changing scenario
    await recalculateSchedule();
  }, [recalculateSchedule]);

  const simulateTime = useCallback(async (hour: number | null) => {
    const response = await fetch(`${MOCK_SERVER_URL}/api/simulate-time`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hour }),
    });

    if (!response.ok) {
      throw new Error('Failed to simulate time');
    }
  }, []);

  const resetState = useCallback(async () => {
    const response = await fetch(`${MOCK_SERVER_URL}/api/reset`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error('Failed to reset state');
    }

    // Recalculate after reset
    await recalculateSchedule();
  }, [recalculateSchedule]);

  return {
    connected,
    error,
    schedule,
    nightComplete: rawState?.nightComplete ?? false,
    isInHeatingWindow: rawState?.isInHeatingWindow ?? false,
    setScheduleParameters,
    recalculateSchedule,
    setBlockEnabled,
    setScenario,
    simulateTime,
    resetState,
    availableScenarios: [
      'typical_winter',
      'cheap_night',
      'expensive_night',
      'negative_prices',
      'flat_prices',
      'volatile',
      'high_prices',
      'mixed_high_low',
      'gradual_increase',
    ],
    currentScenario: rawState?.scenario ?? 'typical_winter',
    rawState,
  };
}
