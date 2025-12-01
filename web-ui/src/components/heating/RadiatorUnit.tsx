import { cn } from '@/lib/utils';
import { Home, Thermometer } from 'lucide-react';

interface RadiatorUnitProps {
  isActive: boolean;
  supplyTemp: number;
  returnTemp: number;
  className?: string;
}

export function RadiatorUnit({ isActive, supplyTemp, returnTemp, className }: RadiatorUnitProps) {
  return (
    <div
      className={cn(
        'relative p-5 rounded-2xl border-2 transition-all duration-500',
        isActive
          ? 'bg-primary/10 border-primary/50 box-glow-primary'
          : 'bg-card/50 border-border',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Home
            className={cn(
              'w-5 h-5 transition-colors',
              isActive ? 'text-primary' : 'text-muted-foreground'
            )}
          />
          <span className="font-semibold text-foreground">Radiators</span>
        </div>
        <span
          className={cn(
            'text-xs font-mono px-2 py-1 rounded transition-colors',
            isActive ? 'bg-primary/20 text-primary' : 'bg-muted text-muted-foreground'
          )}
        >
          {isActive ? 'Active' : 'Standby'}
        </span>
      </div>

      {/* Radiator visualization */}
      <div className="flex gap-2 mb-3 h-14">
        {[...Array(5)].map((_, i) => (
          <div
            key={i}
            className={cn(
              'flex-1 rounded transition-all duration-500',
              isActive
                ? 'bg-gradient-to-b from-hot/60 via-hot/40 to-primary/30'
                : 'bg-muted/50'
            )}
            style={{
              animationDelay: `${i * 100}ms`,
            }}
          />
        ))}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="flex items-center gap-1">
          <Thermometer className="w-3 h-3 text-hot" />
          <span className="text-muted-foreground">Supply:</span>
          <span className="font-mono text-foreground">{supplyTemp.toFixed(1)}°C</span>
        </div>
        <div className="flex items-center gap-1">
          <Thermometer className="w-3 h-3 text-cold" />
          <span className="text-muted-foreground">Return:</span>
          <span className="font-mono text-foreground">{returnTemp.toFixed(1)}°C</span>
        </div>
      </div>
    </div>
  );
}
