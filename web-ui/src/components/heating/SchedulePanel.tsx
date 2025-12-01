import { cn } from '@/lib/utils';
import { ScheduleState } from '@/types/heating';
import { Clock, Euro, Calendar, CheckCircle, History, AlertCircle } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { useTranslation } from 'react-i18next';

interface SchedulePanelProps {
  schedule: ScheduleState;
  nightComplete?: boolean;
  onBlockEnabledChange?: (blockNumber: number, enabled: boolean) => void;
  className?: string;
}

// Check if a block end time is in the past using full ISO datetime
function isBlockInPast(endDateTime: string): boolean {
  if (!endDateTime) return false;
  const now = new Date();
  const blockEnd = new Date(endDateTime);
  return now > blockEnd;
}

export function SchedulePanel({ schedule, nightComplete, onBlockEnabledChange, className }: SchedulePanelProps) {
  const { t } = useTranslation();
  const avgPrice =
    schedule.blocks.length > 0
      ? schedule.blocks.reduce((sum, b) => sum + b.price, 0) / schedule.blocks.length
      : 0;

  return (
    <div className={cn('p-4 rounded-xl bg-card border border-border', className)}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Calendar className="w-4 h-4 text-primary" />
          {t('schedule.title')}
        </h3>
        <div className="flex items-center gap-1">
          {schedule.nordpoolAvailable ? (
            <>
              <CheckCircle className="w-3 h-3 text-success" />
              <span className="text-xs text-success">{t('schedule.pricesAvailable')}</span>
            </>
          ) : (
            <div className="flex items-center gap-1 px-2 py-1 rounded bg-warning/20 border border-warning/30">
              <AlertCircle className="w-3 h-3 text-warning" />
              <span className="text-xs text-warning font-medium">{t('schedule.awaitingPrices')}</span>
            </div>
          )}
        </div>
      </div>

      {/* Night complete indicator */}
      {nightComplete && (
        <div className="flex items-center gap-2 mb-4 p-2 rounded-lg bg-success/20 text-success">
          <CheckCircle className="w-4 h-4" />
          <span className="text-sm">{t('schedule.nightComplete')}</span>
        </div>
      )}

      {/* Current price */}
      <div className="flex items-center justify-between mb-4 p-3 rounded-lg bg-muted/50">
        <div className="flex items-center gap-2">
          <Euro className="w-4 h-4 text-warning" />
          <span className="text-sm text-muted-foreground">{t('schedule.currentPrice')}</span>
        </div>
        <span className="font-mono text-lg text-warning">{schedule.currentPrice.toFixed(1)} {t('units.centsPerKwh')}</span>
      </div>

      {/* Schedule blocks */}
      <div className="space-y-2">
        {schedule.blocks.map((block, index) => {
          const isPast = isBlockInPast(block.endDateTime);
          const isDisabled = !block.enabled;

          return (
            <div
              key={index}
              className={cn(
                'flex items-center justify-between p-2 rounded-lg transition-colors',
                isPast
                  ? 'bg-muted/20 border border-muted/30'
                  : isDisabled
                    ? 'bg-marja/30 border border-marja/50'
                    : 'bg-muted/30 hover:bg-muted/50'
              )}
            >
              <div className="flex items-center gap-2">
                {onBlockEnabledChange && (
                  <Switch
                    checked={block.enabled}
                    onCheckedChange={(checked) => onBlockEnabledChange(index + 1, checked)}
                    disabled={isPast}
                    className={cn(
                      'scale-75',
                      isPast && 'opacity-30 cursor-not-allowed',
                      isDisabled && !isPast && 'data-[state=unchecked]:bg-marja'
                    )}
                    title={isPast ? t('schedule.blockPast') : undefined}
                  />
                )}
                {isPast ? (
                  <History className="w-3 h-3 text-muted-foreground" />
                ) : block.enabled ? (
                  <Clock className="w-3 h-3 text-primary" />
                ) : (
                  <Clock className="w-3 h-3 text-marja" />
                )}
                <span
                  className={cn(
                    'font-mono text-sm',
                    isPast
                      ? 'text-muted-foreground'
                      : isDisabled
                        ? 'text-foreground/70 line-through'
                        : 'text-foreground'
                  )}
                >
                  {block.start} - {block.end}
                </span>
                {isPast && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-medium">
                    {t('schedule.completed')}
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
                    isPast
                      ? 'text-muted-foreground/60'
                      : isDisabled
                        ? 'text-foreground/50 line-through'
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
          {t('schedule.total')}: <span className="font-mono text-foreground">{schedule.scheduledMinutes} {t('schedule.min')}</span>
        </div>
        <div className="text-muted-foreground">
          {t('schedule.avg')}: <span className="font-mono text-success">{avgPrice.toFixed(2)} {t('units.centsPerKwh')}</span>
        </div>
      </div>
    </div>
  );
}
