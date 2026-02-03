import { useState, useCallback, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { ScheduleParameters } from '@/types/heating';
import { Scissors, X, Save, AlertTriangle, Loader2, Euro, Snowflake } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useTranslation } from 'react-i18next';

interface ScheduleEditorProps {
  parameters: ScheduleParameters;
  isInHeatingWindow: boolean;
  onSave: (params: ScheduleParameters) => Promise<void>;
  onRecalculate: () => Promise<boolean>;
}

// Valid options for dropdowns
const BLOCK_DURATIONS = [30, 45, 60];
const BREAK_DURATIONS = [60, 75, 90, 105, 120];
// Max 5h (300min) due to heating window constraint (21:00-07:00 = 600min)
// With breaks equal to block duration, 5.5h+ doesn't fit
const MAX_TOTAL_MINUTES = 300;

// Cold weather mode options
const COLD_BLOCK_DURATIONS = [5, 10, 15];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

// Parse enabled hours from comma-separated string to Set
const parseEnabledHours = (str: string): Set<number> => {
  const hours = new Set<number>();
  if (str) {
    for (const h of str.split(',')) {
      const parsed = parseInt(h.trim());
      if (!isNaN(parsed) && parsed >= 0 && parsed <= 23) {
        hours.add(parsed);
      }
    }
  }
  return hours;
};

// Convert Set to sorted comma-separated string
const hoursToString = (hours: Set<number>): string => {
  return Array.from(hours).sort((a, b) => a - b).join(',');
};

// Generate all valid total hours as multiples of min block duration
// This prevents schedule calculation failures when total minutes % block size != 0
const getValidTotalHours = (minBlockDuration: number): number[] => {
  const options: number[] = [0];
  for (let minutes = minBlockDuration; minutes <= MAX_TOTAL_MINUTES; minutes += minBlockDuration) {
    options.push(minutes / 60);
  }
  return options;
};

// Find closest valid total hours value
const findClosestValidHours = (current: number, minBlockDuration: number): number => {
  const validOptions = getValidTotalHours(minBlockDuration);
  if (validOptions.includes(current)) return current;
  // Find closest valid value
  return validOptions.reduce((prev, curr) =>
    Math.abs(curr - current) < Math.abs(prev - current) ? curr : prev
  );
};

export function useScheduleEditor({
  parameters,
  isInHeatingWindow,
  onSave,
  onRecalculate,
}: ScheduleEditorProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showWarning, setShowWarning] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Local edit state
  const [editParams, setEditParams] = useState<ScheduleParameters>(parameters);
  // Separate string state for cost input (allows typing with comma)
  const [costInputValue, setCostInputValue] = useState<string>(
    parameters.maxCostEur?.toString() ?? ''
  );

  // Reset edit state when opening
  const handleOpen = useCallback(() => {
    setEditParams(parameters);
    setCostInputValue(parameters.maxCostEur?.toString() ?? '');
    setSuccessMessage(null);
    setIsOpen(true);
  }, [parameters]);

  // Parse cost input: accepts both . and , as decimal separator
  const parseCostValue = (input: string): number | null => {
    if (input === '') return null;
    // Replace comma with dot and parse
    const normalized = input.replace(',', '.');
    const parsed = parseFloat(normalized);
    return isNaN(parsed) ? null : parsed;
  };

  // Validate min <= max
  const isValid = editParams.minBlockDuration <= editParams.maxBlockDuration;

  // Handle save and recalculate
  const doSaveAndRecalculate = useCallback(async () => {
    setIsLoading(true);
    setSuccessMessage(null);
    try {
      await onSave(editParams);
      const recalcSucceeded = await onRecalculate();
      if (recalcSucceeded) {
        setSuccessMessage(t('schedule.editor.success'));
      } else {
        // Recalculation failed (likely no prices available)
        // Parameters are saved and will apply at next calculation
        setSuccessMessage(t('schedule.editor.successPending'));
      }
      // Auto-close after success
      setTimeout(() => {
        setIsOpen(false);
        setSuccessMessage(null);
      }, 2000);
    } catch (error) {
      console.error('Failed to save schedule parameters:', error);
    } finally {
      setIsLoading(false);
    }
  }, [editParams, onSave, onRecalculate, t]);

  const handleSave = useCallback(async () => {
    if (!isValid) return;

    // If in heating window, show warning first
    if (isInHeatingWindow) {
      setShowWarning(true);
      return;
    }

    await doSaveAndRecalculate();
  }, [isValid, isInHeatingWindow, doSaveAndRecalculate]);

  const handleConfirmWarning = useCallback(async () => {
    setShowWarning(false);
    await doSaveAndRecalculate();
  }, [doSaveAndRecalculate]);

  // Button component - Scissors icon for "cost cutting" 💰✂️
  const EditorButton = (
    <Button
      data-testid="schedule-editor-toggle"
      variant="ghost"
      size="sm"
      onClick={() => isOpen ? setIsOpen(false) : handleOpen()}
      className={cn(
        "h-9 w-9 p-0 text-warning hover:text-warning/80 hover:bg-warning/10",
        isOpen && "text-primary bg-primary/10"
      )}
    >
      {isOpen ? <X className="w-6 h-6" /> : <Scissors className="w-6 h-6" />}
    </Button>
  );

  // Panel component
  const EditorPanel = isOpen ? (
    <div data-testid="schedule-editor-panel" className="p-3 rounded-lg bg-muted/50 border border-border mb-4">
      {/* Header with pun */}
      <div className="flex items-center gap-2 mb-3 pb-2 border-b border-border/50">
        <Scissors className="w-5 h-5 text-warning" />
        <span className="text-sm font-medium text-foreground">{t('schedule.editor.costCutting')}</span>
      </div>

      {/* Success message */}
      {successMessage && (
        <div className="mb-3 p-2 rounded bg-success/20 text-success text-xs flex items-center gap-2">
          <Save className="w-3 h-3" />
          {successMessage}
        </div>
      )}

      {/* Cold weather mode toggle */}
      <div className="flex items-center gap-2 mb-3 pb-2 border-b border-border/50">
        <Switch
          data-testid="cold-weather-toggle"
          checked={editParams.coldWeatherMode}
          onCheckedChange={(checked) =>
            setEditParams((p) => ({ ...p, coldWeatherMode: checked }))
          }
        />
        <span className="text-sm text-foreground flex items-center gap-1">
          <Snowflake className="w-4 h-4 text-blue-400" />
          {t('schedule.editor.coldWeatherMode')}
        </span>
      </div>

      {/* Cold weather mode controls */}
      {editParams.coldWeatherMode ? (
        <>
          {/* Hour selection grid */}
          <div className="mb-3">
            <label className="text-[10px] text-muted-foreground mb-2 block uppercase tracking-wide">
              {t('schedule.editor.enabledHours')}
            </label>
            <div data-testid="cold-hour-grid" className="grid grid-cols-6 gap-1">
              {HOURS.map((hour) => {
                const enabledHours = parseEnabledHours(editParams.coldEnabledHours);
                const isSelected = enabledHours.has(hour);
                return (
                  <button
                    key={hour}
                    data-testid={`cold-hour-${hour}`}
                    data-selected={isSelected}
                    onClick={() => {
                      const newHours = new Set(enabledHours);
                      if (newHours.has(hour)) {
                        newHours.delete(hour);
                      } else {
                        newHours.add(hour);
                      }
                      setEditParams((p) => ({
                        ...p,
                        coldEnabledHours: hoursToString(newHours),
                      }));
                    }}
                    className={cn(
                      "h-7 text-xs font-mono rounded border transition-colors",
                      isSelected
                        ? "bg-blue-500 text-white border-blue-600"
                        : "bg-muted/50 text-muted-foreground border-border hover:bg-muted"
                    )}
                  >
                    {hour.toString().padStart(2, '0')}
                  </button>
                );
              })}
            </div>
            <p className="text-[10px] text-muted-foreground mt-1">
              {t('schedule.editor.blocksAtFive')}
            </p>
          </div>

          {/* Cold weather settings row */}
          <div className="flex items-end gap-2 mb-2">
            <div className="flex-1 min-w-0">
              <label className="text-[10px] text-muted-foreground mb-1 block uppercase tracking-wide">
                {t('schedule.editor.blockDuration')}
              </label>
              <Select
                value={editParams.coldBlockDuration.toString()}
                onValueChange={(v) =>
                  setEditParams((p) => ({ ...p, coldBlockDuration: parseInt(v) }))
                }
              >
                <SelectTrigger data-testid="select-cold-duration" className="h-8 text-xs font-mono">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {COLD_BLOCK_DURATIONS.map((d) => (
                    <SelectItem key={d} value={d.toString()} className="text-xs font-mono">
                      {d} min
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex-1 min-w-0">
              <label className="text-[10px] text-muted-foreground mb-1 block uppercase tracking-wide">
                {t('schedule.editor.preCirc')}
              </label>
              <Input
                data-testid="input-cold-pre-circulation"
                type="number"
                min={0}
                max={10}
                value={editParams.coldPreCirculation}
                onChange={(e) =>
                  setEditParams((p) => ({
                    ...p,
                    coldPreCirculation: Math.max(0, Math.min(10, parseInt(e.target.value) || 0)),
                  }))
                }
                className="h-8 text-xs font-mono"
              />
            </div>
            <div className="flex-1 min-w-0">
              <label className="text-[10px] text-muted-foreground mb-1 block uppercase tracking-wide">
                {t('schedule.editor.postCirc')}
              </label>
              <Input
                data-testid="input-cold-post-circulation"
                type="number"
                min={0}
                max={10}
                value={editParams.coldPostCirculation}
                onChange={(e) =>
                  setEditParams((p) => ({
                    ...p,
                    coldPostCirculation: Math.max(0, Math.min(10, parseInt(e.target.value) || 0)),
                  }))
                }
                className="h-8 text-xs font-mono"
              />
            </div>
            <Button
              data-testid="schedule-editor-save"
              onClick={handleSave}
              disabled={isLoading}
              size="sm"
              className="h-8 px-3"
            >
              {isLoading ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Save className="w-3 h-3" />
              )}
            </Button>
          </div>
        </>
      ) : (
        <>
          {/* Row 1: Block duration settings */}
      <div className="flex items-end gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <label className="text-[10px] text-muted-foreground mb-1 block uppercase tracking-wide">
            {t('schedule.editor.minBlock')}
          </label>
          <Select
            value={editParams.minBlockDuration.toString()}
            onValueChange={(v) => {
              const newMinBlock = parseInt(v);
              setEditParams((p) => ({
                ...p,
                minBlockDuration: newMinBlock,
                // Auto-adjust totalHours to closest valid value for new min block
                totalHours: findClosestValidHours(p.totalHours, newMinBlock),
              }));
            }}
          >
            <SelectTrigger data-testid="select-min-block" className="h-8 text-xs font-mono">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {BLOCK_DURATIONS.map((d) => (
                <SelectItem key={d} value={d.toString()} className="text-xs font-mono">
                  {d}m
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex-1 min-w-0">
          <label className="text-[10px] text-muted-foreground mb-1 block uppercase tracking-wide">
            {t('schedule.editor.maxBlock')}
          </label>
          <Select
            value={editParams.maxBlockDuration.toString()}
            onValueChange={(v) =>
              setEditParams((p) => ({ ...p, maxBlockDuration: parseInt(v) }))
            }
          >
            <SelectTrigger data-testid="select-max-block" className={cn('h-8 text-xs font-mono', !isValid && 'border-destructive')}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {BLOCK_DURATIONS.map((d) => (
                <SelectItem key={d} value={d.toString()} className="text-xs font-mono">
                  {d}m
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex-1 min-w-0">
          <label className="text-[10px] text-muted-foreground mb-1 block uppercase tracking-wide">
            {t('schedule.editor.minBreak')}
          </label>
          <Select
            value={editParams.minBreakDuration.toString()}
            onValueChange={(v) =>
              setEditParams((p) => ({ ...p, minBreakDuration: parseInt(v) }))
            }
          >
            <SelectTrigger data-testid="select-min-break" className="h-8 text-xs font-mono">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {BREAK_DURATIONS.map((d) => (
                <SelectItem key={d} value={d.toString()} className="text-xs font-mono">
                  {d}m
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Row 2: Time and cost settings */}
      <div className="flex items-end gap-2">
        <div className="flex-1 min-w-0">
          <label className="text-[10px] text-muted-foreground mb-1 block uppercase tracking-wide">
            {t('schedule.editor.totalHours')}
          </label>
          <Select
            value={editParams.totalHours.toString()}
            onValueChange={(v) =>
              setEditParams((p) => ({ ...p, totalHours: parseFloat(v) }))
            }
          >
            <SelectTrigger data-testid="select-total-hours" className="h-8 text-xs font-mono">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {getValidTotalHours(editParams.minBlockDuration).map((h) => {
                // Format hours: 0, 45m, 1h, 1h 30m, 2h 15m, etc.
                if (h === 0) return <SelectItem key={h} value={h.toString()} className="text-xs font-mono">0</SelectItem>;
                const hours = Math.floor(h);
                const minutes = Math.round((h - hours) * 60);
                const label = hours > 0 && minutes > 0
                  ? `${hours}h ${minutes}m`
                  : hours > 0
                    ? `${hours}h`
                    : `${minutes}m`;
                return <SelectItem key={h} value={h.toString()} className="text-xs font-mono">{label}</SelectItem>;
              })}
            </SelectContent>
          </Select>
        </div>
        <div className="flex-1 min-w-0">
          <label className="text-[10px] text-muted-foreground mb-1 block uppercase tracking-wide">
            {t('schedule.editor.maxCost')}
          </label>
          <div className="relative">
            <Euro className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-muted-foreground" />
            <Input
              data-testid="input-max-cost"
              type="text"
              inputMode="decimal"
              placeholder={t('schedule.editor.noLimit')}
              value={costInputValue}
              onChange={(e) => {
                // Accept both . and , as decimal separators, only allow numeric input
                const raw = e.target.value;
                // Remove all non-numeric chars except . and ,
                const cleaned = raw.replace(/[^0-9.,]/g, '');
                // Only allow one decimal separator
                const firstDecimal = cleaned.search(/[.,]/);
                const value = firstDecimal >= 0
                  ? cleaned.slice(0, firstDecimal + 1) + cleaned.slice(firstDecimal + 1).replace(/[.,]/g, '')
                  : cleaned;
                setCostInputValue(value);
                // Update editParams with parsed value
                setEditParams((p) => ({
                  ...p,
                  maxCostEur: parseCostValue(value),
                }));
              }}
              className="h-8 text-xs font-mono pl-6 w-full"
            />
          </div>
        </div>
        <Button
          data-testid="schedule-editor-save"
          onClick={handleSave}
          disabled={!isValid || isLoading}
          size="sm"
          className="h-8 px-3"
        >
          {isLoading ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <Save className="w-3 h-3" />
          )}
        </Button>
      </div>

          {/* Validation error */}
          {!isValid && (
            <p className="text-[10px] text-destructive mt-2">
              {t('schedule.editor.minMaxError')}
            </p>
          )}
        </>
      )}
    </div>
  ) : null;

  // Warning dialog
  const WarningDialog = (
    <AlertDialog open={showWarning} onOpenChange={setShowWarning}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-warning" />
            {t('schedule.editor.warningTitle')}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {t('schedule.editor.warningDescription')}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
          <AlertDialogAction onClick={handleConfirmWarning}>
            {t('schedule.editor.applyNow')}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );

  return {
    isOpen,
    EditorButton,
    EditorPanel,
    WarningDialog,
  };
}
