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
}

export interface ScheduleState {
  blocks: PriceBlock[];
  nordpoolAvailable: boolean;
  currentPrice: number;
  scheduledMinutes: number;
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

export interface SystemState {
  heatPump: HeatPumpState;
  poolHeating: PoolHeatingState;
  valve: ValveState;
  schedule: ScheduleState;
  gearSettings: GearSettings;
  tapWater: TapWaterState;
  hotGasSettings: HotGasSettings;
  heatingCurve: HeatingCurveSettings;
}
