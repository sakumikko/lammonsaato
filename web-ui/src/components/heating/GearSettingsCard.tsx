import { cn } from '@/lib/utils';
import { SliderWithFeedback } from '@/components/ui/slider-with-feedback';
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
  onMinChange: (value: number) => Promise<void>;
  onMaxChange: (value: number) => Promise<void>;
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
  const handleMinChange = async (value: number): Promise<void> => {
    if (value <= maxValue) {
      await onMinChange(value);
    }
  };

  const handleMaxChange = async (value: number): Promise<void> => {
    if (value >= minValue) {
      await onMaxChange(value);
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
        <SliderWithFeedback
          label={t('settings.minimumGear')}
          value={minValue}
          onChange={handleMinChange}
          min={minGear}
          max={maxGear}
          step={1}
          unit=""
        />

        {/* Maximum Gear */}
        <SliderWithFeedback
          label={t('settings.maximumGear')}
          value={maxValue}
          onChange={handleMaxChange}
          min={minGear}
          max={maxGear}
          step={1}
          unit=""
        />
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
