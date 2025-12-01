import { useHomeAssistant } from '@/hooks/useHomeAssistant';
import { SystemDiagram } from '@/components/heating/SystemDiagram';
import { ControlPanel } from '@/components/heating/ControlPanel';
import { SchedulePanel } from '@/components/heating/SchedulePanel';
import { Activity, Zap, Wifi, WifiOff } from 'lucide-react';

const Index = () => {
  const {
    state,
    connected,
    error,
    setPoolHeatingEnabled,
    setPoolTargetTemp,
    toggleValve,
    setBlockEnabled,
  } = useHomeAssistant();

  const isPoolActive = state.valve.position === 'pool';

  return (
    <div className="min-h-screen bg-background bg-grid">
      {/* Header */}
      <header className="border-b border-border bg-card/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/20">
                <Zap className="w-6 h-6 text-primary" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-foreground">Lämmönsäätö</h1>
                <p className="text-xs text-muted-foreground">Pool Heating Optimizer</p>
              </div>
            </div>

            {/* Status indicator */}
            <div className="flex items-center gap-4">
              {/* Connection status */}
              <div
                className={`flex items-center gap-2 px-3 py-2 rounded-lg ${
                  connected ? 'bg-success/20' : 'bg-destructive/20'
                }`}
                title={error || (connected ? 'Connected to Home Assistant' : 'Disconnected')}
              >
                {connected ? (
                  <Wifi className="w-4 h-4 text-success" />
                ) : (
                  <WifiOff className="w-4 h-4 text-destructive" />
                )}
                <span className={`text-sm font-medium ${connected ? 'text-success' : 'text-destructive'}`}>
                  {connected ? 'HA' : 'Offline'}
                </span>
              </div>
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted/50">
                <Activity
                  className={`w-4 h-4 ${
                    state.heatPump.heatEnabled ? 'text-success animate-pulse' : 'text-muted-foreground'
                  }`}
                />
                <span className="text-sm font-medium text-foreground">
                  {state.heatPump.heatEnabled ? 'System Active' : 'System Idle'}
                </span>
              </div>
              <div
                className={`px-3 py-2 rounded-lg font-mono text-sm transition-colors ${
                  isPoolActive
                    ? 'bg-hot/20 text-hot border border-hot/30'
                    : 'bg-primary/20 text-primary border border-primary/30'
                }`}
              >
                {isPoolActive ? '→ Pool' : '↓ Radiators'}
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto px-4 py-8">
        <div className="grid lg:grid-cols-3 gap-8">
          {/* System Diagram - takes 2 columns */}
          <div className="lg:col-span-2">
            <div className="rounded-2xl border border-border bg-card/50 backdrop-blur-sm overflow-hidden">
              <div className="px-6 py-4 border-b border-border bg-card/80">
                <h2 className="font-semibold text-foreground">System Overview</h2>
                <p className="text-xs text-muted-foreground mt-1">
                  Click the valve to switch between pool and radiator circuits
                </p>
              </div>
              <SystemDiagram
                state={state}
                onToggleValve={toggleValve}
              />
            </div>
          </div>

          {/* Right sidebar - Controls and Schedule */}
          <div className="space-y-6">
            <ControlPanel
              heatPump={state.heatPump}
              poolHeating={state.poolHeating}
              onPoolEnabledChange={setPoolHeatingEnabled}
              onPoolTempChange={setPoolTargetTemp}
            />

            <SchedulePanel
              schedule={state.schedule}
              nightComplete={state.poolHeating.nightComplete}
              onBlockEnabledChange={setBlockEnabled}
            />
          </div>
        </div>

        {/* Stats bar */}
        <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            {
              label: 'Daily Energy',
              value: `${state.poolHeating.dailyEnergy.toFixed(3)} kWh`,
              color: 'text-primary',
            },
            {
              label: 'Daily Cost',
              value: `€${state.poolHeating.dailyCost.toFixed(3)}`,
              color: 'text-success',
            },
            {
              label: 'Monthly Cost',
              value: `€${state.poolHeating.monthlyCost.toFixed(3)}`,
              color: 'text-success',
            },
            {
              label: 'Pool Temp',
              value: `${state.poolHeating.returnLineTemp.toFixed(1)}°C`,
              color: 'text-hot',
            },
          ].map((stat, index) => (
            <div
              key={index}
              className="p-4 rounded-xl bg-card border border-border text-center"
            >
              <div className="text-xs text-muted-foreground mb-1">{stat.label}</div>
              <div className={`font-mono text-lg ${stat.color}`}>{stat.value}</div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
};

export default Index;
