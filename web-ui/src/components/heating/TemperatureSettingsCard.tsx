import { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { LucideIcon, Check, Loader2 } from 'lucide-react';

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
 * Individual temperature input with local state - only saves on blur/Enter
 */
function TemperatureInput({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  unit = '°C',
}: TemperatureSetting) {
  const [localValue, setLocalValue] = useState(value.toString());
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Sync local value when prop changes (from HA)
  useEffect(() => {
    setLocalValue(value.toString());
  }, [value]);

  const handleSave = useCallback(async () => {
    const numValue = parseFloat(localValue);
    if (isNaN(numValue)) {
      setLocalValue(value.toString());
      return;
    }

    // Clamp to min/max
    const clampedValue = Math.min(max, Math.max(min, numValue));

    // Only save if different from current value
    if (clampedValue !== value) {
      setIsSaving(true);
      try {
        await onChange(clampedValue);
        setSaved(true);
        setTimeout(() => setSaved(false), 1500);
      } finally {
        setIsSaving(false);
      }
    }

    // Always update local to clamped value
    setLocalValue(clampedValue.toString());
  }, [localValue, value, min, max, onChange]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSave();
      (e.target as HTMLInputElement).blur();
    } else if (e.key === 'Escape') {
      setLocalValue(value.toString());
      (e.target as HTMLInputElement).blur();
    }
  };

  const hasChanges = parseFloat(localValue) !== value && !isNaN(parseFloat(localValue));

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label className="text-xs text-muted-foreground">{label}</label>
        <span className="text-xs text-muted-foreground/70">
          {min}–{max} {unit}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Input
          type="number"
          value={localValue}
          onChange={(e) => setLocalValue(e.target.value)}
          onBlur={handleSave}
          onKeyDown={handleKeyDown}
          min={min}
          max={max}
          step={step}
          className={cn(
            'h-9 font-mono text-sm',
            hasChanges && 'border-primary ring-1 ring-primary/20'
          )}
        />
        <span className="text-sm text-muted-foreground w-8">{unit}</span>
        <div className="w-5 h-5 flex items-center justify-center">
          {isSaving && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
          {saved && <Check className="w-4 h-4 text-success" />}
        </div>
      </div>
    </div>
  );
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

      {/* Settings inputs */}
      <div className="space-y-4">
        {settings.map((setting, index) => (
          <TemperatureInput
            key={index}
            {...setting}
          />
        ))}
      </div>
    </div>
  );
}
