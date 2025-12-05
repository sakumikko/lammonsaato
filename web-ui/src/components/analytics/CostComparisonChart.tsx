import { useTranslation } from 'react-i18next';
import {
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CostChartPoint, TimeRange } from '@/types/analytics';

interface CostComparisonChartProps {
  data: CostChartPoint[];
  timeRange: TimeRange;
  totalSavings: number;
}

export function CostComparisonChart({ data, timeRange, totalSavings }: CostComparisonChartProps) {
  const { t } = useTranslation();
  const useBarChart = timeRange === '1w' || timeRange === '4w';

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium">
            {t('analytics.charts.cost')}
          </CardTitle>
          <span className="text-sm font-medium text-success">
            {t('analytics.labels.saved')}: €{totalSavings.toFixed(2)}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          {useBarChart ? (
            <BarChart data={data} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 12 }}
                className="text-muted-foreground"
              />
              <YAxis
                tick={{ fontSize: 12 }}
                className="text-muted-foreground"
                label={{
                  value: '€',
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
                  `€${value.toFixed(2)}`,
                  name === 'actual' ? t('analytics.charts.costActual') : t('analytics.charts.costBaseline'),
                ]}
              />
              <Legend
                formatter={(value) =>
                  value === 'actual' ? t('analytics.charts.costActual') : t('analytics.charts.costBaseline')
                }
              />
              <Bar dataKey="baseline" fill="hsl(var(--muted-foreground))" name="baseline" radius={[4, 4, 0, 0]} opacity={0.5} />
              <Bar dataKey="actual" fill="hsl(var(--success))" name="actual" radius={[4, 4, 0, 0]} />
            </BarChart>
          ) : (
            <AreaChart data={data} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 12 }}
                className="text-muted-foreground"
              />
              <YAxis
                tick={{ fontSize: 12 }}
                className="text-muted-foreground"
                label={{
                  value: '€',
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
                  `€${value.toFixed(2)}`,
                  name === 'actual' ? t('analytics.charts.costActual') : t('analytics.charts.costBaseline'),
                ]}
              />
              <Legend
                formatter={(value) =>
                  value === 'actual' ? t('analytics.charts.costActual') : t('analytics.charts.costBaseline')
                }
              />
              <Area
                type="monotone"
                dataKey="baseline"
                stroke="hsl(var(--muted-foreground))"
                fill="hsl(var(--muted))"
                name="baseline"
              />
              <Area
                type="monotone"
                dataKey="actual"
                stroke="hsl(var(--success))"
                fill="hsl(var(--success))"
                fillOpacity={0.3}
                name="actual"
              />
            </AreaChart>
          )}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
