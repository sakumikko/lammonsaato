import { cn } from '@/lib/utils';
import { SystemState } from '@/types/heating';
import { HeatPumpUnit } from './HeatPumpUnit';
import { ValveIndicator } from './ValveIndicator';
import { PoolUnit } from './PoolUnit';
import { RadiatorUnit } from './RadiatorUnit';
import { GroundLoop } from './GroundLoop';
import { FlowPipe } from './FlowPipe';

interface SystemDiagramProps {
  state: SystemState;
  onToggleValve: () => void;
  className?: string;
}

export function SystemDiagram({ state, onToggleValve, className }: SystemDiagramProps) {
  const isPoolActive = state.valve.position === 'pool';
  const isHeatPumpRunning = state.heatPump.heatEnabled || state.heatPump.compressorRpm > 0;

  return (
    <div className={cn('relative p-2 md:p-6', className)}>
      {/* Vertical flow layout: Ground → Heat Pump → Valve → Pool/Radiators */}
      <div className="flex flex-col items-center gap-1 md:gap-2">

        {/* Row 1: Distribution - Pool ← Valve → Radiators */}
        <div className="grid grid-cols-[1fr_auto_1fr] gap-1 md:gap-4 items-center w-full max-w-3xl">
          {/* Pool (left) */}
          <div className="flex items-center gap-1 md:gap-2">
            <PoolUnit
              state={state.poolHeating}
              isActive={isPoolActive && isHeatPumpRunning}
              className="flex-1"
            />
            <FlowPipe
              variant={isPoolActive && isHeatPumpRunning ? 'hot' : 'inactive'}
              flowing={isPoolActive && isHeatPumpRunning}
              className="w-3 md:w-8"
            />
          </div>

          {/* Valve (center) */}
          <div className="flex flex-col items-center">
            <ValveIndicator
              state={state.valve}
              onToggle={onToggleValve}
            />
          </div>

          {/* Radiators (right) */}
          <div className="flex items-center gap-1 md:gap-2">
            <FlowPipe
              variant={!isPoolActive && isHeatPumpRunning ? 'hot' : 'inactive'}
              flowing={!isPoolActive && isHeatPumpRunning}
              className="w-3 md:w-8"
            />
            <RadiatorUnit
              isActive={!isPoolActive && isHeatPumpRunning}
              supplyTemp={state.heatPump.condenserOutTemp}
              returnTemp={state.heatPump.condenserInTemp}
              className="flex-1"
            />
          </div>
        </div>

        {/* Pipe: Valve ↔ Heat Pump */}
        <FlowPipe
          variant={isHeatPumpRunning ? 'hot' : 'inactive'}
          direction="vertical"
          flowing={isHeatPumpRunning}
          className="h-3 md:h-6"
        />

        {/* Row 2: Heat Pump */}
        <div className="w-full max-w-xs md:max-w-md">
          <HeatPumpUnit state={state.heatPump} />
        </div>

        {/* Pipe: Heat Pump ↔ Ground Loop */}
        <FlowPipe
          variant={isHeatPumpRunning ? 'cold' : 'inactive'}
          direction="vertical"
          flowing={isHeatPumpRunning}
          className="h-3 md:h-6"
        />

        {/* Row 3: Ground Loop */}
        <div className="w-full max-w-[200px] md:max-w-sm">
          <GroundLoop
            brineInTemp={state.heatPump.brineInTemp}
            brineOutTemp={state.heatPump.brineOutTemp}
            isActive={isHeatPumpRunning}
          />
        </div>
      </div>

      {/* Flow direction legend - hidden on mobile */}
      <div className="mt-4 md:mt-8 hidden md:flex justify-center gap-8 text-xs">
        <div className="flex items-center gap-2">
          <div className="w-6 h-2 rounded-full bg-hot/60" />
          <span className="text-muted-foreground">Hot supply</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-2 rounded-full bg-cold/60" />
          <span className="text-muted-foreground">Cold return</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-2 rounded-full bg-muted" />
          <span className="text-muted-foreground">Inactive</span>
        </div>
      </div>
    </div>
  );
}
