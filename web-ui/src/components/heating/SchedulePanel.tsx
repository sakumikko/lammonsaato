import { cn } from '@/lib/utils';
import { ScheduleState } from '@/types/heating';
import { Clock, Euro, Calendar, CheckCircle } from 'lucide-react';

interface SchedulePanelProps {
  schedule: ScheduleState;
  className?: string;
}

export function SchedulePanel({ schedule, className }: SchedulePanelProps) {
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
            <span className="text-xs text-muted-foreground">Awaiting prices</span>
          )}
        </div>
      </div>

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
        {schedule.blocks.map((block, index) => (
          <div
            key={index}
            className="flex items-center justify-between p-2 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Clock className="w-3 h-3 text-primary" />
              <span className="font-mono text-sm text-foreground">
                {block.start} - {block.end}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted-foreground">{block.duration}min</span>
              <span
                className={cn(
                  'font-mono text-sm',
                  block.price < 2 ? 'text-success' : block.price < 5 ? 'text-warning' : 'text-destructive'
                )}
              >
                {block.price.toFixed(2)} c
              </span>
            </div>
          </div>
        ))}
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
