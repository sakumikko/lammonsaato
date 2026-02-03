import { cn } from '@/lib/utils';
import { ScheduleState, ScheduleParameters } from '@/types/heating';
import { Clock, Euro, Calendar, CheckCircle, History, AlertCircle, AlertTriangle, Snowflake } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { useTranslation } from 'react-i18next';
import { useScheduleEditor } from './ScheduleEditor';

interface SchedulePanelProps {
  schedule: ScheduleState;
  nightComplete?: boolean;
  onBlockEnabledChange?: (blockNumber: number, enabled: boolean) => void;
  onScheduleParametersChange?: (params: ScheduleParameters) => Promise<void>;
  onRecalculate?: () => Promise<void>;
  isInHeatingWindow?: boolean;
  className?: string;
}

// Check if a block end time is in the past using full ISO datetime
function isBlockInPast(endDateTime: string): boolean {
  if (!endDateTime) return false;
  const now = new Date();
  const blockEnd = new Date(endDateTime);
  return now > blockEnd;
}

export function SchedulePanel({
  schedule,
  nightComplete,
  onBlockEnabledChange,
  onScheduleParametersChange,
  onRecalculate,
  isInHeatingWindow = false,
  className,
}: SchedulePanelProps) {
  const { t } = useTranslation();
  const avgPrice =
    schedule.blocks.length > 0
      ? schedule.blocks.reduce((sum, b) => sum + b.price, 0) / schedule.blocks.length
      : 0;

  // Schedule editor hook
  const editor = onScheduleParametersChange && onRecalculate
    ? useScheduleEditor({
        parameters: schedule.parameters,
        isInHeatingWindow,
        onSave: onScheduleParametersChange,
        onRecalculate,
      })
    : null;

  // Check if cold weather mode is active
  const isColdWeather = schedule.parameters.coldWeatherMode;

  return (
    <div data-testid="schedule-panel" data-cold-weather={isColdWeather || undefined} className={cn('p-4 rounded-xl bg-card border border-border', isColdWeather && 'border-blue-500/30', className)}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Calendar className="w-4 h-4 text-primary" />
          {t('schedule.title')}
        </h3>
        <div className="flex items-center gap-2">
          {/* Schedule editor button */}
          {editor?.EditorButton}
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

      {/* Editor panel (expands below header when open) */}
      {editor?.EditorPanel}

      {/* Warning dialog */}
      {editor?.WarningDialog}

      {/* Cost limit warning */}
      {schedule.costLimitApplied && (
        <div
          data-testid="cost-limit-warning"
          className="flex items-center gap-2 mb-4 p-2 rounded-lg bg-warning/20 border border-warning/30"
        >
          <AlertTriangle className="w-4 h-4 text-warning flex-shrink-0" />
          <span className="text-xs text-warning">
            {t('schedule.costLimitReached', {
              limit: schedule.parameters.maxCostEur?.toFixed(2) ?? '0',
              disabled: schedule.blocks.filter(b => b.costExceeded).length,
            })}
          </span>
        </div>
      )}

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

      {/* Schedule blocks - compact 2-column grid for cold weather with many blocks */}
      <div
        data-testid="schedule-blocks"
        data-block-count={schedule.blocks.length}
        className={cn(
          isColdWeather && schedule.blocks.length > 6
            ? 'grid grid-cols-2 gap-2'
            : 'space-y-2'
        )}
      >
        {schedule.blocks.map((block, index) => {
          const isPast = isBlockInPast(block.endDateTime);
          const isDisabled = !block.enabled;
          const isCompact = isColdWeather && schedule.blocks.length > 6;

          return (
            <div
              key={index}
              data-block-enabled={block.enabled}
              data-block-price={block.price}
              data-cost-exceeded={block.costExceeded || false}
              className={cn(
                'flex flex-col gap-1 p-2 rounded-lg transition-colors',
                isPast
                  ? 'bg-muted/20 border border-muted/30'
                  : isDisabled
                    ? 'bg-marja/30 border border-marja/50'
                    : isColdWeather
                      ? 'bg-blue-500/10 border border-blue-500/30 hover:bg-blue-500/20'
                      : 'bg-muted/30 hover:bg-muted/50'
              )}
            >
              {/* Row 1: Toggle, icon, heating time range */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {onBlockEnabledChange && !isCompact && (
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
                  ) : isColdWeather ? (
                    <Snowflake className={cn('w-3 h-3', block.enabled ? 'text-blue-400' : 'text-marja')} />
                  ) : block.enabled ? (
                    <Clock className="w-3 h-3 text-primary" />
                  ) : (
                    <Clock className="w-3 h-3 text-marja" />
                  )}
                  <span
                    data-testid="block-heating"
                    className={cn(
                      'font-mono text-sm',
                      isPast
                        ? 'text-muted-foreground'
                        : isDisabled
                          ? 'text-foreground/50 line-through'
                          : 'text-foreground'
                    )}
                  >
                    {block.heatingStart}-{block.end}
                  </span>
                  {isPast && !isCompact && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-medium">
                      {t('schedule.completed')}
                    </span>
                  )}
                </div>
                {/* Duration shown inline for compact mode */}
                {isCompact && (
                  <span
                    data-testid="block-duration"
                    className={cn(
                      'font-mono text-xs',
                      isPast ? 'text-muted-foreground/60' : 'text-muted-foreground'
                    )}
                  >
                    {block.duration}m
                  </span>
                )}
              </div>
              {/* Row 2: Preheat time, duration, price, cost - hidden in compact mode */}
              {!isCompact && (
                <div className="flex items-center justify-between" data-testid="block-preheat">
                  <span
                    className={cn(
                      'font-mono text-xs',
                      isPast
                        ? 'text-muted-foreground/60'
                        : isDisabled
                          ? 'text-amber-600/40'
                          : isColdWeather
                            ? 'text-blue-400/80'
                            : 'text-amber-600 dark:text-amber-400'
                    )}
                  >
                    {isColdWeather ? t('schedule.circ') : t('schedule.preheat')} {block.start}
                  </span>
                  <div className="flex items-center gap-3">
                    <span
                      data-testid="block-duration"
                      className={cn(
                        'font-mono text-xs',
                        isPast
                          ? 'text-muted-foreground/60'
                          : isDisabled
                            ? 'text-foreground/40'
                            : 'text-muted-foreground'
                      )}
                    >
                      {block.duration}{t('schedule.min')}
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
                    <span
                      data-testid="block-cost"
                      className={cn(
                        'font-mono text-xs',
                        isPast
                          ? 'text-muted-foreground/60'
                          : isDisabled
                            ? 'text-foreground/50 line-through'
                            : 'text-muted-foreground'
                      )}
                    >
                      €{block.costEur?.toFixed(2) ?? '0.00'}
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Summary */}
      <div className="mt-4 pt-4 border-t border-border flex items-center justify-between text-sm">
        <div className="text-muted-foreground">
          {t('schedule.total')}: <span data-testid="total-minutes" className="font-mono text-foreground">{schedule.scheduledMinutes} {t('schedule.min')}</span>
        </div>
        <div className="text-muted-foreground">
          {t('schedule.cost')}: <span data-testid="total-cost" className="font-mono text-foreground">€{schedule.totalCost?.toFixed(2) ?? '0.00'}</span>
        </div>
        <div className="text-muted-foreground">
          {t('schedule.avg')}: <span data-testid="avg-price" className="font-mono text-success">{avgPrice.toFixed(2)} {t('units.centsPerKwh')}</span>
        </div>
      </div>
    </div>
  );
}
