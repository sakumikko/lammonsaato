import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { usePoolTempHistory, TimeRangeHours, PoolTempDataPoint } from '@/hooks/usePoolTempHistory';
import { RefreshCw, Thermometer, TrendingUp, TrendingDown, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PoolTempModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  targetTemp: number;
}

const TIME_RANGE_OPTIONS: { label: string; value: TimeRangeHours }[] = [
  { label: '24h', value: 24 },
  { label: '48h', value: 48 },
  { label: '7d', value: 168 },
];

interface ChartDataPoint {
  timestamp: number;
  temperature: number;
  timeLabel: string;      // Short label for X-axis
  tooltipLabel: string;   // Full label for tooltip
  isSmoothed: boolean;
}

function formatAxisLabel(date: Date, hoursRange: TimeRangeHours): string {
  if (hoursRange <= 24) {
    return date.toLocaleTimeString('fi-FI', { hour: '2-digit', minute: '2-digit' });
  } else if (hoursRange <= 48) {
    return `${date.getDate()}.${date.getMonth() + 1} ${date.getHours()}:00`;
  }
  return date.toLocaleDateString('fi-FI', { weekday: 'short', day: 'numeric' });
}

function formatTooltipLabel(date: Date): string {
  return date.toLocaleString('fi-FI', {
    day: 'numeric',
    month: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function prepareChartData(data: PoolTempDataPoint[], hoursRange: TimeRangeHours): ChartDataPoint[] {
  // Downsample for performance - keep every Nth point
  const maxPoints = hoursRange <= 48 ? 100 : 200;
  const step = Math.max(1, Math.floor(data.length / maxPoints));

  return data
    .filter((_, i) => i % step === 0)
    .map(d => ({
      timestamp: d.timestamp.getTime(),
      temperature: d.temperature,
      timeLabel: formatAxisLabel(d.timestamp, hoursRange),
      tooltipLabel: formatTooltipLabel(d.timestamp),
      isSmoothed: d.isSmoothed,
    }));
}

function calculateStats(data: PoolTempDataPoint[]) {
  if (data.length === 0) {
    return { min: 0, max: 0, avg: 0, current: 0 };
  }

  const temps = data.map(d => d.temperature);
  const min = Math.min(...temps);
  const max = Math.max(...temps);
  const avg = temps.reduce((a, b) => a + b, 0) / temps.length;
  const current = data[data.length - 1]?.temperature ?? 0;

  return { min, max, avg, current };
}

export function PoolTempModal({ open, onOpenChange, targetTemp }: PoolTempModalProps) {
  const { t } = useTranslation();
  const [timeRange, setTimeRange] = useState<TimeRangeHours>(24);
  const { data, loading, error, refetch } = usePoolTempHistory(timeRange);

  const chartData = prepareChartData(data, timeRange);
  const stats = calculateStats(data);

  // Calculate Y-axis domain
  const temps = chartData.map(d => d.temperature);
  const minTemp = temps.length > 0 ? Math.min(...temps, targetTemp) - 1 : 20;
  const maxTemp = temps.length > 0 ? Math.max(...temps, targetTemp) + 1 : 30;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Thermometer className="w-5 h-5 text-hot" />
            {t('pool.tempHistory', 'Pool Temperature History')}
          </DialogTitle>
        </DialogHeader>

        {/* Time range selector */}
        <div className="flex items-center justify-between">
          <div className="flex gap-1">
            {TIME_RANGE_OPTIONS.map(option => (
              <Button
                key={option.value}
                variant={timeRange === option.value ? 'default' : 'outline'}
                size="sm"
                onClick={() => setTimeRange(option.value)}
              >
                {option.label}
              </Button>
            ))}
          </div>
          <Button variant="ghost" size="sm" onClick={refetch} disabled={loading}>
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
          </Button>
        </div>

        {/* Stats cards */}
        <div className="grid grid-cols-4 gap-2">
          <div className="p-2 rounded-lg bg-muted/50 text-center">
            <div className="text-xs text-muted-foreground">{t('stats.current', 'Current')}</div>
            <div className="text-lg font-mono font-bold text-hot">{stats.current.toFixed(1)}°C</div>
          </div>
          <div className="p-2 rounded-lg bg-muted/50 text-center">
            <div className="text-xs text-muted-foreground flex items-center justify-center gap-1">
              <TrendingDown className="w-3 h-3" />
              {t('stats.min', 'Min')}
            </div>
            <div className="text-lg font-mono">{stats.min.toFixed(1)}°C</div>
          </div>
          <div className="p-2 rounded-lg bg-muted/50 text-center">
            <div className="text-xs text-muted-foreground flex items-center justify-center gap-1">
              <TrendingUp className="w-3 h-3" />
              {t('stats.max', 'Max')}
            </div>
            <div className="text-lg font-mono">{stats.max.toFixed(1)}°C</div>
          </div>
          <div className="p-2 rounded-lg bg-muted/50 text-center">
            <div className="text-xs text-muted-foreground flex items-center justify-center gap-1">
              <BarChart3 className="w-3 h-3" />
              {t('stats.avg', 'Avg')}
            </div>
            <div className="text-lg font-mono">{stats.avg.toFixed(1)}°C</div>
          </div>
        </div>

        {/* Chart */}
        <div className="h-64 md:h-80">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <Skeleton className="w-full h-full" />
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full text-destructive">
              {error}
            </div>
          ) : chartData.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              {t('analytics.noData', 'No data available')}
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="timeLabel"
                  tick={{ fontSize: 10 }}
                  interval={Math.floor(chartData.length / 6)}
                  className="text-muted-foreground"
                />
                <YAxis
                  domain={[minTemp, maxTemp]}
                  tick={{ fontSize: 10 }}
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
                  formatter={(value: number) => [`${value.toFixed(1)}°C`, t('stats.poolTemp', 'Pool Temp')]}
                  labelFormatter={(_, payload) => {
                    if (payload && payload[0]) {
                      return (payload[0].payload as ChartDataPoint).tooltipLabel;
                    }
                    return '';
                  }}
                />
                <ReferenceLine
                  y={targetTemp}
                  stroke="hsl(var(--warning))"
                  strokeDasharray="5 5"
                  label={{
                    value: `${t('pool.target', 'Target')}: ${targetTemp}°C`,
                    position: 'right',
                    className: 'fill-warning text-xs',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="temperature"
                  stroke="hsl(var(--hot))"
                  strokeWidth={1.5}
                  dot={false}
                  activeDot={{ r: 4, fill: 'hsl(var(--hot))' }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Info note about smoothing */}
        <p className="text-xs text-muted-foreground">
          {t('pool.tempNote', 'Temperature readings are smoothed to filter calibration artifacts. Spikes above 28°C from heat exchanger backwash are automatically reduced.')}
        </p>
      </DialogContent>
    </Dialog>
  );
}
