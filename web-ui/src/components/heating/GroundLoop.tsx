import { cn } from '@/lib/utils';
import { Mountain, Thermometer } from 'lucide-react';

interface GroundLoopProps {
  brineInTemp: number;
  brineOutTemp: number;
  isActive: boolean;
  className?: string;
}

export function GroundLoop({ brineInTemp, brineOutTemp, isActive, className }: GroundLoopProps) {
  return (
    <div
      className={cn(
        'relative p-4 rounded-2xl border-2 transition-all duration-500',
        isActive
          ? 'bg-cold/10 border-cold/50 shadow-glow-cold'
          : 'bg-card/50 border-border',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <Mountain
          className={cn(
            'w-5 h-5 transition-colors',
            isActive ? 'text-cold' : 'text-muted-foreground'
          )}
        />
        <span className="font-semibold text-foreground text-sm">Ground Loop</span>
      </div>

      {/* Ground visualization */}
      <div className="relative h-10 rounded-lg bg-gradient-to-b from-muted/30 to-muted/60 overflow-hidden mb-2">
        <div className="absolute inset-x-2 top-2 bottom-2 flex items-center">
          {isActive && (
            <>
              <div className="h-1 flex-1 bg-cold/40 rounded-full overflow-hidden">
                <div className="h-full w-full pipe-flow-cold" />
              </div>
            </>
          )}
        </div>
        <div className="absolute bottom-1 left-2 right-2 flex justify-between text-[10px] text-muted-foreground">
          <span>Borehole</span>
        </div>
      </div>

      {/* Temps */}
      <div className="flex justify-between text-xs">
        <div className="flex items-center gap-1">
          <Thermometer className="w-3 h-3 text-cold" />
          <span className="text-muted-foreground">In:</span>
          <span className="font-mono text-cold">{brineInTemp.toFixed(1)}°C</span>
        </div>
        <div className="flex items-center gap-1">
          <Thermometer className="w-3 h-3 text-cold/60" />
          <span className="text-muted-foreground">Out:</span>
          <span className="font-mono text-cold/60">{brineOutTemp.toFixed(1)}°C</span>
        </div>
      </div>
    </div>
  );
}
