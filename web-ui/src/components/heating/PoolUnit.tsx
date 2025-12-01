import { cn } from '@/lib/utils';
import { PoolHeatingState } from '@/types/heating';
import { Waves, Euro } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface PoolUnitProps {
  state: PoolHeatingState;
  isActive: boolean;
  className?: string;
}

export function PoolUnit({ state, isActive, className }: PoolUnitProps) {
  const { t } = useTranslation();

  // Get pool status text
  const getStatusText = () => {
    if (isActive) return t('pool.heating');
    if (state.enabled) return t('pool.ready');
    return t('pool.off');
  };

  return (
    <div
      className={cn(
        'relative p-2 md:p-5 rounded-xl md:rounded-2xl border-2 transition-all duration-500',
        isActive
          ? 'bg-hot/10 border-hot/50 shadow-glow-hot'
          : 'bg-card/50 border-border',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-1.5 md:mb-3">
        <div className="flex items-center gap-1.5 md:gap-2">
          <Waves
            className={cn(
              'w-4 h-4 md:w-5 md:h-5 transition-colors',
              isActive ? 'text-hot animate-pulse' : 'text-muted-foreground'
            )}
          />
          <span className="font-semibold text-xs md:text-base text-foreground">{t('pool.title')}</span>
        </div>
        <span
          className={cn(
            'text-[10px] md:text-xs font-mono px-1.5 md:px-2 py-0.5 md:py-1 rounded transition-colors',
            isActive
              ? 'bg-hot/20 text-hot'
              : state.enabled
                ? 'bg-success/20 text-success'
                : 'bg-muted text-muted-foreground'
          )}
        >
          {getStatusText()}
        </span>
      </div>

      {/* Pool visualization */}
      <div className="relative h-10 md:h-16 mb-1.5 md:mb-3 rounded-lg bg-cold/10 border border-cold/30 overflow-hidden">
        <div
          className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-cold/40 to-cold/20 transition-all duration-500"
          style={{ height: '70%' }}
        />
        {isActive && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-3 h-3 md:w-4 md:h-4 rounded-full bg-hot animate-ping opacity-50" />
          </div>
        )}
        <div className="absolute bottom-1 md:bottom-2 right-1 md:right-2 font-mono text-xs md:text-sm text-foreground">
          {state.returnLineTemp.toFixed(1)}°C
        </div>
        <div className="absolute top-1 md:top-2 right-1 md:right-2 text-[10px] md:text-xs text-muted-foreground">
          {t('pool.target')}: {state.targetTemp}°C
        </div>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-1 text-[10px] md:text-xs">
        <Euro className="w-2.5 h-2.5 md:w-3 md:h-3 text-success" />
        <span className="text-muted-foreground">{t('pool.avgPrice')}:</span>
        <span className="font-mono text-foreground">{state.averagePrice.toFixed(2)} {t('units.centsPerKwh')}</span>
      </div>
    </div>
  );
}
