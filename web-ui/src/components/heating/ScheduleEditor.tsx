import { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { ScheduleParameters } from '@/types/heating';
import { Scissors, X, Save, AlertTriangle, Loader2, Euro } from 'lucide-react';
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
  onRecalculate: () => Promise<void>;
}

// Valid options for dropdowns
const BLOCK_DURATIONS = [30, 45, 60];
// Max 5h due to heating window constraint (21:00-07:00 = 600min)
// With breaks equal to block duration, 5.5h+ doesn't fit
const TOTAL_HOURS_OPTIONS = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5];

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
      await onRecalculate();
      setSuccessMessage(t('schedule.editor.success'));
      // Auto-close after success
      setTimeout(() => {
        setIsOpen(false);
        setSuccessMessage(null);
      }, 1500);
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

      {/* All controls in one row */}
      <div className="flex items-end gap-2">
        <div className="flex-1 min-w-0">
          <label className="text-[10px] text-muted-foreground mb-1 block uppercase tracking-wide">
            {t('schedule.editor.minBlock')}
          </label>
          <Select
            value={editParams.minBlockDuration.toString()}
            onValueChange={(v) =>
              setEditParams((p) => ({ ...p, minBlockDuration: parseInt(v) }))
            }
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
              {TOTAL_HOURS_OPTIONS.map((h) => (
                <SelectItem key={h} value={h.toString()} className="text-xs font-mono">
                  {h === 0 ? '0' : `${h}h`}
                </SelectItem>
              ))}
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
