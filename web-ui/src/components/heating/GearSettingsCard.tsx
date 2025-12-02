import { cn } from '@/lib/utils';
import { Slider } from '@/components/ui/slider';
import { GearRangeIndicator } from './GearRangeIndicator';
import { LucideIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface GearSettingsCardProps {
  title: string;
  icon: LucideIcon;
  iconColorClass: string;
  rangeColorClass: string;
  minValue: number;
  maxValue: number;
  currentGear?: number;
  onMinChange: (value: number) => void;
  onMaxChange: (value: number) => void;
  minGear?: number;
  maxGear?: number;
  className?: string;
}

/**
 * Card component for configuring gear limits for a heating circuit
 */
export function GearSettingsCard({
  title,
  icon: Icon,
  iconColorClass,
  rangeColorClass,
  minValue,
  maxValue,
  currentGear,
  onMinChange,
  onMaxChange,
  minGear = 1,
  maxGear = 10,
  className,
}: GearSettingsCardProps) {
  const { t } = useTranslation();

  // Ensure min doesn't exceed max and vice versa
  const handleMinChange = (value: number) => {
    if (value <= maxValue) {
      onMinChange(value);
    }
  };

  const handleMaxChange = (value: number) => {
    if (value >= minValue) {
      onMaxChange(value);
    }
  };

  return (
    <div className={cn('p-4 rounded-xl bg-card border border-border', className)}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <div className={cn('p-1.5 rounded-lg', `${iconColorClass}/20`)}>
          <Icon className={cn('w-4 h-4', iconColorClass)} />
        </div>
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {currentGear !== undefined && (
          <span className="ml-auto text-xs font-mono text-muted-foreground">
            {t('settings.currentGear')}: {currentGear}
          </span>
        )}
      </div>

      {/* Sliders */}
      <div className="space-y-4">
        {/* Minimum Gear */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">{t('settings.minimumGear')}</span>
            <span className="font-mono text-sm text-foreground">{minValue}</span>
          </div>
          <Slider
            value={[minValue]}
            onValueChange={([value]) => handleMinChange(value)}
            min={minGear}
            max={maxGear}
            step={1}
            className="w-full"
          />
        </div>

        {/* Maximum Gear */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">{t('settings.maximumGear')}</span>
            <span className="font-mono text-sm text-foreground">{maxValue}</span>
          </div>
          <Slider
            value={[maxValue]}
            onValueChange={([value]) => handleMaxChange(value)}
            min={minGear}
            max={maxGear}
            step={1}
            className="w-full"
          />
        </div>
      </div>

      {/* Visual Range Indicator */}
      <div className="mt-4 pt-3 border-t border-border">
        <GearRangeIndicator
          min={minValue}
          max={maxValue}
          minGear={minGear}
          maxGear={maxGear}
          currentGear={currentGear}
          colorClass={rangeColorClass}
        />
      </div>
    </div>
  );
}
