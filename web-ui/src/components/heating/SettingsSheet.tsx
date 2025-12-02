import { useState } from 'react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { GearSettingsCard } from './GearSettingsCard';
import { Settings, Home, Waves, Droplet } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';

interface GearSettings {
  heating: { min: number; max: number };
  pool: { min: number; max: number };
  tapWater: { min: number; max: number };
}

interface SettingsSheetProps {
  gearSettings: GearSettings;
  currentGears?: {
    heating?: number;
    pool?: number;
    tapWater?: number;
  };
  onGearSettingsChange: (settings: GearSettings) => void;
  className?: string;
}

export function SettingsSheet({
  gearSettings,
  currentGears,
  onGearSettingsChange,
  className,
}: SettingsSheetProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  const updateSetting = (
    circuit: keyof GearSettings,
    type: 'min' | 'max',
    value: number
  ) => {
    onGearSettingsChange({
      ...gearSettings,
      [circuit]: {
        ...gearSettings[circuit],
        [type]: value,
      },
    });
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
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
      <SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto">
        <SheetHeader className="pb-4">
          <SheetTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-primary" />
            {t('settings.title')}
          </SheetTitle>
          <SheetDescription>
            {t('settings.description')}
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-4 pb-8">
          {/* Heating Circuit */}
          <GearSettingsCard
            title={t('settings.heatingCircuit')}
            icon={Home}
            iconColorClass="text-hot"
            rangeColorClass="bg-hot"
            minValue={gearSettings.heating.min}
            maxValue={gearSettings.heating.max}
            currentGear={currentGears?.heating}
            onMinChange={(v) => updateSetting('heating', 'min', v)}
            onMaxChange={(v) => updateSetting('heating', 'max', v)}
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
            onMinChange={(v) => updateSetting('pool', 'min', v)}
            onMaxChange={(v) => updateSetting('pool', 'max', v)}
          />

          {/* Tap Water (DHW) */}
          <GearSettingsCard
            title={t('settings.tapWaterCircuit')}
            icon={Droplet}
            iconColorClass="text-cold"
            rangeColorClass="bg-cold"
            minValue={gearSettings.tapWater.min}
            maxValue={gearSettings.tapWater.max}
            currentGear={currentGears?.tapWater}
            onMinChange={(v) => updateSetting('tapWater', 'min', v)}
            onMaxChange={(v) => updateSetting('tapWater', 'max', v)}
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}
