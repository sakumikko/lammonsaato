import { useState, useEffect, useRef } from 'react';
import { Slider } from '@/components/ui/slider';
import { Loader2, Check, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SliderWithFeedbackProps {
  value: number;
  onChange: (value: number) => Promise<void>;
  min: number;
  max: number;
  step?: number;
  label: string;
  unit?: string;
  className?: string;
}

type SaveStatus = 'idle' | 'saving' | 'success' | 'error';

/**
 * Slider component with optimistic updates, debounced saving, and visual feedback.
 *
 * Behavior:
 * - While dragging: Local value updates instantly
 * - After drag stops (500ms): "Saving" spinner appears
 * - On success: Green checkmark appears briefly (2s)
 * - On error: Red X appears, slider reverts to server value
 */
export function SliderWithFeedback({
  value,
  onChange,
  min,
  max,
  step = 1,
  label,
  unit = '°C',
  className,
}: SliderWithFeedbackProps) {
  const [localValue, setLocalValue] = useState(value);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const statusTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const serverValueRef = useRef(value);

  // Track if we're in the middle of a user-initiated change
  const isPendingRef = useRef(false);
  // Track when the last save completed to prevent immediate server value sync
  const lastSaveTimeRef = useRef(0);
  const SYNC_GRACE_PERIOD = 2000; // Don't sync from server for 2s after save

  // Sync with server value when it changes externally
  useEffect(() => {
    const timeSinceLastSave = Date.now() - lastSaveTimeRef.current;
    const withinGracePeriod = timeSinceLastSave < SYNC_GRACE_PERIOD;

    // Only sync if:
    // 1. Not currently saving
    // 2. Not pending (user just made a change, waiting for debounce/save)
    // 3. Not within grace period after save (let optimistic value persist)
    // 4. The value actually differs from server value (avoid unnecessary updates)
    if (!isPendingRef.current && saveStatus !== 'saving' && !withinGracePeriod && value !== serverValueRef.current) {
      serverValueRef.current = value;
      setLocalValue(value);
    }
  }, [value, saveStatus]);

  // Clear status after delay
  useEffect(() => {
    if (saveStatus === 'success' || saveStatus === 'error') {
      statusTimeoutRef.current = setTimeout(() => {
        setSaveStatus('idle');
      }, 2000);
      return () => {
        if (statusTimeoutRef.current) {
          clearTimeout(statusTimeoutRef.current);
        }
      };
    }
  }, [saveStatus]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
      if (statusTimeoutRef.current) clearTimeout(statusTimeoutRef.current);
    };
  }, []);

  const handleChange = (newValue: number) => {
    // Update local state immediately (optimistic)
    setLocalValue(newValue);

    // Mark as pending user change
    isPendingRef.current = true;

    // Reset status when user starts interacting
    if (saveStatus !== 'idle') {
      setSaveStatus('idle');
    }

    // Clear any pending save
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    // Debounce: wait 500ms after last change before saving
    saveTimeoutRef.current = setTimeout(async () => {
      setSaveStatus('saving');
      try {
        await onChange(newValue);
        setSaveStatus('success');
        serverValueRef.current = newValue;
        // Record save time to prevent immediate server sync
        lastSaveTimeRef.current = Date.now();
      } catch (error) {
        console.error('Failed to save slider value:', error);
        setSaveStatus('error');
        // Revert to last known server value on error
        setLocalValue(serverValueRef.current);
      } finally {
        // Clear pending flag after save attempt completes
        isPendingRef.current = false;
      }
    }, 500);
  };

  const formatValue = (val: number) => {
    return step < 1 ? val.toFixed(1) : val.toFixed(0);
  };

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <div className="flex items-center gap-2">
          {/* Status indicators */}
          {saveStatus === 'saving' && (
            <Loader2
              className="w-3 h-3 animate-spin text-muted-foreground"
              data-testid="slider-saving"
            />
          )}
          {saveStatus === 'success' && (
            <Check
              className="w-3 h-3 text-success"
              data-testid="slider-success"
            />
          )}
          {saveStatus === 'error' && (
            <X
              className="w-3 h-3 text-destructive"
              data-testid="slider-error"
            />
          )}
          {/* Value display */}
          <span className="font-mono text-sm text-foreground" data-testid="slider-value">
            {formatValue(localValue)}{unit}
          </span>
        </div>
      </div>
      <Slider
        value={[localValue]}
        onValueChange={([v]) => handleChange(v)}
        min={min}
        max={max}
        step={step}
        className="w-full"
        data-testid="slider-input"
      />
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>{min}{unit}</span>
        <span>{max}{unit}</span>
      </div>
    </div>
  );
}
