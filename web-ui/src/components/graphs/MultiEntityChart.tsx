/**
 * Main multi-entity chart component using Recharts
 * Displays normalized values (0-100%) for different-scale entities
 */

import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { MultiEntityHistoryData, EntityConfig } from '@/types/graphs';
import { ChartTooltip } from './ChartTooltip';
import { ChartLegend } from './ChartLegend';
import { Loader2 } from 'lucide-react';

interface MultiEntityChartProps {
  data: MultiEntityHistoryData | null;
  entities: EntityConfig[];
  visibleEntities: Set<string>;
  onToggleEntity: (entityId: string) => void;
  loading?: boolean;
  error?: string | null;
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function MultiEntityChart({
  data,
  entities,
  visibleEntities,
  onToggleEntity,
  loading,
  error,
}: MultiEntityChartProps) {
  // Transform data for Recharts
  const chartData = useMemo(() => {
    if (!data) return [];

    return data.series.map(point => {
      const entry: Record<string, unknown> = {
        timestamp: point.timestamp,
        values: point.values,
      };

      // Add normalized values as direct properties for each visible entity
      for (const [entityId, values] of Object.entries(point.values)) {
        if (visibleEntities.has(entityId)) {
          entry[`${entityId}_normalized`] = values.normalized;
        }
      }

      return entry;
    });
  }, [data, visibleEntities]);

  // Get current (latest) values for legend
  const currentValues = useMemo(() => {
    if (!data || data.series.length === 0) return {};

    const lastPoint = data.series[data.series.length - 1];
    const result: Record<string, number | null> = {};

    for (const [entityId, values] of Object.entries(lastPoint.values)) {
      result[entityId] = values.raw;
    }

    return result;
  }, [data]);

  // Entity configs as record for tooltip
  const entityConfigs = useMemo(() => {
    return Object.fromEntries(entities.map(e => [e.entityId, e]));
  }, [entities]);

  if (loading) {
    return (
      <div
        data-testid="chart-loading"
        className="flex items-center justify-center h-64"
      >
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div
        data-testid="chart-error"
        className="flex items-center justify-center h-64 text-destructive"
      >
        <p>Failed to load chart data: {error}</p>
      </div>
    );
  }

  if (!data || data.series.length === 0) {
    return (
      <div data-testid="multi-entity-chart">
        <div className="flex items-center justify-center h-64 text-muted-foreground">
          <p>No data available</p>
        </div>
        <ChartLegend
          entities={entities}
          visibleEntities={visibleEntities}
          onToggle={onToggleEntity}
        />
      </div>
    );
  }

  const visibleEntityList = entities.filter(e => visibleEntities.has(e.entityId));

  return (
    <div data-testid="multi-entity-chart">
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="timestamp"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={formatTime}
              stroke="hsl(var(--muted-foreground))"
              fontSize={12}
            />
            <YAxis
              domain={[0, 100]}
              tickFormatter={(v) => `${v}%`}
              stroke="hsl(var(--muted-foreground))"
              fontSize={12}
            />
            <Tooltip
              content={<ChartTooltip entities={entityConfigs} />}
            />
            {visibleEntityList.map(entity => (
              <Line
                key={entity.entityId}
                type="stepAfter"
                dataKey={`${entity.entityId}_normalized`}
                stroke={entity.color}
                strokeWidth={2}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <ChartLegend
        entities={entities}
        visibleEntities={visibleEntities}
        onToggle={onToggleEntity}
        currentValues={currentValues}
      />
    </div>
  );
}
