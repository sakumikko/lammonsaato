# Product Requirements Document

## 1. Overview

**Product Name:** Lammonsaato - Pool Heating Optimizer

**Purpose:** Automate pool heating scheduling to minimize electricity costs by leveraging Nordpool spot pricing, scheduling heating during the cheapest overnight hours.

**Target Users:** Building owners/managers with:
- Thermia Mega ground-source heat pump
- Pool heating circuit controlled via relay/switch
- Electricity purchased at Nordpool spot prices
- Home Assistant running on Raspberry Pi

## 2. Problem Statement

Pool heating is expensive and typically runs at fixed times regardless of electricity prices. Spot pricing can vary 10x between peak and off-peak hours. Manual optimization is impractical since prices change daily and are only known ~13:00 the day before.

## 3. Goals

1. **Cost Reduction:** Reduce pool heating electricity costs by 30-50% through optimal scheduling
2. **Automation:** Fully automatic daily schedule calculation and execution
3. **Reliability:** Handle integration failures gracefully without manual intervention
4. **Transparency:** Track energy usage and costs for analysis

## 4. Functional Requirements

### 4.1 Schedule Optimization

| ID | Requirement |
|----|-------------|
| FR-1 | System SHALL fetch tomorrow's Nordpool prices when they become available (~13:00 CET) |
| FR-2 | System SHALL calculate optimal heating schedule within the defined overnight window |
| FR-3 | System SHALL split total heating time into blocks with mandatory breaks between them |
| FR-4 | System SHALL select the cheapest price combination across all valid block configurations |
| FR-5 | System SHALL store the calculated schedule in Home Assistant entities |
| FR-5a | System SHALL support up to 10 heating blocks per night |
| FR-5b | System SHALL apply cost constraint when configured, enabling only cheapest blocks up to the EUR limit |
| FR-5c | System SHALL calculate energy cost per block based on 5kW power consumption and block duration |

### 4.2 Heating Control

| ID | Requirement |
|----|-------------|
| FR-6 | System SHALL start heating at scheduled block start times |
| FR-7 | System SHALL stop heating at scheduled block end times |
| FR-8 | System SHALL provide manual start/stop override controls |
| FR-9 | System SHALL provide a master enable/disable toggle |
| FR-10 | System SHALL stop heating and skip remaining night schedules when pool target temperature is reached |
| FR-11 | User SHALL be able to disable individual heating blocks (e.g., to skip high-price periods) |

### 4.3 Energy Monitoring

| ID | Requirement |
|----|-------------|
| FR-12 | System SHALL calculate thermal power from condenser temperature differential |
| FR-13 | System SHALL estimate electrical consumption using assumed COP |
| FR-14 | System SHALL calculate real-time cost based on current electricity price |
| FR-15 | System SHALL aggregate daily and monthly energy/cost totals |

### 4.4 Session Logging

| ID | Requirement |
|----|-------------|
| FR-16 | System SHALL log heating session start with initial temperatures |
| FR-17 | System SHALL log temperatures periodically during heating |
| FR-18 | System SHALL log session end with energy/cost summary |
| FR-19 | System SHALL store session data locally in JSON format |

### 4.5 Peak Power Avoidance

| ID | Requirement |
|----|-------------|
| FR-33 | System SHALL adjust heat pump additional heater settings based on time of day to avoid peak power costs |
| FR-34 | System SHALL set external_additional_heater_start to -10°C during daytime (6:40-21:00) |
| FR-35 | System SHALL set external_additional_heater_stop to 0°C during daytime (6:40-21:00) |
| FR-36 | System SHALL set external_additional_heater_start to -6°C during nighttime (21:00-6:40) |
| FR-37 | System SHALL set external_additional_heater_stop to 4°C during nighttime (21:00-6:40) |
| FR-38 | System SHALL apply daytime settings at 6:40 to ensure settings are active before Helen peak hours (7-21) |
| FR-39 | System SHALL apply nighttime settings at 21:00 when peak hours end |

### 4.6 Dashboard & UI

| ID | Requirement |
|----|-------------|
| FR-20 | Dashboard SHALL display current heating status |
| FR-21 | Dashboard SHALL display scheduled heating blocks with times and prices |
| FR-22 | Dashboard SHALL display real-time energy metrics when heating is active |
| FR-23 | Dashboard SHALL display daily/monthly cost summaries |
| FR-24 | Web UI SHALL allow user to set pool target temperature |
| FR-25 | Web UI SHALL allow user to enable/disable individual heating blocks |
| FR-26 | Web UI SHALL allow user to toggle master heating enabled state |
| FR-27 | Web UI SHALL allow user to configure schedule parameters (min/max block duration, total hours) |
| FR-28 | Web UI SHALL allow user to set max cost per night (EUR), with empty = no limit |
| FR-29 | Web UI SHALL display cost per block in EUR |
| FR-30 | Web UI SHALL display total scheduled cost in EUR |
| FR-31 | Web UI SHALL show warning when cost limit causes blocks to be disabled |
| FR-32 | Web UI SHALL allow user to manually override cost-exceeded blocks (re-enable them) |

## 5. Non-Functional Requirements

### 5.1 Reliability

| ID | Requirement |
|----|-------------|
| NFR-1 | System SHALL recover from Thermia integration freezes automatically |
| NFR-2 | System SHALL handle missing or stale sensor data gracefully |
| NFR-3 | System SHALL continue operating if optional sensors are unavailable |
| NFR-4 | Automations SHALL not fail if logging service encounters errors |

### 5.2 Performance

| ID | Requirement |
|----|-------------|
| NFR-5 | Schedule calculation SHALL complete within 30 seconds |
| NFR-6 | System SHALL run on Raspberry Pi 4 with Home Assistant OS |

### 5.3 Usability

| ID | Requirement |
|----|-------------|
| NFR-7 | Times SHALL be displayed in 24-hour format |
| NFR-8 | Prices SHALL be displayed in cents per kWh (c/kWh) |
| NFR-9 | Dashboard SHALL work on mobile devices |

## 6. Constraints

### 6.1 Heating Window
- **Start:** 21:00 (9 PM)
- **End:** 07:00 (7 AM next day)
- **Rationale:** Overnight hours typically have lowest prices; avoids peak evening demand

### 6.2 Block Parameters
- **Total Duration:** 0-5 hours (configurable via UI)
- **Block Size:** 30-60 minutes each (configurable min/max)
- **Max Blocks:** 10 per night
- **Break Duration:** Equal to preceding block (allows space heating between pool heating)
- **Rationale:** Shorter blocks with breaks prevent overwhelming heat pump capacity; 5-hour maximum ensures adequate break time within 10-hour window

### 6.3 Energy Calculation Assumptions
- **Flow Rate:** 45 liters per minute
- **COP:** 3.0 (conservative estimate)
- **Specific Heat:** 4.186 kJ/(kg·K)
- **Rationale:** Based on typical Thermia Mega operating parameters

### 6.4 Cost Constraint Assumptions
- **Power Consumption:** 5 kW (heat pump electrical draw during pool heating)
- **Energy per Block:** power × duration (e.g., 30 min block = 2.5 kWh)
- **Cost per Block:** energy × spot price (c/kWh)
- **Rationale:** 5 kW is approximate based on typical compressor power at full load

### 6.5 Helen Peak Power Pricing
- **Peak Hours:** 07:00-21:00
- **Peak Power Charge:** Additional cost when power consumption exceeds threshold during peak hours
- **Mitigation:** Reduce external additional heater usage during peak hours by lowering temperature thresholds
- **Daytime Settings (6:40-21:00):** Start at -10°C, stop at 0°C (effectively disables additional heater in normal conditions)
- **Nighttime Settings (21:00-6:40):** Start at -6°C, stop at 4°C (normal operation)
- **Buffer Time:** Settings applied 20 minutes before peak hours start (6:40) to ensure system has adjusted

### 6.6 Hardware Constraints
- Pool water temperature sensor not available (uses condenser temps instead)
- Thermia integration occasionally freezes (requires periodic reload)
- No direct heat pump control (uses relay to enable/disable circuit)

## 7. Success Metrics

| Metric | Target |
|--------|--------|
| Average price vs. night window average | 20%+ lower |
| System uptime | 99%+ |
| Missed heating blocks due to failures | <1 per month |
| Energy tracking accuracy | Within 20% of actual |

## 8. Out of Scope

- Direct heat pump temperature setpoint control
- Weather-based predictive scheduling
- Multiple pool support
- Cloud dashboard or mobile app
- Automatic price alert notifications
