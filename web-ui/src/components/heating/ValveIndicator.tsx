import { cn } from '@/lib/utils';
import { ValveState } from '@/types/heating';
import { ArrowRight, ArrowDown, RefreshCw } from 'lucide-react';

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
          'relative w-16 h-16 rounded-full border-4 flex items-center justify-center transition-all duration-500 cursor-pointer hover:scale-105 active:scale-95',
          state.transitioning
            ? 'border-warning bg-warning/20 animate-pulse'
            : isPool
              ? 'border-hot bg-hot/20 shadow-glow-hot'
              : 'border-primary bg-primary/20 shadow-glow-primary'
        )}
      >
        {state.transitioning ? (
          <RefreshCw className="w-6 h-6 text-warning animate-spin" />
        ) : (
          <div
            className={cn(
              'w-8 h-2 rounded-full transition-all duration-500',
              isPool ? 'bg-hot rotate-90' : 'bg-primary rotate-0'
            )}
          />
        )}
      </button>

      {/* Direction arrows */}
      <div className="absolute -top-6 left-1/2 -translate-x-1/2">
        <ArrowDown
          className={cn(
            'w-4 h-4 transition-colors',
            !isPool && !state.transitioning ? 'text-primary' : 'text-muted-foreground/30'
          )}
        />
      </div>
      <div className="absolute top-1/2 -right-6 -translate-y-1/2">
        <ArrowRight
          className={cn(
            'w-4 h-4 transition-colors',
            isPool && !state.transitioning ? 'text-hot' : 'text-muted-foreground/30'
          )}
        />
      </div>

    </div>
  );
}
