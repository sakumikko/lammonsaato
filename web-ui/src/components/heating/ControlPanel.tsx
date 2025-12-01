import { cn } from '@/lib/utils';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import { HeatPumpState, PoolHeatingState } from '@/types/heating';
import { Power, Waves, Target, Thermometer } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface ControlPanelProps {
  heatPump: HeatPumpState;
  poolHeating: PoolHeatingState;
  onPoolEnabledChange: (enabled: boolean) => void;
  onPoolTempChange: (temp: number) => void;
  className?: string;
}

export function ControlPanel({
  heatPump,
  poolHeating,
  onPoolEnabledChange,
  onPoolTempChange,
  className,
}: ControlPanelProps) {
  const { t } = useTranslation();

  // Map heat pump mode to translation key
  const getModeText = (mode: string) => {
    const modeKey = mode.toLowerCase() as 'heat' | 'cool' | 'off';
    return t(`heatPump.mode.${modeKey}`, mode);
  };

  return (
    <div className={cn('space-y-4', className)}>
      {/* Heat Pump Controls */}
      <div className="p-4 rounded-xl bg-card border border-border">
        <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
          <Power className="w-4 h-4 text-primary" />
          {t('controls.title')}
        </h3>

        <div className="space-y-3">
          {/* Heat Pump Status (read-only) */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div
                className={cn(
                  'w-2 h-2 rounded-full transition-colors',
                  heatPump.heatEnabled ? 'bg-success animate-pulse' : 'bg-muted-foreground'
                )}
              />
              <span className="text-sm text-foreground">{t('heatPump.title')}</span>
            </div>
            <span className={cn(
              'text-xs font-mono px-2 py-1 rounded',
              heatPump.heatEnabled ? 'bg-success/20 text-success' : 'bg-muted text-muted-foreground'
            )}>
              {getModeText(heatPump.heatpumpMode)}
            </span>
          </div>

          {/* Compressor RPM */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{t('heatPump.compressor')}</span>
            <span className="font-mono text-foreground">{heatPump.compressorRpm} {t('units.rpm')}</span>
          </div>

          {/* Brine Pump */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{t('heatPump.brinePump')}</span>
            <span className="font-mono text-foreground">{heatPump.brineCirculationSpeed.toFixed(0)}{t('units.percent')}</span>
          </div>
        </div>
      </div>

      {/* Pool Controls */}
      <div className="p-4 rounded-xl bg-card border border-border">
        <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
          <Waves className="w-4 h-4 text-hot" />
          {t('controls.poolHeating')}
        </h3>

        <div className="space-y-4">
          {/* Scheduled Heating Enabled */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div
                className={cn(
                  'w-2 h-2 rounded-full transition-colors',
                  poolHeating.enabled ? 'bg-success' : 'bg-muted-foreground'
                )}
              />
              <span className="text-sm text-foreground">{t('controls.scheduledHeating')}</span>
            </div>
            <Switch
              checked={poolHeating.enabled}
              onCheckedChange={onPoolEnabledChange}
            />
          </div>

          {/* Target Temperature */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-hot" />
                <span className="text-sm text-foreground">{t('controls.targetTemperature')}</span>
              </div>
              <span className="font-mono text-sm text-hot">{poolHeating.targetTemp}°C</span>
            </div>
            <Slider
              value={[poolHeating.targetTemp]}
              onValueChange={([value]) => onPoolTempChange(value)}
              min={20}
              max={32}
              step={0.5}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>20°C</span>
              <span>32°C</span>
            </div>
          </div>
        </div>
      </div>

      {/* Outdoor Temperature */}
      <div className="p-4 rounded-xl bg-card border border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Thermometer className="w-4 h-4 text-cold" />
            <span className="text-sm text-foreground">{t('controls.outdoor')}</span>
          </div>
          <span className="font-mono text-lg text-foreground">
            {heatPump.outdoorTemp.toFixed(1)}°C
          </span>
        </div>
      </div>
    </div>
  );
}
