import { useTranslation } from 'react-i18next';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { TimeRange } from '@/types/analytics';

interface TimeRangeSelectorProps {
  value: TimeRange;
  onChange: (value: TimeRange) => void;
}

export function TimeRangeSelector({ value, onChange }: TimeRangeSelectorProps) {
  const { t } = useTranslation();

  const ranges: { value: TimeRange; label: string }[] = [
    { value: '1w', label: t('analytics.timeRange.1w') },
    { value: '4w', label: t('analytics.timeRange.4w') },
    { value: '3m', label: t('analytics.timeRange.3m') },
    { value: '12m', label: t('analytics.timeRange.12m') },
  ];

  return (
    <ToggleGroup
      type="single"
      value={value}
      onValueChange={(v) => v && onChange(v as TimeRange)}
      className="justify-start"
    >
      {ranges.map((range) => (
        <ToggleGroupItem
          key={range.value}
          value={range.value}
          aria-label={range.label}
          className="px-4 py-2 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"
        >
          {range.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
