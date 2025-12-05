import { useTranslation } from 'react-i18next';
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
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PoolTempPoint, TimeRange } from '@/types/analytics';

interface PoolTempChartProps {
  data: PoolTempPoint[];
  timeRange: TimeRange;
  target: number;
}

export function PoolTempChart({ data, timeRange, target }: PoolTempChartProps) {
  const { t } = useTranslation();

  // Calculate domain with some padding
  const temps = data.map((d) => d.temp);
  const minTemp = Math.min(...temps, target) - 1;
  const maxTemp = Math.max(...temps, target) + 1;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium">
          {t('analytics.charts.poolTemp')}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 12 }}
              className="text-muted-foreground"
            />
            <YAxis
              domain={[minTemp, maxTemp]}
              tick={{ fontSize: 12 }}
              className="text-muted-foreground"
              label={{
                value: '°C',
                angle: -90,
                position: 'insideLeft',
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
              formatter={(value: number, name: string) => [
                `${value.toFixed(1)}°C`,
                name === 'temp' ? t('stats.poolTemp') : t('pool.target'),
              ]}
            />
            <Legend
              formatter={(value) => (value === 'temp' ? t('stats.poolTemp') : t('pool.target'))}
            />
            <ReferenceLine
              y={target}
              stroke="hsl(var(--warning))"
              strokeDasharray="5 5"
              label={{
                value: t('pool.target'),
                position: 'right',
                className: 'fill-warning text-xs',
              }}
            />
            <Line
              type="monotone"
              dataKey="temp"
              stroke="hsl(var(--hot))"
              strokeWidth={2}
              dot={{ r: 4, fill: 'hsl(var(--hot))' }}
              activeDot={{ r: 6 }}
              name="temp"
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
