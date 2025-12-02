import { cn } from '@/lib/utils';

interface GearRangeIndicatorProps {
  min: number;
  max: number;
  minGear?: number;
  maxGear?: number;
  currentGear?: number;
  colorClass?: string;
  className?: string;
}

/**
 * Visual indicator showing gear range as dots
 * Highlights the allowed range between min and max values
 */
export function GearRangeIndicator({
  min,
  max,
  minGear = 1,
  maxGear = 10,
  currentGear,
  colorClass = 'bg-primary',
  className,
}: GearRangeIndicatorProps) {
  const gears = Array.from({ length: maxGear - minGear + 1 }, (_, i) => minGear + i);

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <div className="flex items-center justify-between gap-1">
        {gears.map((gear) => {
          const isInRange = gear >= min && gear <= max;
          const isCurrent = currentGear !== undefined && gear === currentGear;

          return (
            <div
              key={gear}
              className={cn(
                'w-2.5 h-2.5 rounded-full transition-all duration-300',
                isInRange ? colorClass : 'bg-muted',
                isCurrent && 'ring-2 ring-foreground ring-offset-1 ring-offset-background scale-125'
              )}
              title={`Gear ${gear}${isCurrent ? ' (current)' : ''}`}
            />
          );
        })}
      </div>
      <div className="flex items-center justify-between text-[10px] text-muted-foreground font-mono">
        <span>{minGear}</span>
        <span>{maxGear}</span>
      </div>
    </div>
  );
}
