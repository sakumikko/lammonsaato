import { cn } from '@/lib/utils';
import { Slider } from '@/components/ui/slider';
import { LucideIcon } from 'lucide-react';

interface TemperatureSetting {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step?: number;
  unit?: string;
}

interface TemperatureSettingsCardProps {
  title: string;
  icon: LucideIcon;
  iconColorClass: string;
  settings: TemperatureSetting[];
  currentValue?: number;
  currentLabel?: string;
  className?: string;
}

/**
 * Card component for configuring temperature-based settings
 */
export function TemperatureSettingsCard({
  title,
  icon: Icon,
  iconColorClass,
  settings,
  currentValue,
  currentLabel,
  className,
}: TemperatureSettingsCardProps) {
  return (
    <div className={cn('p-4 rounded-xl bg-card border border-border', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className={cn('p-1.5 rounded-lg', `${iconColorClass}/20`)}>
            <Icon className={cn('w-4 h-4', iconColorClass)} />
          </div>
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        </div>
        {currentValue !== undefined && currentLabel && (
          <div className={cn('px-2 py-1 rounded-lg text-xs font-mono', `${iconColorClass}/20`, iconColorClass)}>
            {currentLabel}: {currentValue.toFixed(1)}°C
          </div>
        )}
      </div>

      {/* Settings sliders */}
      <div className="space-y-4">
        {settings.map((setting, index) => (
          <div key={index} className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">{setting.label}</span>
              <span className="font-mono text-sm text-foreground">
                {setting.value.toFixed(setting.step && setting.step < 1 ? 1 : 0)}{setting.unit || '°C'}
              </span>
            </div>
            <Slider
              value={[setting.value]}
              onValueChange={([value]) => setting.onChange(value)}
              min={setting.min}
              max={setting.max}
              step={setting.step || 1}
              className="w-full"
            />
            <div className="flex justify-between text-[10px] text-muted-foreground">
              <span>{setting.min}{setting.unit || '°C'}</span>
              <span>{setting.max}{setting.unit || '°C'}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
