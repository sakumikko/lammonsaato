import { useState, useEffect, useRef } from 'react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { GearSettingsCard } from './GearSettingsCard';
import { TemperatureSettingsCard } from './TemperatureSettingsCard';
import { PeakPowerSettingsCard } from './PeakPowerSettingsCard';
import { TemperatureChart } from './TemperatureChart';
import { Settings, Home, Waves, Droplet, Flame, TrendingUp, Thermometer } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { GearSettings, TapWaterState, HotGasSettings, HeatingCurveSettings, HeatPumpState, PeakPowerSettings, SystemSupplyState } from '@/types/heating';
import {
  GearCircuit,
  GearLimitType,
  TapWaterSetting,
  HotGasSetting,
  HeatingCurveSetting,
  PeakPowerSetting,
  PeakPowerTime,
} from '@/hooks/useHomeAssistant';

interface SettingsSheetProps {
  gearSettings: GearSettings;
  tapWater: TapWaterState;
  hotGasSettings: HotGasSettings;
  heatingCurve: HeatingCurveSettings;
  peakPower: PeakPowerSettings;
  heatPump: HeatPumpState;
  systemSupply: SystemSupplyState;
  currentGears?: {
    heating?: number;
    pool?: number;
    tapWater?: number;
  };
  onGearLimitChange: (circuit: GearCircuit, type: GearLimitType, value: number) => Promise<void>;
  onTapWaterChange: (setting: TapWaterSetting, value: number) => Promise<void>;
  onHotGasChange: (setting: HotGasSetting, value: number) => Promise<void>;
  onHeatingCurveChange: (setting: HeatingCurveSetting, value: number) => Promise<void>;
  onPeakPowerSettingChange: (setting: PeakPowerSetting, value: number) => Promise<void>;
  onPeakPowerTimeChange: (setting: PeakPowerTime, time: string) => Promise<void>;
  onFixedSupplyEnabledChange: (enabled: boolean) => Promise<void>;
  onFixedSupplyTargetChange: (value: number) => Promise<void>;
  onComfortWheelChange: (value: number) => Promise<void>;
  className?: string;
  // External control (when rendered without trigger)
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  showTrigger?: boolean;
}

interface TemperatureDataPoint {
  time: string;
  timestamp: number;
  dischargePipe: number;
  outdoor: number;
  tapWater: number;
  condenserOut: number;
}

export function SettingsSheet({
  gearSettings,
  tapWater,
  hotGasSettings,
  heatingCurve,
  peakPower,
  heatPump,
  systemSupply,
  currentGears,
  onGearLimitChange,
  onTapWaterChange,
  onHotGasChange,
  onHeatingCurveChange,
  onPeakPowerSettingChange,
  onPeakPowerTimeChange,
  onFixedSupplyEnabledChange,
  onFixedSupplyTargetChange,
  onComfortWheelChange,
  className,
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
  showTrigger = true,
}: SettingsSheetProps) {
  const { t } = useTranslation();
  const [internalOpen, setInternalOpen] = useState(false);

  // Use controlled state if provided, otherwise internal
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : internalOpen;
  const setOpen = isControlled ? (controlledOnOpenChange ?? (() => {})) : setInternalOpen;
  const [temperatureHistory, setTemperatureHistory] = useState<TemperatureDataPoint[]>([]);
  const lastUpdateRef = useRef<number>(0);

  // Update temperature history when values change
  useEffect(() => {
    const now = Date.now();
    // Only add data point every 30 seconds
    if (now - lastUpdateRef.current < 30000) return;
    lastUpdateRef.current = now;

    const time = new Date().toLocaleTimeString('fi-FI', { hour: '2-digit', minute: '2-digit' });
    setTemperatureHistory(prev => {
      const newPoint: TemperatureDataPoint = {
        time,
        timestamp: now,
        dischargePipe: heatPump.dischargePipeTemp,
        outdoor: heatPump.outdoorTemp,
        tapWater: tapWater.weightedTemp,
        condenserOut: heatPump.condenserOutTemp,
      };
      const updated = [...prev, newPoint];
      // Keep last 60 points (30 minutes of data at 30s intervals)
      return updated.slice(-60);
    });
  }, [heatPump.dischargePipeTemp, heatPump.outdoorTemp, tapWater.weightedTemp, heatPump.condenserOutTemp]);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      {showTrigger && (
        <SheetTrigger asChild>
          <button
            className={cn(
              'p-2 rounded-lg transition-colors',
              'hover:bg-muted/80 active:bg-muted',
              'text-muted-foreground hover:text-foreground',
              className
            )}
            title={t('settings.title')}
          >
            <Settings className="w-5 h-5" />
          </button>
        </SheetTrigger>
      )}
      <SheetContent side="right" className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader className="pb-4">
          <SheetTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-primary" />
            {t('settings.title')}
          </SheetTitle>
          <SheetDescription>
            {t('settings.description')}
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-6 pb-8">
          {/* Temperature Chart */}
          <TemperatureChart
            data={temperatureHistory}
            currentDischargeTemp={heatPump.dischargePipeTemp}
            currentOutdoorTemp={heatPump.outdoorTemp}
            currentTapWaterTemp={tapWater.weightedTemp}
            warningThreshold={100}
            dangerThreshold={110}
          />

          {/* Hot Gas Protection */}
          <TemperatureSettingsCard
            title={t('settings.hotGasProtection')}
            icon={Flame}
            iconColorClass="text-hot"
            currentValue={heatPump.dischargePipeTemp}
            currentLabel={t('settings.current')}
            settings={[
              {
                label: t('settings.hotGasPumpStart'),
                value: hotGasSettings.pumpStartTemp,
                onChange: (v) => onHotGasChange('pumpStartTemp', v),
                min: 50,
                max: 100,
              },
              {
                label: t('settings.hotGasLowerStop'),
                value: hotGasSettings.lowerStopLimit,
                onChange: (v) => onHotGasChange('lowerStopLimit', v),
                min: 40,
                max: 90,
              },
              {
                label: t('settings.hotGasUpperStop'),
                value: hotGasSettings.upperStopLimit,
                onChange: (v) => onHotGasChange('upperStopLimit', v),
                min: 70,
                max: 120,
              },
            ]}
          />

          {/* Tap Water Settings */}
          <TemperatureSettingsCard
            title={t('settings.tapWaterSettings')}
            icon={Droplet}
            iconColorClass="text-primary"
            currentValue={tapWater.weightedTemp}
            currentLabel={t('settings.current')}
            settings={[
              {
                label: t('settings.tapWaterStart'),
                value: tapWater.startTemp,
                onChange: (v) => onTapWaterChange('startTemp', v),
                min: 35,
                max: 55,
              },
              {
                label: t('settings.tapWaterStop'),
                value: tapWater.stopTemp,
                onChange: (v) => onTapWaterChange('stopTemp', v),
                min: 40,
                max: 65,
              },
            ]}
          />

          {/* Heating Curve Limits */}
          <TemperatureSettingsCard
            title={t('settings.heatingCurveLimits')}
            icon={TrendingUp}
            iconColorClass="text-success"
            settings={[
              {
                label: t('settings.curveMaxLimit'),
                value: heatingCurve.maxLimitation,
                onChange: (v) => onHeatingCurveChange('maxLimitation', v),
                min: 35,
                max: 65,
              },
              {
                label: t('settings.curveMinLimit'),
                value: heatingCurve.minLimitation,
                onChange: (v) => onHeatingCurveChange('minLimitation', v),
                min: 15,
                max: 40,
              },
            ]}
          />

          {/* Fixed Supply & Comfort Wheel */}
          <div className="rounded-lg border bg-card p-4 space-y-4">
            <div className="flex items-center gap-2">
              <Thermometer className="w-5 h-5 text-primary" />
              <h3 className="font-semibold">{t('settings.supplyControl')}</h3>
            </div>

            {/* Fixed Supply Enable Toggle */}
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <label className="text-sm font-medium">{t('settings.fixedSupplyEnable')}</label>
                <p className="text-xs text-muted-foreground">
                  {t('settings.fixedSupplyDescription')}
                </p>
              </div>
              <Switch
                checked={systemSupply.fixedModeEnabled}
                onCheckedChange={onFixedSupplyEnabledChange}
              />
            </div>

            {/* Fixed Supply Target */}
            <TemperatureSettingsCard
              title={t('settings.fixedSupplyTarget')}
              icon={Thermometer}
              iconColorClass="text-primary"
              currentValue={systemSupply.supplyTemp}
              currentLabel={t('settings.current')}
              settings={[
                {
                  label: t('settings.fixedTarget'),
                  value: systemSupply.fixedTarget,
                  onChange: onFixedSupplyTargetChange,
                  min: 20,
                  max: 55,
                },
              ]}
            />

            {/* Comfort Wheel */}
            <TemperatureSettingsCard
              title={t('settings.comfortWheel')}
              icon={Home}
              iconColorClass="text-hot"
              settings={[
                {
                  label: t('settings.comfortWheelValue'),
                  value: systemSupply.comfortWheel,
                  onChange: onComfortWheelChange,
                  min: 15,
                  max: 30,
                },
              ]}
            />
          </div>

          {/* Peak Power Avoidance */}
          <PeakPowerSettingsCard
            settings={peakPower}
            onSettingChange={onPeakPowerSettingChange}
            onTimeChange={onPeakPowerTimeChange}
          />

          {/* Section divider */}
          <div className="border-t border-border pt-4">
            <h4 className="text-sm font-medium text-muted-foreground mb-4">
              {t('settings.gearLimitsSection')}
            </h4>
          </div>

          {/* Heating Circuit */}
          <GearSettingsCard
            title={t('settings.heatingCircuit')}
            icon={Home}
            iconColorClass="text-hot"
            rangeColorClass="bg-hot"
            minValue={gearSettings.heating.min}
            maxValue={gearSettings.heating.max}
            currentGear={currentGears?.heating}
            onMinChange={(v) => onGearLimitChange('heating', 'min', v)}
            onMaxChange={(v) => onGearLimitChange('heating', 'max', v)}
          />

          {/* Pool Circuit */}
          <GearSettingsCard
            title={t('settings.poolCircuit')}
            icon={Waves}
            iconColorClass="text-primary"
            rangeColorClass="bg-primary"
            minValue={gearSettings.pool.min}
            maxValue={gearSettings.pool.max}
            currentGear={currentGears?.pool}
            onMinChange={(v) => onGearLimitChange('pool', 'min', v)}
            onMaxChange={(v) => onGearLimitChange('pool', 'max', v)}
          />

          {/* Tap Water (DHW) Gear */}
          <GearSettingsCard
            title={t('settings.tapWaterCircuit')}
            icon={Droplet}
            iconColorClass="text-cold"
            rangeColorClass="bg-cold"
            minValue={gearSettings.tapWater.min}
            maxValue={gearSettings.tapWater.max}
            currentGear={currentGears?.tapWater}
            onMinChange={(v) => onGearLimitChange('tapWater', 'min', v)}
            onMaxChange={(v) => onGearLimitChange('tapWater', 'max', v)}
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}
