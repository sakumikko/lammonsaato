import { cn } from '@/lib/utils';
import { HeatPumpState } from '@/types/heating';
import { Zap, Thermometer, Wind } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface HeatPumpUnitProps {
  state: HeatPumpState;
  className?: string;
}

export function HeatPumpUnit({ state, className }: HeatPumpUnitProps) {
  const { t } = useTranslation();
  const isRunning = state.heatEnabled && state.compressorRpm > 0;

  // Map heat pump mode to translation key
  const getModeText = (mode: string) => {
    const modeKey = mode.toLowerCase() as 'heat' | 'cool' | 'off';
    return t(`heatPump.mode.${modeKey}`, mode);
  };

  return (
    <div
      className={cn(
        'relative p-3 md:p-6 rounded-xl md:rounded-2xl border-2 transition-all duration-500',
        isRunning
          ? 'bg-card border-primary/50 box-glow-primary'
          : 'bg-card/50 border-border',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2 md:mb-4">
        <div className="flex items-center gap-1.5 md:gap-2">
          <div
            className={cn(
              'w-2 h-2 md:w-3 md:h-3 rounded-full transition-colors',
              isRunning ? 'bg-success animate-pulse' : 'bg-muted-foreground'
            )}
          />
          <span className="font-semibold text-sm md:text-base text-foreground">{t('heatPump.title')}</span>
        </div>
        <span
          className={cn(
            'text-[10px] md:text-xs font-mono px-1.5 md:px-2 py-0.5 md:py-1 rounded',
            isRunning ? 'bg-success/20 text-success' : 'bg-muted text-muted-foreground'
          )}
        >
          {getModeText(state.heatpumpMode)}
        </span>
      </div>

      {/* Compressor visualization */}
      <div className="flex items-center justify-center mb-2 md:mb-4">
        <div
          className={cn(
            'relative w-14 h-14 md:w-20 md:h-20 rounded-full border-2 md:border-4 flex items-center justify-center transition-all duration-300',
            isRunning
              ? 'border-primary bg-primary/10'
              : 'border-muted bg-muted/50'
          )}
        >
          <Zap
            className={cn(
              'w-6 h-6 md:w-8 md:h-8 transition-all',
              isRunning ? 'text-primary animate-pulse' : 'text-muted-foreground'
            )}
          />
          {isRunning && (
            <div className="absolute inset-0 rounded-full border-2 md:border-4 border-primary/30 animate-ping" />
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2 md:gap-3 text-xs md:text-sm">
        <div className="flex items-center gap-1 md:gap-2">
          <Zap className="w-3 h-3 md:w-4 md:h-4 text-primary" />
          <div>
            <div className="text-muted-foreground text-[10px] md:text-xs">{t('heatPump.compressor')}</div>
            <div className="font-mono text-foreground text-xs md:text-sm">{state.compressorRpm} {t('units.rpm')}</div>
          </div>
        </div>
        <div className="flex items-center gap-1 md:gap-2">
          <Wind className="w-3 h-3 md:w-4 md:h-4 text-cold" />
          <div>
            <div className="text-muted-foreground text-[10px] md:text-xs">{t('heatPump.brinePump')}</div>
            <div className="font-mono text-foreground text-xs md:text-sm">{state.brineCirculationSpeed.toFixed(1)}{t('units.percent')}</div>
          </div>
        </div>
      </div>

      {/* Temperature bars - Condenser (water) circuit */}
      <div className="mt-2 md:mt-4 space-y-1 md:space-y-2">
        <div className="flex items-center justify-between text-[10px] md:text-xs">
          <span className="text-cold flex items-center gap-0.5 md:gap-1">
            <Thermometer className="w-2.5 h-2.5 md:w-3 md:h-3" /> {t('heatPump.condenserIn')}
          </span>
          <span className="font-mono text-cold">{state.condenserInTemp.toFixed(1)}°C</span>
        </div>
        <div className="flex items-center justify-between text-[10px] md:text-xs">
          <span className="text-hot flex items-center gap-0.5 md:gap-1">
            <Thermometer className="w-2.5 h-2.5 md:w-3 md:h-3" /> {t('heatPump.condenserOut')}
          </span>
          <span className="font-mono text-hot">{state.condenserOutTemp.toFixed(1)}°C</span>
        </div>
        <div className="flex items-center justify-between text-[10px] md:text-xs pt-1 border-t border-border/50">
          <span className="text-primary flex items-center gap-0.5 md:gap-1">
            <Thermometer className="w-2.5 h-2.5 md:w-3 md:h-3" /> ΔT
          </span>
          <span className="font-mono text-primary">{state.condenserDeltaT.toFixed(1)}°C</span>
        </div>
      </div>
    </div>
  );
}
