/**
 * Entity picker for custom graph - allows users to select which entities to display
 */

import { EntityPreset } from '@/types/graphs';
import { ALL_ENTITY_PRESETS } from '@/constants/entityPresets';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface EntityPickerProps {
  selectedEntities: Set<string>;
  onToggleEntity: (entityId: string) => void;
}

export function EntityPicker({ selectedEntities, onToggleEntity }: EntityPickerProps) {
  // Group entities by their axis group for better organization
  const groupedEntities = ALL_ENTITY_PRESETS.reduce((acc, entity) => {
    const group = entity.axisGroup || 'other';
    if (!acc[group]) {
      acc[group] = [];
    }
    acc[group].push(entity);
    return acc;
  }, {} as Record<string, EntityPreset[]>);

  const groupLabels: Record<string, string> = {
    control: 'Control Values',
    delta: 'Temperature Differences',
    right: 'Temperatures',
    percent: 'Percentages',
    other: 'Other',
  };

  const groupOrder = ['control', 'delta', 'right', 'percent', 'other'];

  return (
    <TooltipProvider delayDuration={100}>
      <div className="border rounded-lg p-4 mb-4" data-testid="entity-picker">
        <h3 className="text-sm font-medium mb-3">Select Entities</h3>
        <div className="space-y-4">
          {groupOrder.map(group => {
            const entities = groupedEntities[group];
            if (!entities || entities.length === 0) return null;

            return (
              <div key={group}>
                <h4 className="text-xs text-muted-foreground mb-2">
                  {groupLabels[group] || group}
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                  {entities.map(entity => (
                    <Tooltip key={entity.entityId}>
                      <TooltipTrigger asChild>
                        <label
                          className="flex items-center gap-2 text-sm cursor-pointer hover:bg-accent/50 rounded p-1"
                        >
                          <Checkbox
                            checked={selectedEntities.has(entity.entityId)}
                            onCheckedChange={() => onToggleEntity(entity.entityId)}
                          />
                          <span
                            className="w-3 h-3 rounded-full flex-shrink-0"
                            style={{ backgroundColor: entity.color }}
                          />
                          <span className="truncate">{entity.label}</span>
                        </label>
                      </TooltipTrigger>
                      <TooltipContent>
                        <code className="text-xs">{entity.entityId}</code>
                      </TooltipContent>
                    </Tooltip>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </TooltipProvider>
  );
}
