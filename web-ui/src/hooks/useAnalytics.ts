import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  TimeRange,
  DailyStats,
  WeeklyStats,
  AnalyticsData,
  AnalyticsSummary,
  EnergyChartPoint,
  CostChartPoint,
  TempCorrelationPoint,
  PoolTempPoint,
  TIME_RANGE_CONFIG,
  DAY_LABELS_FI,
  DAY_LABELS_EN,
} from '@/types/analytics';
import { useHAHistory, DailyHistoryData } from './useHAHistory';

const COP = 3.0; // Coefficient of Performance
const AVG_BASELINE_PRICE = 10; // Average spot price 21-07 in c/kWh (fallback baseline)

// Transform HA history data to DailyStats format
function transformToDailyStats(historyData: DailyHistoryData[]): DailyStats[] {
  return historyData
    .filter((d) => d.electricEnergy !== null) // Only include days with energy data
    .map((d) => {
      const electricEnergy = d.electricEnergy ?? 0;
      const thermalEnergy = electricEnergy * COP;
      const actualCost = d.dailyCost ?? 0;

      // Use baseline cost from night summary if available, otherwise calculate
      const baselineCost = d.baselineCost !== null
        ? d.baselineCost
        : (electricEnergy * AVG_BASELINE_PRICE) / 100;

      // Use savings from night summary if available
      const savings = d.savings !== null
        ? d.savings
        : baselineCost - actualCost;

      // Use avg price from night summary if available
      const avgPrice = d.avgSpotPrice !== null
        ? d.avgSpotPrice
        : (electricEnergy > 0 ? (actualCost / electricEnergy) * 100 : 0);

      // Use duration from night summary if available
      const heatingMinutes = d.duration !== null
        ? d.duration
        : (electricEnergy > 0 ? Math.round(electricEnergy * 60) : 0);

      return {
        date: d.date,
        thermalEnergy: Math.round(thermalEnergy * 100) / 100,
        electricEnergy: Math.round(electricEnergy * 100) / 100,
        actualCost: Math.round(actualCost * 100) / 100,
        baselineCost: Math.round(baselineCost * 100) / 100,
        savings: Math.round(savings * 100) / 100,
        avgOutdoorTemp: d.avgOutdoorTemp !== null ? Math.round(d.avgOutdoorTemp * 10) / 10 : 0,
        minOutdoorTemp: d.avgOutdoorTemp !== null ? Math.round((d.avgOutdoorTemp - 3) * 10) / 10 : 0,
        maxOutdoorTemp: d.avgOutdoorTemp !== null ? Math.round((d.avgOutdoorTemp + 3) * 10) / 10 : 0,
        poolTempEnd: d.poolTemp !== null ? Math.round(d.poolTemp * 10) / 10 : 0,
        poolTempStart: d.poolTemp !== null ? Math.round((d.poolTemp - 2) * 10) / 10 : 0,
        heatingMinutes: heatingMinutes,
        avgPrice: Math.round(avgPrice * 100) / 100,
        avgBaselinePrice: AVG_BASELINE_PRICE,
      };
    });
}

// Aggregate daily stats into weekly stats
function aggregateToWeekly(dailyStats: DailyStats[]): WeeklyStats[] {
  const weeks: Map<string, DailyStats[]> = new Map();

  dailyStats.forEach((day) => {
    const date = new Date(day.date);
    const dayOfWeek = date.getDay();
    const monday = new Date(date);
    monday.setDate(date.getDate() - ((dayOfWeek + 6) % 7));
    const weekKey = monday.toISOString().split('T')[0];

    if (!weeks.has(weekKey)) {
      weeks.set(weekKey, []);
    }
    weeks.get(weekKey)!.push(day);
  });

  const weeklyStats: WeeklyStats[] = [];

  weeks.forEach((days, weekStart) => {
    const date = new Date(weekStart);
    const startOfYear = new Date(date.getFullYear(), 0, 1);
    const weekNumber = Math.ceil(((date.getTime() - startOfYear.getTime()) / 86400000 + startOfYear.getDay() + 1) / 7);

    const totals = {
      thermalEnergy: days.reduce((sum, d) => sum + d.thermalEnergy, 0),
      electricEnergy: days.reduce((sum, d) => sum + d.electricEnergy, 0),
      actualCost: days.reduce((sum, d) => sum + d.actualCost, 0),
      baselineCost: days.reduce((sum, d) => sum + d.baselineCost, 0),
      savings: days.reduce((sum, d) => sum + d.savings, 0),
      heatingMinutes: days.reduce((sum, d) => sum + d.heatingMinutes, 0),
    };

    const averages = {
      outdoorTemp: days.reduce((sum, d) => sum + d.avgOutdoorTemp, 0) / days.length,
      poolTempEnd: days.reduce((sum, d) => sum + d.poolTempEnd, 0) / days.length,
      pricePerKwh: days.reduce((sum, d) => sum + d.avgPrice, 0) / days.length,
    };

    weeklyStats.push({
      weekStart,
      weekNumber,
      year: date.getFullYear(),
      dailyStats: days,
      totals: {
        thermalEnergy: Math.round(totals.thermalEnergy * 100) / 100,
        electricEnergy: Math.round(totals.electricEnergy * 100) / 100,
        actualCost: Math.round(totals.actualCost * 100) / 100,
        baselineCost: Math.round(totals.baselineCost * 100) / 100,
        savings: Math.round(totals.savings * 100) / 100,
        heatingMinutes: totals.heatingMinutes,
      },
      averages: {
        outdoorTemp: Math.round(averages.outdoorTemp * 10) / 10,
        poolTempEnd: Math.round(averages.poolTempEnd * 10) / 10,
        pricePerKwh: Math.round(averages.pricePerKwh * 100) / 100,
      },
    });
  });

  return weeklyStats.sort((a, b) => a.weekStart.localeCompare(b.weekStart));
}

// Calculate summary statistics
function calculateSummary(dailyStats: DailyStats[]): AnalyticsSummary {
  if (dailyStats.length === 0) {
    return {
      totalThermalEnergy: 0,
      totalElectricEnergy: 0,
      totalCost: 0,
      totalBaseline: 0,
      totalSavings: 0,
      savingsPercent: 0,
      avgOutdoorTemp: 0,
      avgPoolTemp: 0,
      totalHeatingHours: 0,
      avgCOP: COP,
    };
  }

  const totalThermalEnergy = dailyStats.reduce((sum, d) => sum + d.thermalEnergy, 0);
  const totalElectricEnergy = dailyStats.reduce((sum, d) => sum + d.electricEnergy, 0);
  const totalCost = dailyStats.reduce((sum, d) => sum + d.actualCost, 0);
  const totalBaseline = dailyStats.reduce((sum, d) => sum + d.baselineCost, 0);
  const totalSavings = totalBaseline - totalCost;
  const totalHeatingMinutes = dailyStats.reduce((sum, d) => sum + d.heatingMinutes, 0);

  return {
    totalThermalEnergy: Math.round(totalThermalEnergy * 10) / 10,
    totalElectricEnergy: Math.round(totalElectricEnergy * 10) / 10,
    totalCost: Math.round(totalCost * 100) / 100,
    totalBaseline: Math.round(totalBaseline * 100) / 100,
    totalSavings: Math.round(totalSavings * 100) / 100,
    savingsPercent: totalBaseline > 0 ? Math.round((totalSavings / totalBaseline) * 1000) / 10 : 0,
    avgOutdoorTemp: Math.round((dailyStats.reduce((sum, d) => sum + d.avgOutdoorTemp, 0) / dailyStats.length) * 10) / 10,
    avgPoolTemp: Math.round((dailyStats.reduce((sum, d) => sum + d.poolTempEnd, 0) / dailyStats.length) * 10) / 10,
    totalHeatingHours: Math.round((totalHeatingMinutes / 60) * 10) / 10,
    avgCOP: COP,
  };
}

export function useAnalytics(timeRange: TimeRange): AnalyticsData & { isLoading: boolean; error: string | null } {
  const { i18n } = useTranslation();
  const dayLabels = i18n.language === 'fi' ? DAY_LABELS_FI : DAY_LABELS_EN;

  // Fetch real data from Home Assistant
  const { data: historyData, loading, error } = useHAHistory(timeRange);

  const data = useMemo(() => {
    const config = TIME_RANGE_CONFIG[timeRange];

    // Transform HA history to our format
    const dailyStats = transformToDailyStats(historyData);
    const weeklyStats = aggregateToWeekly(dailyStats);
    const summary = calculateSummary(dailyStats);

    const now = new Date();
    const startDate = new Date(now);
    startDate.setDate(startDate.getDate() - config.days);

    // Generate chart data based on aggregation type
    const useWeekly = config.aggregation === 'weekly';

    const energyData: EnergyChartPoint[] = useWeekly
      ? weeklyStats.map((w) => ({
          date: w.weekStart,
          label: `Vko ${w.weekNumber}`,
          thermal: w.totals.thermalEnergy,
          electric: w.totals.electricEnergy,
        }))
      : dailyStats.map((d) => {
          const date = new Date(d.date);
          return {
            date: d.date,
            label: dayLabels[date.getDay()],
            thermal: d.thermalEnergy,
            electric: d.electricEnergy,
          };
        });

    const costData: CostChartPoint[] = useWeekly
      ? weeklyStats.map((w) => ({
          date: w.weekStart,
          label: `Vko ${w.weekNumber}`,
          actual: w.totals.actualCost,
          baseline: w.totals.baselineCost,
          savings: w.totals.savings,
        }))
      : dailyStats.map((d) => {
          const date = new Date(d.date);
          return {
            date: d.date,
            label: dayLabels[date.getDay()],
            actual: d.actualCost,
            baseline: d.baselineCost,
            savings: d.savings,
          };
        });

    const tempCorrelationData: TempCorrelationPoint[] = useWeekly
      ? weeklyStats.map((w) => ({
          date: w.weekStart,
          label: `Vko ${w.weekNumber}`,
          outdoorTemp: w.averages.outdoorTemp,
          energy: w.totals.electricEnergy,
          cost: w.totals.actualCost,
        }))
      : dailyStats.map((d) => {
          const date = new Date(d.date);
          return {
            date: d.date,
            label: dayLabels[date.getDay()],
            outdoorTemp: d.avgOutdoorTemp,
            energy: d.electricEnergy,
            cost: d.actualCost,
          };
        });

    const poolTempData: PoolTempPoint[] = useWeekly
      ? weeklyStats.map((w) => ({
          date: w.weekStart,
          label: `Vko ${w.weekNumber}`,
          temp: w.averages.poolTempEnd,
          target: 27, // Default target
        }))
      : dailyStats.map((d) => {
          const date = new Date(d.date);
          return {
            date: d.date,
            label: dayLabels[date.getDay()],
            temp: d.poolTempEnd,
            target: 27,
          };
        });

    return {
      timeRange,
      startDate: startDate.toISOString().split('T')[0],
      endDate: now.toISOString().split('T')[0],
      dailyStats,
      weeklyStats,
      chartData: {
        energy: energyData,
        cost: costData,
        tempCorrelation: tempCorrelationData,
        poolTemp: poolTempData,
      },
      summary,
    };
  }, [timeRange, dayLabels, historyData]);

  return {
    ...data,
    isLoading: loading,
    error,
  };
}
