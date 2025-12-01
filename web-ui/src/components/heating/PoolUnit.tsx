import { cn } from '@/lib/utils';
import { PoolHeatingState } from '@/types/heating';
import { Waves, Euro } from 'lucide-react';

interface PoolUnitProps {
  state: PoolHeatingState;
  isActive: boolean;
  className?: string;
}

export function PoolUnit({ state, isActive, className }: PoolUnitProps) {
  return (
    <div
      className={cn(
        'relative p-5 rounded-2xl border-2 transition-all duration-500',
        isActive
          ? 'bg-hot/10 border-hot/50 box-glow-accent'
          : 'bg-card/50 border-border',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Waves
            className={cn(
              'w-5 h-5 transition-colors',
              isActive ? 'text-hot animate-pulse' : 'text-muted-foreground'
            )}
          />
          <span className="font-semibold text-foreground">Pool</span>
        </div>
        <span
          className={cn(
            'text-xs font-mono px-2 py-1 rounded transition-colors',
            isActive
              ? 'bg-hot/20 text-hot'
              : state.enabled
                ? 'bg-success/20 text-success'
                : 'bg-muted text-muted-foreground'
          )}
        >
          {isActive ? 'Heating' : state.enabled ? 'Ready' : 'Off'}
        </span>
      </div>

      {/* Pool visualization */}
      <div className="relative h-16 mb-3 rounded-lg bg-cold/10 border border-cold/30 overflow-hidden">
        <div
          className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-cold/40 to-cold/20 transition-all duration-500"
          style={{ height: '70%' }}
        />
        {isActive && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-4 h-4 rounded-full bg-hot animate-ping opacity-50" />
          </div>
        )}
        <div className="absolute bottom-2 right-2 font-mono text-sm text-foreground">
          {state.returnLineTemp.toFixed(1)}°C
        </div>
        <div className="absolute top-2 right-2 text-xs text-muted-foreground">
          Target: {state.targetTemp}°C
        </div>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-1 text-xs">
        <Euro className="w-3 h-3 text-success" />
        <span className="text-muted-foreground">Avg Price:</span>
        <span className="font-mono text-foreground">{state.averagePrice.toFixed(2)} c/kWh</span>
      </div>
    </div>
  );
}
