import { useState, useRef } from 'react';
import { cn } from '@/lib/utils';
import { SliderWithFeedback } from '@/components/ui/slider-with-feedback';
import { Input } from '@/components/ui/input';
import { Zap, Sun, Moon, Loader2, Check, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { PeakPowerSettings } from '@/types/heating';
import { PeakPowerSetting, PeakPowerTime } from '@/hooks/useHomeAssistant';

interface PeakPowerSettingsCardProps {
  settings: PeakPowerSettings;
  onSettingChange: (setting: PeakPowerSetting, value: number) => Promise<void>;
  onTimeChange: (setting: PeakPowerTime, time: string) => Promise<void>;
  className?: string;
}

type SaveStatus = 'idle' | 'saving' | 'success' | 'error';

/**
 * Settings card for Peak Power Avoidance feature.
 * Adjusts additional heater thresholds during Helen peak hours (7-21) to avoid peak power charges.
 */
export function PeakPowerSettingsCard({
  settings,
  onSettingChange,
  onTimeChange,
  className,
}: PeakPowerSettingsCardProps) {
  const { t } = useTranslation();

  return (
    <div className={cn('p-4 rounded-xl bg-card border border-border', className)}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <div className="p-1.5 rounded-lg bg-warning/20">
          <Zap className="w-4 h-4 text-warning" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            {t('settings.peakPower.title')}
          </h3>
          <p className="text-xs text-muted-foreground">
            {t('settings.peakPower.description')}
          </p>
        </div>
      </div>

      <div className="space-y-6">
        {/* Daytime Section (Peak Hours) */}
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Sun className="w-4 h-4 text-warning" />
            <span className="text-sm font-medium text-foreground">
              {t('settings.peakPower.daytime')}
            </span>
          </div>

          {/* Daytime Start Time */}
          <TimeInput
            label={t('settings.peakPower.startTime')}
            value={settings.daytimeStartTime}
            onChange={(time) => onTimeChange('daytimeStart', time)}
          />

          {/* Daytime Heater Start */}
          <SliderWithFeedback
            label={t('settings.peakPower.heaterStart')}
            value={settings.daytimeHeaterStart}
            onChange={(v) => onSettingChange('daytimeHeaterStart', v)}
            min={-15}
            max={0}
            step={1}
            unit="°C"
          />

          {/* Daytime Heater Stop */}
          <SliderWithFeedback
            label={t('settings.peakPower.heaterStop')}
            value={settings.daytimeHeaterStop}
            onChange={(v) => onSettingChange('daytimeHeaterStop', v)}
            min={-10}
            max={10}
            step={1}
            unit="°C"
          />
        </div>

        {/* Divider */}
        <div className="border-t border-border" />

        {/* Nighttime Section (Off-Peak Hours) */}
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Moon className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium text-foreground">
              {t('settings.peakPower.nighttime')}
            </span>
          </div>

          {/* Nighttime Start Time */}
          <TimeInput
            label={t('settings.peakPower.startTime')}
            value={settings.nighttimeStartTime}
            onChange={(time) => onTimeChange('nighttimeStart', time)}
          />

          {/* Nighttime Heater Start */}
          <SliderWithFeedback
            label={t('settings.peakPower.heaterStart')}
            value={settings.nighttimeHeaterStart}
            onChange={(v) => onSettingChange('nighttimeHeaterStart', v)}
            min={-15}
            max={0}
            step={1}
            unit="°C"
          />

          {/* Nighttime Heater Stop */}
          <SliderWithFeedback
            label={t('settings.peakPower.heaterStop')}
            value={settings.nighttimeHeaterStop}
            onChange={(v) => onSettingChange('nighttimeHeaterStop', v)}
            min={-10}
            max={10}
            step={1}
            unit="°C"
          />
        </div>
      </div>
    </div>
  );
}

/**
 * Time input component with debounced saving and visual feedback.
 */
interface TimeInputProps {
  label: string;
  value: string;
  onChange: (time: string) => Promise<void>;
}

function TimeInput({ label, value, onChange }: TimeInputProps) {
  const [localValue, setLocalValue] = useState(value);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleChange = (newValue: string) => {
    setLocalValue(newValue);

    // Clear any pending save
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    // Validate time format (HH:MM)
    if (!/^\d{2}:\d{2}$/.test(newValue)) {
      return; // Don't save invalid format
    }

    // Debounce save
    saveTimeoutRef.current = setTimeout(async () => {
      setSaveStatus('saving');
      try {
        await onChange(newValue);
        setSaveStatus('success');
        setTimeout(() => setSaveStatus('idle'), 2000);
      } catch (error) {
        console.error('Failed to save time:', error);
        setSaveStatus('error');
        setLocalValue(value); // Revert on error
        setTimeout(() => setSaveStatus('idle'), 2000);
      }
    }, 500);
  };

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <div className="flex items-center gap-2">
          {saveStatus === 'saving' && (
            <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />
          )}
          {saveStatus === 'success' && (
            <Check className="w-3 h-3 text-success" />
          )}
          {saveStatus === 'error' && (
            <X className="w-3 h-3 text-destructive" />
          )}
        </div>
      </div>
      <Input
        type="time"
        value={localValue}
        onChange={(e) => handleChange(e.target.value)}
        className="w-28 font-mono text-sm"
      />
    </div>
  );
}
