import { useState } from 'react';
import { useHomeAssistant } from '@/hooks/useHomeAssistant';
import { SystemDiagram } from '@/components/heating/SystemDiagram';
import { ControlPanel } from '@/components/heating/ControlPanel';
import { SchedulePanel } from '@/components/heating/SchedulePanel';
import { SettingsSheet } from '@/components/heating/SettingsSheet';
import { StatusIndicator } from '@/components/StatusIndicator';
import { SettingsDropdown } from '@/components/SettingsDropdown';
import { Zap, BarChart3 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { useTranslation } from 'react-i18next';

const Index = () => {
  const { t } = useTranslation();
  const [heatPumpSettingsOpen, setHeatPumpSettingsOpen] = useState(false);
  const {
    state,
    connected,
    error,
    setPoolHeatingEnabled,
    setPoolTargetTemp,
    toggleValve,
    setBlockEnabled,
    setGearLimit,
    setTapWaterSetting,
    setHotGasSetting,
    setHeatingCurveSetting,
    setScheduleParameters,
    recalculateSchedule,
    isInHeatingWindow,
  } = useHomeAssistant();

  return (
    <div className="min-h-screen bg-background bg-grid">
      {/* Header */}
      <header className="border-b border-border bg-card/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto px-2 md:px-4 py-2 md:py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 md:gap-3">
              <div className="p-1.5 md:p-2 rounded-lg bg-primary/20">
                <Zap className="w-5 h-5 md:w-6 md:h-6 text-primary" />
              </div>
              <div>
                <h1 className="text-base md:text-xl font-bold text-foreground">{t('app.title')}</h1>
                <p className="text-xs text-muted-foreground hidden md:block">{t('app.subtitle')}</p>
              </div>
            </div>

            {/* Status indicators */}
            <div className="flex items-center gap-1.5 md:gap-2">
              {/* Analytics link */}
              <Link to="/analytics">
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <BarChart3 className="w-4 h-4" />
                  <span className="sr-only">{t('analytics.title')}</span>
                </Button>
              </Link>

              {/* Settings dropdown (theme, language, heat pump settings) */}
              <SettingsDropdown onOpenHeatPumpSettings={() => setHeatPumpSettingsOpen(true)} />

              {/* Consolidated status indicator */}
              <StatusIndicator
                connected={connected}
                systemActive={state.heatPump.heatEnabled}
                error={error}
              />

              {/* Heat pump settings sheet (controlled externally) */}
              <SettingsSheet
                gearSettings={state.gearSettings}
                tapWater={state.tapWater}
                hotGasSettings={state.hotGasSettings}
                heatingCurve={state.heatingCurve}
                heatPump={state.heatPump}
                onGearLimitChange={setGearLimit}
                onTapWaterChange={setTapWaterSetting}
                onHotGasChange={setHotGasSetting}
                onHeatingCurveChange={setHeatingCurveSetting}
                currentGears={{
                  heating: state.heatPump.compressorGear,
                }}
                open={heatPumpSettingsOpen}
                onOpenChange={setHeatPumpSettingsOpen}
                showTrigger={false}
              />
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto px-2 md:px-4 py-4 md:py-8">
        <div className="grid lg:grid-cols-3 gap-4 md:gap-8">
          {/* System Diagram - takes 2 columns */}
          <div className="lg:col-span-2">
            <div className="rounded-xl md:rounded-2xl border border-border bg-card/50 backdrop-blur-sm overflow-hidden">
              <div className="px-3 md:px-6 py-2 md:py-4 border-b border-border bg-card/80">
                <h2 className="font-semibold text-sm md:text-base text-foreground">{t('systemOverview.title')}</h2>
                <p className="text-xs text-muted-foreground mt-0.5 md:mt-1 hidden md:block">
                  {t('systemOverview.description')}
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
              onScheduleParametersChange={setScheduleParameters}
              onRecalculate={recalculateSchedule}
              isInHeatingWindow={isInHeatingWindow()}
            />
          </div>
        </div>

        {/* Stats bar */}
        <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            {
              label: t('stats.dailyEnergy'),
              value: `${state.poolHeating.dailyEnergy.toFixed(3)} kWh`,
              color: 'text-primary',
            },
            {
              label: t('stats.dailyCost'),
              value: `€${state.poolHeating.dailyCost.toFixed(3)}`,
              color: 'text-success',
            },
            {
              label: t('stats.monthlyCost'),
              value: `€${state.poolHeating.monthlyCost.toFixed(3)}`,
              color: 'text-success',
            },
            {
              label: t('stats.poolTemp'),
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
