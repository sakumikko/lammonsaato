import { useState, useEffect, useCallback, useMemo } from 'react';
import { getHAWebSocket, HAEntityState, StatisticsResult } from '@/lib/ha-websocket';

export type EntityValueType = 'numeric' | 'boolean' | 'datetime' | 'string' | 'unknown';
export type EntityDomain = 'sensor' | 'input_number' | 'input_boolean' | 'input_datetime' | 'input_text' | 'binary_sensor' | 'switch' | 'number' | 'other';

export interface EntityInfo {
  entityId: string;
  domain: EntityDomain;
  friendlyName: string;
  state: string;
  valueType: EntityValueType;
  numericValue: number | null;
  unit: string | null;
  lastChanged: Date;
  lastUpdated: Date;
  attributes: Record<string, unknown>;
}

export interface HistoryDataPoint {
  timestamp: Date;
  value: number | string | boolean | null;
  numericValue: number | null;
}

export interface EntityHistoryData {
  entityId: string;
  points: HistoryDataPoint[];
  stats?: {
    min: number;
    max: number;
    mean: number;
  };
}

export type TimeRangeHours = 1 | 6 | 24 | 48 | 168; // 1h, 6h, 24h, 48h, 7d

/**
 * Determine the value type from an entity state
 */
function getValueType(state: string, domain: EntityDomain): EntityValueType {
  // Boolean domains
  if (domain === 'input_boolean' || domain === 'binary_sensor' || domain === 'switch') {
    return 'boolean';
  }

  // Datetime domain
  if (domain === 'input_datetime') {
    return 'datetime';
  }

  // Check if numeric
  if (state !== 'unknown' && state !== 'unavailable') {
    const num = parseFloat(state);
    if (!isNaN(num)) {
      return 'numeric';
    }
  }

  // Check for datetime-like strings
  if (/^\d{4}-\d{2}-\d{2}/.test(state)) {
    return 'datetime';
  }

  return 'string';
}

/**
 * Extract domain from entity ID
 */
function getDomain(entityId: string): EntityDomain {
  const domain = entityId.split('.')[0];
  const validDomains: EntityDomain[] = ['sensor', 'input_number', 'input_boolean', 'input_datetime', 'input_text', 'binary_sensor', 'switch', 'number'];
  return validDomains.includes(domain as EntityDomain) ? domain as EntityDomain : 'other';
}

/**
 * Parse HA entity state into EntityInfo
 */
function parseEntityState(state: HAEntityState): EntityInfo {
  const domain = getDomain(state.entity_id);
  const valueType = getValueType(state.state, domain);
  const numericValue = valueType === 'numeric' ? parseFloat(state.state) : null;

  return {
    entityId: state.entity_id,
    domain,
    friendlyName: (state.attributes.friendly_name as string) || state.entity_id,
    state: state.state,
    valueType,
    numericValue,
    unit: (state.attributes.unit_of_measurement as string) || null,
    lastChanged: new Date(state.last_changed),
    lastUpdated: new Date(state.last_updated),
    attributes: state.attributes,
  };
}

export interface UseEntityBrowserReturn {
  entities: EntityInfo[];
  filteredEntities: EntityInfo[];
  loading: boolean;
  error: string | null;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  domainFilter: EntityDomain | 'all';
  setDomainFilter: (domain: EntityDomain | 'all') => void;
  valueTypeFilter: EntityValueType | 'all';
  setValueTypeFilter: (type: EntityValueType | 'all') => void;
  refetch: () => void;
  fetchHistory: (entityId: string, hours: TimeRangeHours) => Promise<EntityHistoryData>;
}

export function useEntityBrowser(): UseEntityBrowserReturn {
  const [entities, setEntities] = useState<EntityInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [domainFilter, setDomainFilter] = useState<EntityDomain | 'all'>('all');
  const [valueTypeFilter, setValueTypeFilter] = useState<EntityValueType | 'all'>('all');

  const fetchEntities = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const ws = getHAWebSocket();
      if (!ws.connected) {
        await ws.connect();
      }

      const states = await ws.getStates();
      const parsed = states
        .map(parseEntityState)
        .sort((a, b) => a.entityId.localeCompare(b.entityId));

      setEntities(parsed);
    } catch (err) {
      console.error('[useEntityBrowser] Failed to fetch entities:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch entities');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEntities();
  }, [fetchEntities]);

  // Subscribe to state changes
  useEffect(() => {
    const ws = getHAWebSocket();
    const unsubscribe = ws.onStateChange((entityId, newState) => {
      setEntities(prev =>
        prev.map(e =>
          e.entityId === entityId ? parseEntityState(newState) : e
        )
      );
    });
    return unsubscribe;
  }, []);

  const filteredEntities = useMemo(() => {
    let result = entities;

    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(e =>
        e.entityId.toLowerCase().includes(query) ||
        e.friendlyName.toLowerCase().includes(query)
      );
    }

    // Apply domain filter
    if (domainFilter !== 'all') {
      result = result.filter(e => e.domain === domainFilter);
    }

    // Apply value type filter
    if (valueTypeFilter !== 'all') {
      result = result.filter(e => e.valueType === valueTypeFilter);
    }

    return result;
  }, [entities, searchQuery, domainFilter, valueTypeFilter]);

  const fetchHistory = useCallback(async (entityId: string, hours: TimeRangeHours): Promise<EntityHistoryData> => {
    const ws = getHAWebSocket();
    if (!ws.connected) {
      await ws.connect();
    }

    const end = new Date();
    const start = new Date(end.getTime() - hours * 60 * 60 * 1000);

    // Try to get statistics first (more efficient for long periods)
    const entity = entities.find(e => e.entityId === entityId);
    const isNumeric = entity?.valueType === 'numeric';

    if (isNumeric && hours >= 24) {
      // Use statistics for numeric entities over longer periods
      const period = hours <= 48 ? 'hour' : 'day';
      const statistics = await ws.getStatistics(start, end, [entityId], period);
      const entityStats = statistics[entityId] || [];

      if (entityStats.length > 0) {
        const points: HistoryDataPoint[] = entityStats.map(stat => ({
          timestamp: new Date(stat.start),
          value: stat.mean ?? stat.state ?? null,
          numericValue: stat.mean ?? stat.state ?? null,
        }));

        // Calculate overall stats
        const numericValues = points.map(p => p.numericValue).filter((v): v is number => v !== null);
        const stats = numericValues.length > 0 ? {
          min: Math.min(...numericValues),
          max: Math.max(...numericValues),
          mean: numericValues.reduce((a, b) => a + b, 0) / numericValues.length,
        } : undefined;

        return { entityId, points, stats };
      }
    }

    // Fall back to raw history
    const history = await ws.getHistory(start, end, [entityId], true);

    // Handle both object and array formats
    let historyStates: HAEntityState[] = [];
    if (history && typeof history === 'object') {
      if (Array.isArray(history)) {
        historyStates = history[0] || [];
      } else {
        const historyObj = history as unknown as Record<string, HAEntityState[]>;
        historyStates = historyObj[entityId] || [];
      }
    }

    const points: HistoryDataPoint[] = historyStates.map(state => {
      const stateObj = state as Record<string, unknown>;
      const stateValue = (stateObj.state ?? stateObj.s) as string;
      const lastUpdated = stateObj.last_updated ?? stateObj.lu;

      // Handle both ISO string format and Unix timestamp (minimal_response format)
      // minimal_response returns 'lu' as Unix timestamp in seconds
      let timestamp: Date;
      if (typeof lastUpdated === 'number') {
        // Unix timestamp in seconds - convert to milliseconds
        timestamp = new Date(lastUpdated * 1000);
      } else {
        // ISO string format
        timestamp = new Date(lastUpdated as string);
      }

      const numericValue = stateValue !== 'unknown' && stateValue !== 'unavailable'
        ? parseFloat(stateValue)
        : null;

      return {
        timestamp,
        value: stateValue,
        numericValue: isNaN(numericValue as number) ? null : numericValue,
      };
    });

    // Calculate stats for numeric data
    const numericValues = points.map(p => p.numericValue).filter((v): v is number => v !== null);
    const stats = numericValues.length > 0 ? {
      min: Math.min(...numericValues),
      max: Math.max(...numericValues),
      mean: numericValues.reduce((a, b) => a + b, 0) / numericValues.length,
    } : undefined;

    return { entityId, points, stats };
  }, [entities]);

  return {
    entities,
    filteredEntities,
    loading,
    error,
    searchQuery,
    setSearchQuery,
    domainFilter,
    setDomainFilter,
    valueTypeFilter,
    setValueTypeFilter,
    refetch: fetchEntities,
    fetchHistory,
  };
}
