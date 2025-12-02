import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from 'recharts';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { Thermometer, AlertTriangle } from 'lucide-react';

interface TemperatureDataPoint {
  time: string;
  timestamp: number;
  dischargePipe: number;
  outdoor: number;
  tapWater: number;
  condenserOut: number;
}

interface TemperatureChartProps {
  data: TemperatureDataPoint[];
  currentDischargeTemp: number;
  currentOutdoorTemp: number;
  currentTapWaterTemp: number;
  warningThreshold?: number;
  dangerThreshold?: number;
  className?: string;
}

export function TemperatureChart({
  data,
  currentDischargeTemp,
  currentOutdoorTemp,
  currentTapWaterTemp,
  warningThreshold = 100,
  dangerThreshold = 110,
  className,
}: TemperatureChartProps) {
  const { t } = useTranslation();

  // Determine status based on discharge temp
  const status = useMemo(() => {
    if (currentDischargeTemp >= dangerThreshold) return 'danger';
    if (currentDischargeTemp >= warningThreshold) return 'warning';
    return 'normal';
  }, [currentDischargeTemp, warningThreshold, dangerThreshold]);

  const statusColors = {
    normal: 'text-success',
    warning: 'text-warning',
    danger: 'text-destructive',
  };

  const statusBg = {
    normal: 'bg-success/20',
    warning: 'bg-warning/20',
    danger: 'bg-destructive/20',
  };

  return (
    <div className={cn('p-4 rounded-xl bg-card border border-border', className)}>
      {/* Header with current values */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Thermometer className="w-5 h-5 text-hot" />
          <h3 className="text-sm font-semibold text-foreground">
            {t('temperatures.title')}
          </h3>
        </div>
        {status !== 'normal' && (
          <div className={cn('flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium', statusBg[status], statusColors[status])}>
            <AlertTriangle className="w-3 h-3" />
            {status === 'warning' ? t('temperatures.warning') : t('temperatures.danger')}
          </div>
        )}
      </div>

      {/* Current temperature cards */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <div className={cn('p-2 rounded-lg text-center', statusBg[status])}>
          <div className="text-xs text-muted-foreground">{t('temperatures.hotGas')}</div>
          <div className={cn('font-mono text-lg font-bold', statusColors[status])}>
            {currentDischargeTemp.toFixed(1)}°C
          </div>
        </div>
        <div className="p-2 rounded-lg bg-cold/20 text-center">
          <div className="text-xs text-muted-foreground">{t('temperatures.outdoor')}</div>
          <div className="font-mono text-lg font-bold text-cold">
            {currentOutdoorTemp.toFixed(1)}°C
          </div>
        </div>
        <div className="p-2 rounded-lg bg-primary/20 text-center">
          <div className="text-xs text-muted-foreground">{t('temperatures.tapWater')}</div>
          <div className="font-mono text-lg font-bold text-primary">
            {currentTapWaterTemp.toFixed(1)}°C
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" opacity={0.3} />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 10 }}
              className="text-muted-foreground"
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 10 }}
              className="text-muted-foreground"
              tickLine={false}
              domain={['auto', 'auto']}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px',
                fontSize: '12px',
              }}
              labelStyle={{ color: 'hsl(var(--foreground))' }}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px' }}
              iconSize={8}
            />

            {/* Warning zone */}
            <ReferenceArea
              y1={warningThreshold}
              y2={dangerThreshold}
              fill="hsl(var(--warning))"
              fillOpacity={0.1}
            />
            {/* Danger zone */}
            <ReferenceArea
              y1={dangerThreshold}
              y2={150}
              fill="hsl(var(--destructive))"
              fillOpacity={0.1}
            />

            {/* Threshold lines */}
            <ReferenceLine
              y={warningThreshold}
              stroke="hsl(var(--warning))"
              strokeDasharray="5 5"
              strokeWidth={1}
            />
            <ReferenceLine
              y={dangerThreshold}
              stroke="hsl(var(--destructive))"
              strokeDasharray="5 5"
              strokeWidth={1}
            />

            <Line
              type="monotone"
              dataKey="dischargePipe"
              name={t('temperatures.hotGas')}
              stroke="hsl(var(--hot))"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
            <Line
              type="monotone"
              dataKey="outdoor"
              name={t('temperatures.outdoor')}
              stroke="hsl(var(--cold))"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
            <Line
              type="monotone"
              dataKey="tapWater"
              name={t('temperatures.tapWater')}
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Legend explanation */}
      <div className="mt-2 flex items-center justify-center gap-4 text-[10px] text-muted-foreground">
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-warning" />
          <span>{t('temperatures.warningAt', { temp: warningThreshold })}</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-0.5 bg-destructive" />
          <span>{t('temperatures.dangerAt', { temp: dangerThreshold })}</span>
        </div>
      </div>
    </div>
  );
}

// Hook to manage temperature history
export function useTemperatureHistory(maxPoints: number = 60) {
  const historyRef = useMemo(() => ({ data: [] as TemperatureDataPoint[] }), []);

  const addDataPoint = (
    dischargePipe: number,
    outdoor: number,
    tapWater: number,
    condenserOut: number
  ) => {
    const now = new Date();
    const time = now.toLocaleTimeString('fi-FI', { hour: '2-digit', minute: '2-digit' });

    historyRef.data.push({
      time,
      timestamp: now.getTime(),
      dischargePipe,
      outdoor,
      tapWater,
      condenserOut,
    });

    // Keep only last maxPoints
    if (historyRef.data.length > maxPoints) {
      historyRef.data.shift();
    }

    return [...historyRef.data];
  };

  return { data: historyRef.data, addDataPoint };
}
