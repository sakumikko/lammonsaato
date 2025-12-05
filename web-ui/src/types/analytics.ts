// Time range options for analytics views
export type TimeRange = '1w' | '4w' | '3m' | '12m';

// Daily statistics aggregated from HA history
export interface DailyStats {
  date: string; // ISO date YYYY-MM-DD
  thermalEnergy: number; // kWh transferred to pool
  electricEnergy: number; // kWh consumed (thermalEnergy / COP)
  actualCost: number; // € actual optimized cost
  baselineCost: number; // € what avg 21-07 price would have cost
  savings: number; // € difference (baseline - actual)
  avgOutdoorTemp: number; // °C average
  minOutdoorTemp: number;
  maxOutdoorTemp: number;
  poolTempEnd: number; // °C at end of heating session
  poolTempStart: number; // °C at start
  heatingMinutes: number; // total heating duration
  avgPrice: number; // c/kWh average price paid
  avgBaselinePrice: number; // c/kWh average 21-07 price
}

// Weekly aggregation for longer views (3m, 12m)
export interface WeeklyStats {
  weekStart: string; // ISO date of Monday
  weekNumber: number;
  year: number;
  dailyStats: DailyStats[];
  totals: {
    thermalEnergy: number;
    electricEnergy: number;
    actualCost: number;
    baselineCost: number;
    savings: number;
    heatingMinutes: number;
  };
  averages: {
    outdoorTemp: number;
    poolTempEnd: number;
    pricePerKwh: number;
  };
}

// Chart data point formats
export interface EnergyChartPoint {
  date: string;
  label: string; // "Ma", "Ti", etc. or "Vko 45"
  thermal: number;
  electric: number;
}

export interface CostChartPoint {
  date: string;
  label: string;
  actual: number;
  baseline: number;
  savings: number;
}

export interface TempCorrelationPoint {
  date: string;
  label: string;
  outdoorTemp: number;
  energy: number;
  cost: number;
}

export interface PoolTempPoint {
  date: string;
  label: string;
  temp: number;
  target: number;
}

// Summary statistics for the selected period
export interface AnalyticsSummary {
  totalThermalEnergy: number; // kWh
  totalElectricEnergy: number; // kWh
  totalCost: number; // €
  totalBaseline: number; // €
  totalSavings: number; // €
  savingsPercent: number; // %
  avgOutdoorTemp: number; // °C
  avgPoolTemp: number; // °C
  totalHeatingHours: number;
  avgCOP: number; // Coefficient of Performance
}

// Complete analytics data structure
export interface AnalyticsData {
  timeRange: TimeRange;
  startDate: string;
  endDate: string;
  dailyStats: DailyStats[];
  weeklyStats: WeeklyStats[];
  chartData: {
    energy: EnergyChartPoint[];
    cost: CostChartPoint[];
    tempCorrelation: TempCorrelationPoint[];
    poolTemp: PoolTempPoint[];
  };
  summary: AnalyticsSummary;
}

// Configuration for time ranges
export const TIME_RANGE_CONFIG: Record<TimeRange, { days: number; aggregation: 'daily' | 'weekly'; label: string }> = {
  '1w': { days: 7, aggregation: 'daily', label: '1 Week' },
  '4w': { days: 28, aggregation: 'daily', label: '4 Weeks' },
  '3m': { days: 90, aggregation: 'weekly', label: '3 Months' },
  '12m': { days: 365, aggregation: 'weekly', label: '12 Months' },
};

// Finnish day abbreviations
export const DAY_LABELS_FI = ['Su', 'Ma', 'Ti', 'Ke', 'To', 'Pe', 'La'];
export const DAY_LABELS_EN = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
