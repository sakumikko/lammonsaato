import { cn } from '@/lib/utils';
import { ScheduleState } from '@/types/heating';
import { Clock, Euro, Calendar, CheckCircle, Ban, History, AlertCircle } from 'lucide-react';
import { Switch } from '@/components/ui/switch';

interface SchedulePanelProps {
  schedule: ScheduleState;
  nightComplete?: boolean;
  onBlockEnabledChange?: (blockNumber: number, enabled: boolean) => void;
  className?: string;
}

// Check if a block end time is in the past
function isBlockInPast(endTime: string): boolean {
  const now = new Date();
  const [hours, minutes] = endTime.split(':').map(Number);

  // Create a date for today with the block end time
  const blockEnd = new Date();
  blockEnd.setHours(hours, minutes, 0, 0);

  // If block end is between 00:00-07:00, it's "tomorrow morning" in the schedule
  // but if current time is after 07:00, those blocks are in the past
  if (hours < 7) {
    // Morning block - check if we're past 07:00 today
    if (now.getHours() >= 7) {
      return true; // Morning blocks are done for today
    }
  }

  return now > blockEnd;
}

export function SchedulePanel({ schedule, nightComplete, onBlockEnabledChange, className }: SchedulePanelProps) {
  const avgPrice =
    schedule.blocks.length > 0
      ? schedule.blocks.reduce((sum, b) => sum + b.price, 0) / schedule.blocks.length
      : 0;

  return (
    <div className={cn('p-4 rounded-xl bg-card border border-border', className)}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Calendar className="w-4 h-4 text-primary" />
          Tonight's Schedule
        </h3>
        <div className="flex items-center gap-1">
          {schedule.nordpoolAvailable ? (
            <>
              <CheckCircle className="w-3 h-3 text-success" />
              <span className="text-xs text-success">Prices available</span>
            </>
          ) : (
            <div className="flex items-center gap-1 px-2 py-1 rounded bg-warning/20 border border-warning/30">
              <AlertCircle className="w-3 h-3 text-warning" />
              <span className="text-xs text-warning font-medium">Awaiting prices</span>
            </div>
          )}
        </div>
      </div>

      {/* Night complete indicator */}
      {nightComplete && (
        <div className="flex items-center gap-2 mb-4 p-2 rounded-lg bg-success/20 text-success">
          <CheckCircle className="w-4 h-4" />
          <span className="text-sm">Target reached - remaining blocks skipped</span>
        </div>
      )}

      {/* Current price */}
      <div className="flex items-center justify-between mb-4 p-3 rounded-lg bg-muted/50">
        <div className="flex items-center gap-2">
          <Euro className="w-4 h-4 text-warning" />
          <span className="text-sm text-muted-foreground">Current Price</span>
        </div>
        <span className="font-mono text-lg text-warning">{schedule.currentPrice.toFixed(1)} c/kWh</span>
      </div>

      {/* Schedule blocks */}
      <div className="space-y-2">
        {schedule.blocks.map((block, index) => {
          const isPast = isBlockInPast(block.end);
          const isDisabled = !block.enabled;

          return (
            <div
              key={index}
              className={cn(
                'flex items-center justify-between p-2 rounded-lg transition-colors',
                isPast
                  ? 'bg-muted/20 border border-muted/30'
                  : isDisabled
                    ? 'bg-muted/10 opacity-60'
                    : 'bg-muted/30 hover:bg-muted/50'
              )}
            >
              <div className="flex items-center gap-2">
                {onBlockEnabledChange && (
                  <Switch
                    checked={block.enabled}
                    onCheckedChange={(checked) => onBlockEnabledChange(index + 1, checked)}
                    disabled={isPast}
                    className={cn('scale-75', isPast && 'opacity-30 cursor-not-allowed')}
                    title={isPast ? 'This block has already completed' : undefined}
                  />
                )}
                {isPast ? (
                  <History className="w-3 h-3 text-muted-foreground" />
                ) : block.enabled ? (
                  <Clock className="w-3 h-3 text-primary" />
                ) : (
                  <Ban className="w-3 h-3 text-muted-foreground" />
                )}
                <span
                  className={cn(
                    'font-mono text-sm',
                    isPast
                      ? 'text-muted-foreground'
                      : isDisabled
                        ? 'text-muted-foreground line-through'
                        : 'text-foreground'
                  )}
                >
                  {block.start} - {block.end}
                </span>
                {isPast && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-medium">
                    Completed
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span className={cn('text-xs', isPast ? 'text-muted-foreground/60' : 'text-muted-foreground')}>
                  {block.duration}min
                </span>
                <span
                  className={cn(
                    'font-mono text-sm',
                    isPast || isDisabled
                      ? 'text-muted-foreground/60'
                      : block.price < 2
                        ? 'text-success'
                        : block.price < 5
                          ? 'text-warning'
                          : 'text-destructive'
                  )}
                >
                  {block.price.toFixed(2)} c
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Summary */}
      <div className="mt-4 pt-4 border-t border-border flex items-center justify-between text-sm">
        <div className="text-muted-foreground">
          Total: <span className="font-mono text-foreground">{schedule.scheduledMinutes} min</span>
        </div>
        <div className="text-muted-foreground">
          Avg: <span className="font-mono text-success">{avgPrice.toFixed(2)} c/kWh</span>
        </div>
      </div>
    </div>
  );
}
