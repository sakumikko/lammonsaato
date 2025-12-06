import { useHomeAssistant } from '@/hooks/useHomeAssistant';
import { SystemDiagram } from '@/components/heating/SystemDiagram';
import { ControlPanel } from '@/components/heating/ControlPanel';
import { SchedulePanel } from '@/components/heating/SchedulePanel';
import { SettingsSheet } from '@/components/heating/SettingsSheet';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { ThemeToggle } from '@/components/ThemeToggle';
import { Activity, Zap, Wifi, WifiOff, BarChart3 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { useTranslation } from 'react-i18next';

const Index = () => {
  const { t } = useTranslation();
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

  const isPoolActive = state.valve.position === 'pool';

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

            {/* Status indicator */}
            <div className="flex items-center gap-1.5 md:gap-4">
              {/* Analytics link */}
              <Link to="/analytics">
                <Button variant="ghost" size="sm" className="gap-1.5">
                  <BarChart3 className="w-4 h-4" />
                  <span className="hidden md:inline">{t('analytics.title')}</span>
                </Button>
              </Link>
              {/* Settings, Theme and Language switchers */}
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
              />
              <ThemeToggle />
              <LanguageSwitcher />
              {/* Connection status */}
              <div
                className={`flex items-center gap-1 md:gap-2 px-2 md:px-3 py-1.5 md:py-2 rounded-lg ${
                  connected ? 'bg-success/20' : 'bg-destructive/20'
                }`}
                title={error || (connected ? t('status.connected') : t('status.disconnected'))}
              >
                {connected ? (
                  <Wifi className="w-4 h-4 text-success" />
                ) : (
                  <WifiOff className="w-4 h-4 text-destructive" />
                )}
                <span className={`text-sm font-medium hidden md:inline ${connected ? 'text-success' : 'text-destructive'}`}>
                  {connected ? 'HA' : t('status.offline')}
                </span>
              </div>
              <div className="flex items-center gap-1 md:gap-2 px-2 md:px-3 py-1.5 md:py-2 rounded-lg bg-muted/50">
                <Activity
                  className={`w-4 h-4 ${
                    state.heatPump.heatEnabled ? 'text-success animate-pulse' : 'text-muted-foreground'
                  }`}
                />
                <span className="text-sm font-medium text-foreground hidden md:inline">
                  {state.heatPump.heatEnabled ? t('status.systemActive') : t('status.systemIdle')}
                </span>
              </div>
              <div
                className="px-2 md:px-3 py-1.5 md:py-2 rounded-lg font-mono text-xs md:text-sm transition-colors bg-hot/20 text-hot border border-hot/30"
              >
                {isPoolActive ? `→ ${t('valve.pool')}` : `↓ ${t('valve.radiators')}`}
              </div>
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
