import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { ArrowLeft, BarChart3, Loader2, AlertCircle, LineChart } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  TimeRangeSelector,
  SummaryCards,
  EnergyChart,
  CostComparisonChart,
  PoolTempChart,
} from '@/components/analytics';
import { useAnalytics } from '@/hooks/useAnalytics';
import { TimeRange } from '@/types/analytics';
import { ThemeToggle } from '@/components/ThemeToggle';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';

export function Analytics() {
  const [timeRange, setTimeRange] = useState<TimeRange>('1w');
  const { t } = useTranslation();
  const analytics = useAnalytics(timeRange);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/60">
        <div className="container flex h-14 items-center justify-between px-4">
          <div className="flex items-center gap-4">
            <Link to="/">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4 mr-2" />
                {t('app.title')}
              </Button>
            </Link>
            <div className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-primary" />
              <h1 className="text-lg font-semibold">{t('analytics.title')}</h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link to="/graphs">
              <Button variant="ghost" size="sm">
                <LineChart className="w-4 h-4 mr-1" />
                {t('analytics.graphs', { defaultValue: 'Graphs' })}
              </Button>
            </Link>
            <ThemeToggle />
            <LanguageSwitcher />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container px-4 py-6 space-y-6">
        {/* Time Range Selector */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            {analytics.isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
            <span>{analytics.startDate} – {analytics.endDate}</span>
          </div>
        </div>

        {/* Error State */}
        {analytics.error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>{t('analytics.error.title', { defaultValue: 'Error loading data' })}</AlertTitle>
            <AlertDescription>
              {analytics.error}
            </AlertDescription>
          </Alert>
        )}

        {/* Loading State */}
        {analytics.isLoading && !analytics.error && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => (
                <Card key={i} className="animate-pulse">
                  <CardContent className="p-4">
                    <div className="h-4 bg-muted rounded w-2/3 mb-2" />
                    <div className="h-8 bg-muted rounded w-1/2" />
                  </CardContent>
                </Card>
              ))}
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {[...Array(3)].map((_, i) => (
                <Card key={i} className="animate-pulse">
                  <CardContent className="p-4">
                    <div className="h-4 bg-muted rounded w-1/3 mb-4" />
                    <div className="h-[300px] bg-muted rounded" />
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Data Content */}
        {!analytics.isLoading && !analytics.error && (
          <>
            {/* Summary Cards */}
            <SummaryCards summary={analytics.summary} />

            {/* Charts Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <EnergyChart data={analytics.chartData.tempCorrelation} timeRange={timeRange} />
              <CostComparisonChart
                data={analytics.chartData.cost}
                timeRange={timeRange}
                totalSavings={analytics.summary.totalSavings}
              />
              <PoolTempChart
                data={analytics.chartData.poolTemp}
                timeRange={timeRange}
                target={27}
              />
            </div>

            {/* Footer Info */}
            <div className="text-center text-xs text-muted-foreground pt-4 border-t">
              <p>
                {t('analytics.footer.note', {
                  defaultValue: 'Data is calculated based on thermal energy transfer with COP {{cop}}',
                  cop: analytics.summary.avgCOP,
                })}
              </p>
            </div>
          </>
        )}

        {/* No data state */}
        {!analytics.isLoading && !analytics.error && analytics.dailyStats.length === 0 && (
          <div className="text-center py-12 text-muted-foreground">
            <BarChart3 className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>{t('analytics.noData', { defaultValue: 'No data available for this time period' })}</p>
          </div>
        )}
      </main>
    </div>
  );
}
