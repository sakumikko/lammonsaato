import { cn } from '@/lib/utils';
import { ValveState } from '@/types/heating';
import { ArrowDown, RefreshCw } from 'lucide-react';

interface ValveIndicatorProps {
  state: ValveState;
  onToggle?: () => void;
  className?: string;
}

export function ValveIndicator({ state, onToggle, className }: ValveIndicatorProps) {
  const isPool = state.position === 'pool';

  return (
    <div className={cn('relative', className)}>
      {/* Valve body */}
      <button
        onClick={onToggle}
        disabled={state.transitioning}
        className={cn(
          'relative w-10 h-10 md:w-16 md:h-16 rounded-full border-2 md:border-4 flex items-center justify-center transition-all duration-500 cursor-pointer hover:scale-105 active:scale-95',
          state.transitioning
            ? 'border-warning bg-warning/20 animate-pulse'
            : 'border-hot bg-hot/20 shadow-glow-hot'
        )}
      >
        {state.transitioning ? (
          <RefreshCw className="w-4 h-4 md:w-6 md:h-6 text-warning animate-spin" />
        ) : (
          /* L-shaped connector: vertical to heat pump (bottom), horizontal to active circuit */
          <>
            {/* Vertical bar - from center going DOWN to heat pump */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 w-1.5 h-1/2 md:w-2 bg-hot rounded-full" />
            {/* Horizontal bar - goes LEFT to pool or RIGHT to radiators */}
            <div
              className={cn(
                'absolute top-1/2 -translate-y-1/2 w-1/2 h-1.5 md:h-2 bg-hot rounded-full transition-all duration-500',
                isPool ? 'right-1/2' : 'left-1/2'
              )}
            />
            {/* Junction circle for smooth corner */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1.5 h-1.5 md:w-2 md:h-2 bg-hot rounded-full" />
          </>
        )}
      </button>

      {/* Arrow from heat pump */}
      <div className="absolute -bottom-4 md:-bottom-6 left-1/2 -translate-x-1/2">
        <ArrowDown
          className={cn(
            'w-3 h-3 md:w-4 md:h-4 rotate-180 transition-colors',
            !state.transitioning ? 'text-hot' : 'text-muted-foreground/30'
          )}
        />
      </div>

    </div>
  );
}
