/**
 * Time range selector component for multi-entity graph
 */

import { TimeRange } from '@/types/graphs';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface TimeRangeSelectorProps {
  value: TimeRange;
  onChange: (value: TimeRange) => void;
}

const TIME_RANGES: { value: TimeRange; label: string }[] = [
  { value: '1h', label: '1h' },
  { value: '6h', label: '6h' },
  { value: '24h', label: '24h' },
  { value: '7d', label: '7d' },
];

export function TimeRangeSelector({ value, onChange }: TimeRangeSelectorProps) {
  return (
    <div className="flex gap-1">
      {TIME_RANGES.map(range => (
        <Button
          key={range.value}
          variant={value === range.value ? 'default' : 'outline'}
          size="sm"
          onClick={() => onChange(range.value)}
          data-testid={`time-range-${range.value}`}
          data-active={value === range.value}
          className={cn(
            'px-3',
            value === range.value && 'pointer-events-none'
          )}
        >
          {range.label}
        </Button>
      ))}
    </div>
  );
}
