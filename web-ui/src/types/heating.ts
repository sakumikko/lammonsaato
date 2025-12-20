export interface HeatPumpState {
  heatEnabled: boolean;
  tapWaterEnabled: boolean;
  compressorGear: number;
  compressorRpm: number;
  brineInTemp: number;
  brineOutTemp: number;
  brineCirculationSpeed: number;
  condenserInTemp: number;
  condenserOutTemp: number;
  condenserDeltaT: number;
  outdoorTemp: number;
  heatpumpMode: 'Heat' | 'Cool' | 'Off';
  // Hot gas / discharge temperatures
  dischargePipeTemp: number;
  suctionGasTemp: number;
  liquidLineTemp: number;
}

export interface PoolHeatingState {
  enabled: boolean;
  active: boolean;
  inHeatingWindow: boolean;
  targetTemp: number;
  nightComplete: boolean;
  returnLineTemp: number;
  heatExchangerDeltaT: number;
  electricalPower: number;
  dailyEnergy: number;
  dailyCost: number;
  monthlyCost: number;
  averagePrice: number;
}

export interface ValveState {
  position: 'pool' | 'radiators';
  transitioning: boolean;
}

export interface PriceBlock {
  start: string;      // Display time HH:MM
  end: string;        // Display time HH:MM
  endDateTime: string; // Full ISO datetime for comparison
  price: number;
  duration: number;
  enabled: boolean;
  costEur: number;        // Cost of this block in EUR
  costExceeded: boolean;  // True if disabled due to cost limit
}

export interface ScheduleParameters {
  minBlockDuration: number;  // 30, 45, or 60 minutes
  maxBlockDuration: number;  // 30, 45, or 60 minutes
  totalHours: number;        // 0 to 6 in 0.5 steps
  maxCostEur: number | null; // Maximum cost limit in EUR, null = no limit
}

export interface ScheduleState {
  blocks: PriceBlock[];
  nordpoolAvailable: boolean;
  currentPrice: number;
  scheduledMinutes: number;
  parameters: ScheduleParameters;
  totalCost: number;          // Total cost of enabled blocks in EUR
  costLimitApplied: boolean;  // True if cost limit caused some blocks to be disabled
}

export interface GearLimits {
  min: number;
  max: number;
}

export interface GearSettings {
  heating: GearLimits;
  pool: GearLimits;
  tapWater: GearLimits;
}

export interface TapWaterState {
  topTemp: number;
  lowerTemp: number;
  weightedTemp: number;
  startTemp: number;
  stopTemp: number;
}

export interface HotGasSettings {
  pumpStartTemp: number;
  lowerStopLimit: number;
  upperStopLimit: number;
}

export interface HeatingCurveSettings {
  maxLimitation: number;
  minLimitation: number;
}

export interface PeakPowerSettings {
  daytimeHeaterStart: number;   // Default: -10°C
  daytimeHeaterStop: number;    // Default: 0°C
  nighttimeHeaterStart: number; // Default: -6°C
  nighttimeHeaterStop: number;  // Default: 4°C
  daytimeStartTime: string;     // Default: "06:40"
  nighttimeStartTime: string;   // Default: "21:00"
}

export interface SystemSupplyState {
  supplyTemp: number;           // Current system supply line temperature
  curveTarget: number;          // Calculated target from heat curve
  fixedTarget: number;          // Fixed supply target setpoint
  fixedModeEnabled: boolean;    // Whether fixed mode is active
}

export interface SystemState {
  heatPump: HeatPumpState;
  poolHeating: PoolHeatingState;
  valve: ValveState;
  schedule: ScheduleState;
  gearSettings: GearSettings;
  tapWater: TapWaterState;
  hotGasSettings: HotGasSettings;
  heatingCurve: HeatingCurveSettings;
  peakPower: PeakPowerSettings;
  systemSupply: SystemSupplyState;
}
