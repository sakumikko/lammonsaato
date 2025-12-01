import { cn } from '@/lib/utils';
import { Mountain, Thermometer } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface GroundLoopProps {
  brineInTemp: number;
  brineOutTemp: number;
  isActive: boolean;
  className?: string;
}

export function GroundLoop({ brineInTemp, brineOutTemp, isActive, className }: GroundLoopProps) {
  const { t } = useTranslation();

  return (
    <div
      className={cn(
        'relative p-2 md:p-4 rounded-xl md:rounded-2xl border-2 transition-all duration-500',
        isActive
          ? 'bg-cold/10 border-cold/50 shadow-glow-cold'
          : 'bg-card/50 border-border',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-1.5 md:gap-2 mb-1.5 md:mb-3">
        <Mountain
          className={cn(
            'w-4 h-4 md:w-5 md:h-5 transition-colors',
            isActive ? 'text-cold' : 'text-muted-foreground'
          )}
        />
        <span className="font-semibold text-foreground text-xs md:text-sm">{t('groundLoop.title')}</span>
      </div>

      {/* Ground visualization */}
      <div className="relative h-6 md:h-10 rounded-lg bg-gradient-to-b from-muted/30 to-muted/60 overflow-hidden mb-1 md:mb-2">
        <div className="absolute inset-x-1 md:inset-x-2 top-1 md:top-2 bottom-1 md:bottom-2 flex items-center">
          {isActive && (
            <>
              <div className="h-0.5 md:h-1 flex-1 bg-cold/40 rounded-full overflow-hidden">
                <div className="h-full w-full pipe-flow-cold" />
              </div>
            </>
          )}
        </div>
        <div className="absolute bottom-0.5 md:bottom-1 left-1 md:left-2 right-1 md:right-2 flex justify-between text-[8px] md:text-[10px] text-muted-foreground">
          <span>{t('groundLoop.borehole')}</span>
        </div>
      </div>

      {/* Temps */}
      <div className="flex justify-between text-[10px] md:text-xs">
        <div className="flex items-center gap-0.5 md:gap-1">
          <Thermometer className="w-2.5 h-2.5 md:w-3 md:h-3 text-cold" />
          <span className="text-muted-foreground">{t('groundLoop.in')}</span>
          <span className="font-mono text-cold">{brineInTemp.toFixed(1)}°C</span>
        </div>
        <div className="flex items-center gap-0.5 md:gap-1">
          <Thermometer className="w-2.5 h-2.5 md:w-3 md:h-3 text-cold/60" />
          <span className="text-muted-foreground">{t('groundLoop.out')}</span>
          <span className="font-mono text-cold/60">{brineOutTemp.toFixed(1)}°C</span>
        </div>
      </div>
    </div>
  );
}
