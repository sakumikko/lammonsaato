/**
 * Custom tooltip component for multi-entity chart
 * Shows actual (denormalized) values with units
 */

import { EntityConfig } from '@/types/graphs';

interface TooltipPayloadItem {
  dataKey: string;
  value: number;
  color: string;
  payload: {
    timestamp: number;
    values: Record<string, { raw: number | null; normalized: number | null }>;
  };
}

interface ChartTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  entities: Record<string, EntityConfig>;
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp);
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function ChartTooltip({ active, payload, entities }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  const firstPayload = payload[0];
  const timestamp = firstPayload.payload.timestamp;
  const values = firstPayload.payload.values;

  return (
    <div className="bg-popover border border-border rounded-lg shadow-lg p-3 text-sm">
      <div className="font-medium mb-2 text-muted-foreground">
        {formatTime(timestamp)}
      </div>
      <div className="space-y-1">
        {payload.map(item => {
          const entityId = item.dataKey.replace('_normalized', '');
          const entity = entities[entityId];
          const entityValues = values[entityId];

          if (!entity || !entityValues) return null;

          const rawValue = entityValues.raw;
          const displayValue = rawValue !== null
            ? `${rawValue.toFixed(2)}${entity.unit ? ` ${entity.unit}` : ''}`
            : 'N/A';

          return (
            <div key={entityId} className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: entity.color }}
              />
              <span className="font-medium">{entity.label}:</span>
              <span className="font-mono">{displayValue}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
