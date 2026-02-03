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
  start: string;          // Display time HH:MM - preheat start (15 min before heating)
  heatingStart: string;   // Display time HH:MM - actual heating start
  end: string;            // Display time HH:MM - heating end
  endDateTime: string;    // Full ISO datetime for comparison
  price: number;
  duration: number;       // Heating duration in minutes (not including preheat)
  preheatDuration: number; // Preheat duration in minutes (15)
  enabled: boolean;
  costEur: number;        // Cost of this block in EUR (heating only, preheat is FREE)
  costExceeded: boolean;  // True if disabled due to cost limit
}

export interface ScheduleParameters {
  minBlockDuration: number;  // 30, 45, or 60 minutes (heating duration, preheat added automatically)
  maxBlockDuration: number;  // 30, 45, or 60 minutes (heating duration, preheat added automatically)
  totalHours: number;        // 0 to 6 in 0.5 steps
  maxCostEur: number | null; // Maximum cost limit in EUR, null = no limit
  minBreakDuration: number;  // 60, 75, 90, 105, or 120 minutes between blocks
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
  comfortWheel: number;         // Comfort wheel setting (room temp offset)
}

export interface ExternalHeaterSettings {
  alwaysEnableTemp: number;     // Enable in extreme cold (-15°C default)
  alwaysDisableTemp: number;    // Disable when warmer (-10°C default)
  offpeakEnableTemp: number;    // Enable during off-peak (-5°C default)
  offpeakDisableTemp: number;   // Disable during off-peak (-2°C default)
  durationMinutes: number;      // Duration threshold (30 min default)
  manualControl: boolean;       // Manual control mode (disables automations)
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
  externalHeater: ExternalHeaterSettings;
}
