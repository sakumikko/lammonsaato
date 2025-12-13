/**
 * Display component for PID integral values
 *
 * Shows running integrals over 15, 30, and 60 minute windows
 */

import { IntegralResult } from '@/hooks/useIntegralCalculation';

interface IntegralDisplayProps {
  /** Integral calculation results */
  integrals: IntegralResult | null;
  /** Label for the sensor being integrated */
  sensorLabel?: string;
}

function formatIntegral(value: number): string {
  // Format with 1 decimal place, show + for positive values
  const formatted = value.toFixed(1);
  return value >= 0 ? `+${formatted}` : formatted;
}

export function IntegralDisplay({
  integrals,
  sensorLabel = 'PID Sum',
}: IntegralDisplayProps) {
  if (!integrals) {
    return null;
  }

  return (
    <div
      className="bg-card/50 border rounded-lg p-3 mt-4"
      data-testid="integral-display"
    >
      <h3 className="text-sm font-medium text-muted-foreground mb-2">
        {sensorLabel} Integral
      </h3>
      <div className="grid grid-cols-3 gap-4">
        <div data-testid="integral-15m">
          <div className="text-xs text-muted-foreground">15 min</div>
          <div
            className="text-lg font-mono font-semibold"
            data-testid="integral-15m-value"
          >
            {formatIntegral(integrals.integral15m)}
          </div>
        </div>
        <div data-testid="integral-30m">
          <div className="text-xs text-muted-foreground">30 min</div>
          <div
            className="text-lg font-mono font-semibold"
            data-testid="integral-30m-value"
          >
            {formatIntegral(integrals.integral30m)}
          </div>
        </div>
        <div data-testid="integral-60m">
          <div className="text-xs text-muted-foreground">60 min</div>
          <div
            className="text-lg font-mono font-semibold"
            data-testid="integral-60m-value"
          >
            {formatIntegral(integrals.integral60m)}
          </div>
        </div>
      </div>
    </div>
  );
}
