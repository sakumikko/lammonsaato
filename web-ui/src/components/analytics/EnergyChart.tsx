import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { TempCorrelationPoint, TimeRange } from '@/types/analytics';

type EnergyType = 'electric' | 'thermal';

interface EnergyChartProps {
  data: TempCorrelationPoint[];
  timeRange: TimeRange;
}

export function EnergyChart({ data, timeRange }: EnergyChartProps) {
  const { t } = useTranslation();
  const [energyType, setEnergyType] = useState<EnergyType>('electric');
  const useBarForEnergy = timeRange === '1w';

  // Transform data based on energy type selection
  const chartData = data.map((d) => ({
    ...d,
    energy: energyType === 'electric' ? d.energy : d.energy * 3, // COP = 3
  }));

  const energyLabel = energyType === 'electric'
    ? t('analytics.charts.energyElectric')
    : t('analytics.charts.energyThermal');

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium">
            {t('analytics.charts.tempCorrelation')}
          </CardTitle>
          <ToggleGroup
            type="single"
            value={energyType}
            onValueChange={(v) => v && setEnergyType(v as EnergyType)}
            size="sm"
          >
            <ToggleGroupItem value="electric" className="text-xs px-2">
              {t('analytics.charts.energyElectric')}
            </ToggleGroupItem>
            <ToggleGroupItem value="thermal" className="text-xs px-2">
              {t('analytics.charts.energyThermal')}
            </ToggleGroupItem>
          </ToggleGroup>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={chartData} margin={{ top: 5, right: 40, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 12 }}
              className="text-muted-foreground"
            />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 12 }}
              className="text-muted-foreground"
              label={{
                value: 'kWh',
                angle: -90,
                position: 'insideLeft',
                className: 'fill-muted-foreground',
              }}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 12 }}
              className="text-muted-foreground"
              label={{
                value: '°C',
                angle: 90,
                position: 'insideRight',
                className: 'fill-muted-foreground',
              }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--card))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px',
              }}
              labelStyle={{ color: 'hsl(var(--foreground))' }}
              formatter={(value: number, name: string) => {
                if (name === 'energy') return [`${value.toFixed(1)} kWh`, energyLabel];
                if (name === 'outdoorTemp') return [`${value.toFixed(1)}°C`, t('controls.outdoor')];
                return [value, name];
              }}
            />
            <Legend
              formatter={(value) => {
                if (value === 'energy') return energyLabel;
                if (value === 'outdoorTemp') return t('controls.outdoor');
                return value;
              }}
            />
            {useBarForEnergy ? (
              <Bar
                yAxisId="left"
                dataKey="energy"
                fill="hsl(var(--primary))"
                name="energy"
                radius={[4, 4, 0, 0]}
              />
            ) : (
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="energy"
                stroke="hsl(var(--primary))"
                strokeWidth={2}
                dot={{ r: 3 }}
                name="energy"
              />
            )}
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="outdoorTemp"
              stroke="hsl(var(--cold))"
              strokeWidth={2}
              dot={{ r: 3 }}
              name="outdoorTemp"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
