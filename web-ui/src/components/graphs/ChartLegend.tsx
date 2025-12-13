/**
 * Legend component for multi-entity graph with visibility toggles
 */

import { EntityConfig } from '@/types/graphs';
import { cn } from '@/lib/utils';

interface ChartLegendProps {
  entities: EntityConfig[];
  visibleEntities: Set<string>;
  onToggle: (entityId: string) => void;
  currentValues?: Record<string, number | null>;
}

export function ChartLegend({
  entities,
  visibleEntities,
  onToggle,
  currentValues,
}: ChartLegendProps) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-2 mt-4">
      {entities.map(entity => {
        const isVisible = visibleEntities.has(entity.entityId);
        const currentValue = currentValues?.[entity.entityId];

        return (
          <button
            key={entity.entityId}
            onClick={() => onToggle(entity.entityId)}
            data-testid={`legend-${entity.entityId}`}
            data-visible={isVisible}
            className={cn(
              'flex items-center gap-2 px-2 py-1 rounded-md transition-colors',
              'hover:bg-accent/50',
              !isVisible && 'opacity-40'
            )}
          >
            {/* Color indicator */}
            <span
              className={cn(
                'w-3 h-3 rounded-full flex-shrink-0',
                isVisible ? '' : 'border-2 border-current'
              )}
              style={{
                backgroundColor: isVisible ? entity.color : 'transparent',
                borderColor: !isVisible ? entity.color : undefined,
              }}
            />

            {/* Label */}
            <span className="text-sm font-medium">{entity.label}</span>

            {/* Current value */}
            {currentValue !== undefined && currentValue !== null && (
              <span className="text-xs text-muted-foreground font-mono">
                {currentValue.toFixed(1)}
                {entity.unit && entity.unit}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
