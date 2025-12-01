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
        'relative p-6 rounded-2xl border-2 transition-all duration-500',
        isRunning
          ? 'bg-card border-primary/50 box-glow-primary'
          : 'bg-card/50 border-border',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              'w-3 h-3 rounded-full transition-colors',
              isRunning ? 'bg-success animate-pulse' : 'bg-muted-foreground'
            )}
          />
          <span className="font-semibold text-foreground">{t('heatPump.title')}</span>
        </div>
        <span
          className={cn(
            'text-xs font-mono px-2 py-1 rounded',
            isRunning ? 'bg-success/20 text-success' : 'bg-muted text-muted-foreground'
          )}
        >
          {getModeText(state.heatpumpMode)}
        </span>
      </div>

      {/* Compressor visualization */}
      <div className="flex items-center justify-center mb-4">
        <div
          className={cn(
            'relative w-20 h-20 rounded-full border-4 flex items-center justify-center transition-all duration-300',
            isRunning
              ? 'border-primary bg-primary/10'
              : 'border-muted bg-muted/50'
          )}
        >
          <Zap
            className={cn(
              'w-8 h-8 transition-all',
              isRunning ? 'text-primary animate-pulse' : 'text-muted-foreground'
            )}
          />
          {isRunning && (
            <div className="absolute inset-0 rounded-full border-4 border-primary/30 animate-ping" />
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-primary" />
          <div>
            <div className="text-muted-foreground text-xs">{t('heatPump.compressor')}</div>
            <div className="font-mono text-foreground">{state.compressorRpm} {t('units.rpm')}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Wind className="w-4 h-4 text-cold" />
          <div>
            <div className="text-muted-foreground text-xs">{t('heatPump.brinePump')}</div>
            <div className="font-mono text-foreground">{state.brineCirculationSpeed.toFixed(1)}{t('units.percent')}</div>
          </div>
        </div>
      </div>

      {/* Temperature bars - Condenser (water) circuit */}
      <div className="mt-4 space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-cold flex items-center gap-1">
            <Thermometer className="w-3 h-3" /> {t('heatPump.condenserIn')}
          </span>
          <span className="font-mono text-cold">{state.condenserInTemp.toFixed(1)}°C</span>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="text-hot flex items-center gap-1">
            <Thermometer className="w-3 h-3" /> {t('heatPump.condenserOut')}
          </span>
          <span className="font-mono text-hot">{state.condenserOutTemp.toFixed(1)}°C</span>
        </div>
        <div className="flex items-center justify-between text-xs pt-1 border-t border-border/50">
          <span className="text-primary flex items-center gap-1">
            <Thermometer className="w-3 h-3" /> ΔT
          </span>
          <span className="font-mono text-primary">{state.condenserDeltaT.toFixed(1)}°C</span>
        </div>
      </div>
    </div>
  );
}
