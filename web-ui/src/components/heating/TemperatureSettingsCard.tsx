import { cn } from '@/lib/utils';
import { SliderWithFeedback } from '@/components/ui/slider-with-feedback';
import { LucideIcon } from 'lucide-react';

interface TemperatureSetting {
  label: string;
  value: number;
  onChange: (value: number) => Promise<void>;
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
          <SliderWithFeedback
            key={index}
            label={setting.label}
            value={setting.value}
            onChange={setting.onChange}
            min={setting.min}
            max={setting.max}
            step={setting.step || 1}
            unit={setting.unit || '°C'}
          />
        ))}
      </div>
    </div>
  );
}
