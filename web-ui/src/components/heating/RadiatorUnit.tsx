import { cn } from '@/lib/utils';
import { Home, Thermometer } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface RadiatorUnitProps {
  isActive: boolean;
  supplyTemp: number;
  returnTemp: number;
  className?: string;
}

export function RadiatorUnit({ isActive, supplyTemp, returnTemp, className }: RadiatorUnitProps) {
  const { t } = useTranslation();

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
          <Home
            className={cn(
              'w-4 h-4 md:w-5 md:h-5 transition-colors',
              isActive ? 'text-hot' : 'text-muted-foreground'
            )}
          />
          <span className="font-semibold text-xs md:text-base text-foreground">{t('radiators.title')}</span>
        </div>
        <span
          className={cn(
            'text-[10px] md:text-xs font-mono px-1.5 md:px-2 py-0.5 md:py-1 rounded transition-colors',
            isActive ? 'bg-hot/20 text-hot' : 'bg-muted text-muted-foreground'
          )}
        >
          {isActive ? t('radiators.active') : t('radiators.standby')}
        </span>
      </div>

      {/* Radiator visualization */}
      <div className="flex gap-0.5 md:gap-2 mb-1.5 md:mb-3 h-8 md:h-14">
        {[...Array(5)].map((_, i) => (
          <div
            key={i}
            className={cn(
              'flex-1 rounded transition-all duration-500',
              // Show only 2 bars on mobile
              i >= 2 && 'hidden md:block',
              isActive
                ? 'bg-gradient-to-b from-hot/60 via-hot/40 to-primary/30'
                : 'bg-muted/50'
            )}
            style={{
              animationDelay: `${i * 100}ms`,
            }}
          />
        ))}
      </div>

      {/* Stats - stacked on mobile */}
      <div className="flex flex-col md:grid md:grid-cols-2 gap-0.5 md:gap-2 text-[10px] md:text-xs">
        <div className="flex items-center gap-0.5 md:gap-1">
          <Thermometer className="w-2.5 h-2.5 md:w-3 md:h-3 text-hot" />
          <span className="text-muted-foreground">{t('radiators.supply')}:</span>
          <span className="font-mono text-foreground">{supplyTemp.toFixed(1)}°C</span>
        </div>
        <div className="flex items-center gap-0.5 md:gap-1">
          <Thermometer className="w-2.5 h-2.5 md:w-3 md:h-3 text-cold" />
          <span className="text-muted-foreground">{t('radiators.return')}:</span>
          <span className="font-mono text-foreground">{returnTemp.toFixed(1)}°C</span>
        </div>
      </div>
    </div>
  );
}
