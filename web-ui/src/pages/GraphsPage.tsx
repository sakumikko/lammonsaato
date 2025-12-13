/**
 * Multi-entity graph page for analyzing Thermia heat pump data
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { MultiEntityChart, TimeRangeSelector, IntegralDisplay, EntityPicker } from '@/components/graphs';
import { useHistoryData } from '@/hooks/useHistoryData';
import { useIntegralCalculation } from '@/hooks/useIntegralCalculation';
import { useRollingIntegrals, ROLLING_INTEGRAL_ENTITIES } from '@/hooks/useRollingIntegrals';
import { DEFAULT_GRAPHS, ENTITY_PRESETS } from '@/constants/entityPresets';
import { GraphConfig, TimeRange, EntityConfig } from '@/types/graphs';

const PID_SUM_ENTITY_ID = 'sensor.external_heater_pid_sum';
const ROLLING_INTEGRAL_IDS = Object.values(ROLLING_INTEGRAL_ENTITIES);

export function GraphsPage() {
  const [activeGraphId, setActiveGraphId] = useState(DEFAULT_GRAPHS[0].id);
  const [timeRange, setTimeRange] = useState<TimeRange>(DEFAULT_GRAPHS[0].timeRange);
  const [visibleEntities, setVisibleEntities] = useState<Set<string>>(() => {
    const graph = DEFAULT_GRAPHS[0];
    return new Set(graph.entities.filter(e => e.visible).map(e => e.entityId));
  });
  // Custom graph selected entities (used when activeGraphId === 'custom')
  const [customSelectedEntities, setCustomSelectedEntities] = useState<Set<string>>(new Set());

  const isCustomGraph = activeGraphId === 'custom';

  const { data, loading, error, fetchData } = useHistoryData();

  // Get active graph config (builds entities from customSelectedEntities for custom graph)
  const activeGraph = useMemo((): GraphConfig => {
    const graph = DEFAULT_GRAPHS.find(g => g.id === activeGraphId) || DEFAULT_GRAPHS[0];

    if (isCustomGraph) {
      // Build entities from selected presets
      const customEntities: EntityConfig[] = Array.from(customSelectedEntities)
        .map(entityId => ENTITY_PRESETS[entityId])
        .filter((e): e is EntityConfig => !!e)
        .map(e => ({ ...e, visible: true }));

      return {
        ...graph,
        entities: customEntities,
      };
    }

    return graph;
  }, [activeGraphId, isCustomGraph, customSelectedEntities]);

  // Calculate PID integral if current graph contains the PID sum entity
  const hasPidSum = useMemo(() => {
    return activeGraph.entities.some(e => e.entityId === PID_SUM_ENTITY_ID);
  }, [activeGraph.entities]);

  const pidIntegrals = useIntegralCalculation(
    hasPidSum ? data : null,
    PID_SUM_ENTITY_ID
  );

  // Calculate rolling integrals for graphing
  const rollingIntegrals = useRollingIntegrals(data, PID_SUM_ENTITY_ID, hasPidSum);

  // Merge rolling integral entities into active graph entities
  const chartEntities = useMemo((): EntityConfig[] => {
    if (!hasPidSum || !rollingIntegrals) {
      return activeGraph.entities;
    }
    return [...activeGraph.entities, ...rollingIntegrals.entities];
  }, [activeGraph.entities, hasPidSum, rollingIntegrals]);

  // Use merged data with rolling integrals if available
  const chartData = useMemo(() => {
    if (hasPidSum && rollingIntegrals) {
      return rollingIntegrals.data;
    }
    return data;
  }, [data, hasPidSum, rollingIntegrals]);

  // Fetch data when graph, time range, or visible entities change
  useEffect(() => {
    const visibleConfigs = activeGraph.entities.filter(e =>
      visibleEntities.has(e.entityId)
    );
    if (visibleConfigs.length > 0) {
      fetchData(visibleConfigs, timeRange);
    }
  }, [activeGraph.id, timeRange, visibleEntities, fetchData]);

  // Handle graph change
  const handleGraphChange = useCallback((graphId: string) => {
    const graph = DEFAULT_GRAPHS.find(g => g.id === graphId);
    if (graph) {
      setActiveGraphId(graphId);
      setTimeRange(graph.timeRange);

      if (graphId === 'custom') {
        // For custom graph, visible entities = custom selected entities
        setVisibleEntities(customSelectedEntities);
      } else {
        setVisibleEntities(new Set(
          graph.entities.filter(e => e.visible).map(e => e.entityId)
        ));
      }
    }
  }, [customSelectedEntities]);

  // Handle custom entity selection toggle
  const handleCustomEntityToggle = useCallback((entityId: string) => {
    setCustomSelectedEntities(prev => {
      const next = new Set(prev);
      if (next.has(entityId)) {
        next.delete(entityId);
      } else {
        next.add(entityId);
      }
      // Also update visible entities
      setVisibleEntities(next);
      return next;
    });
  }, []);

  // Handle time range change
  const handleTimeRangeChange = useCallback((newRange: TimeRange) => {
    setTimeRange(newRange);
  }, []);

  // Handle entity visibility toggle
  const handleToggleEntity = useCallback((entityId: string) => {
    setVisibleEntities(prev => {
      const next = new Set(prev);
      if (next.has(entityId)) {
        next.delete(entityId);
      } else {
        next.add(entityId);
      }
      return next;
    });
  }, []);

  return (
    <div className="min-h-screen bg-background" data-testid="graphs-page">
      {/* Header */}
      <header className="border-b bg-card/50 backdrop-blur sticky top-0 z-10">
        <div className="container mx-auto px-4 py-3">
          <div className="flex items-center gap-4 flex-wrap">
            <Link to="/">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4 mr-1" />
                Back
              </Button>
            </Link>

            <Select value={activeGraphId} onValueChange={handleGraphChange}>
              <SelectTrigger className="w-[200px]" data-testid="graph-selector">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DEFAULT_GRAPHS.map(graph => (
                  <SelectItem key={graph.id} value={graph.id}>
                    {graph.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="ml-auto">
              <TimeRangeSelector
                value={timeRange}
                onChange={handleTimeRangeChange}
              />
            </div>
          </div>
        </div>
      </header>

      {/* Chart */}
      <main className="container mx-auto px-4 py-6">
        <div className="bg-card border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-4">{activeGraph.name}</h2>

          {/* Entity Picker for custom graph */}
          {isCustomGraph && (
            <EntityPicker
              selectedEntities={customSelectedEntities}
              onToggleEntity={handleCustomEntityToggle}
            />
          )}

          {/* Show chart or empty state for custom graph */}
          {isCustomGraph && customSelectedEntities.size === 0 ? (
            <div
              className="h-[400px] flex items-center justify-center text-muted-foreground"
              data-testid="multi-entity-chart"
            >
              Select entities above to display in the chart
            </div>
          ) : (
            <MultiEntityChart
              data={chartData}
              entities={chartEntities}
              visibleEntities={visibleEntities}
              onToggleEntity={handleToggleEntity}
              loading={loading}
              error={error}
            />
          )}

          {hasPidSum && (
            <IntegralDisplay integrals={pidIntegrals} sensorLabel="PID Sum" />
          )}
        </div>
      </main>
    </div>
  );
}

export default GraphsPage;
