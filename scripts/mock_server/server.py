"""
Mock Home Assistant Server for Testing

This server provides endpoints that mimic Home Assistant's behavior for testing
the pool heating web UI without a real HA instance.

Features:
- Real schedule optimization algorithm
- Controllable price scenarios
- Simulated HA state management
- WebSocket-like state updates
- HA-compatible WebSocket API at /api/websocket

Usage:
    python -m scripts.mock_server.server
    # or
    uvicorn scripts.mock_server.server:app --reload --port 8765
"""

import asyncio
import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
import random

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the real algorithm
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.lib.schedule_optimizer import (
    find_best_heating_schedule,
    validate_schedule_parameters,
    generate_15min_prices,
    schedule_to_json,
    calculate_schedule_stats,
    apply_cost_constraint,
    DEFAULT_MIN_BLOCK_MINUTES,
    DEFAULT_MAX_BLOCK_MINUTES,
    DEFAULT_TOTAL_HEATING_MINUTES,
    ENERGY_PER_SLOT_KWH,
)

# Import HA WebSocket support
from .state_manager import MockStateManager
from .ha_websocket import HAWebSocketHandler


# ============================================
# PRICE SCENARIOS
# ============================================

class PriceScenario(str, Enum):
    TYPICAL_WINTER = "typical_winter"
    CHEAP_NIGHT = "cheap_night"
    EXPENSIVE_NIGHT = "expensive_night"
    NEGATIVE_PRICES = "negative_prices"
    FLAT_PRICES = "flat_prices"
    VOLATILE = "volatile"
    HIGH_PRICES = "high_prices"          # For cost constraint testing
    MIXED_HIGH_LOW = "mixed_high_low"    # For cost constraint testing
    GRADUAL_INCREASE = "gradual_increase" # For cost constraint testing
    CUSTOM = "custom"


def generate_scenario_prices(scenario: PriceScenario) -> Dict[str, List[float]]:
    """Generate 15-minute prices for a given scenario."""

    if scenario == PriceScenario.TYPICAL_WINTER:
        # Higher prices during day, lower at night
        hourly_today = [
            0.08, 0.07, 0.06, 0.05, 0.04, 0.05, 0.07, 0.10,  # 0-7
            0.12, 0.14, 0.13, 0.12, 0.11, 0.10, 0.11, 0.12,  # 8-15
            0.15, 0.18, 0.16, 0.12, 0.08, 0.05, 0.04, 0.03,  # 16-23
        ]
        hourly_tomorrow = [
            0.02, 0.02, 0.01, 0.01, 0.02, 0.03, 0.05, 0.08,  # 0-7
            0.10, 0.12, 0.11, 0.10, 0.09, 0.08, 0.09, 0.10,  # 8-15
            0.13, 0.16, 0.14, 0.10, 0.06, 0.04, 0.03, 0.02,  # 16-23
        ]

    elif scenario == PriceScenario.CHEAP_NIGHT:
        # Very cheap prices during night hours
        hourly_today = [0.10] * 21 + [0.02, 0.01, 0.015]
        hourly_tomorrow = [0.01, 0.005, 0.01, 0.015, 0.02, 0.03, 0.05] + [0.10] * 17

    elif scenario == PriceScenario.EXPENSIVE_NIGHT:
        # Unusually expensive night (e.g., cold snap)
        hourly_today = [0.10] * 21 + [0.15, 0.18, 0.20]
        hourly_tomorrow = [0.22, 0.25, 0.20, 0.18, 0.15, 0.12, 0.10] + [0.08] * 17

    elif scenario == PriceScenario.NEGATIVE_PRICES:
        # High wind/solar generation causing negative prices
        hourly_today = [0.05] * 21 + [-0.01, -0.02, -0.01]
        hourly_tomorrow = [-0.03, -0.04, -0.02, 0.01, 0.03, 0.05, 0.06] + [0.08] * 17

    elif scenario == PriceScenario.FLAT_PRICES:
        # Very stable prices (rare)
        hourly_today = [0.05] * 24
        hourly_tomorrow = [0.05] * 24

    elif scenario == PriceScenario.VOLATILE:
        # Random volatile prices
        random.seed(42)  # Reproducible randomness
        hourly_today = [0.03 + random.random() * 0.15 for _ in range(24)]
        hourly_tomorrow = [0.02 + random.random() * 0.12 for _ in range(24)]

    elif scenario == PriceScenario.HIGH_PRICES:
        # All night prices high (0.15-0.25) - cost limit kicks in quickly
        hourly_today = [0.12] * 21 + [0.18, 0.20, 0.22]
        hourly_tomorrow = [0.25, 0.23, 0.20, 0.18, 0.16, 0.15, 0.14] + [0.12] * 17

    elif scenario == PriceScenario.MIXED_HIGH_LOW:
        # First half cheap, second half expensive
        hourly_today = [0.10] * 21 + [0.02, 0.02, 0.02]
        hourly_tomorrow = [0.02, 0.02, 0.02, 0.03, 0.20, 0.22, 0.25] + [0.15] * 17

    elif scenario == PriceScenario.GRADUAL_INCREASE:
        # Prices increase gradually through the night
        hourly_today = [0.10] * 21 + [0.02, 0.03, 0.04]
        hourly_tomorrow = [0.05, 0.07, 0.09, 0.11, 0.13, 0.16, 0.20] + [0.15] * 17

    else:  # CUSTOM - return empty, will be set via API
        hourly_today = [0.05] * 24
        hourly_tomorrow = [0.05] * 24

    return {
        'today': generate_15min_prices(hourly_today),
        'tomorrow': generate_15min_prices(hourly_tomorrow),
    }


# ============================================
# STATE MANAGEMENT
# ============================================

@dataclass
class MockState:
    """Mock Home Assistant state."""

    # Schedule parameters
    min_block_duration: int = DEFAULT_MIN_BLOCK_MINUTES
    max_block_duration: int = DEFAULT_MAX_BLOCK_MINUTES
    total_hours: float = 2.0
    max_cost_eur: Optional[float] = None  # Cost limit, None = no limit
    min_break_duration: int = 90  # Minimum break between blocks

    # Cold weather mode parameters
    cold_weather_mode: bool = False
    cold_enabled_hours: str = "21,22,23,0,1,2,3,4,5,6"
    cold_block_duration: int = 10
    cold_pre_circulation: int = 5
    cold_post_circulation: int = 5

    # Price scenario
    scenario: PriceScenario = PriceScenario.TYPICAL_WINTER
    custom_prices_today: Optional[List[float]] = None
    custom_prices_tomorrow: Optional[List[float]] = None

    # Current prices
    current_price: float = 0.05
    tomorrow_valid: bool = True

    # Schedule state
    schedule_blocks: List[Dict] = field(default_factory=list)
    night_complete: bool = False
    total_cost: float = 0.0          # Total cost of enabled blocks
    cost_limit_applied: bool = False  # True if cost limit caused blocks to be disabled

    # Heating block enabled states
    block_enabled: Dict[int, bool] = field(default_factory=lambda: {1: True, 2: True, 3: True, 4: True})

    # Time simulation
    simulated_hour: Optional[int] = None  # If set, overrides real time

    def get_prices(self) -> Dict[str, List[float]]:
        """Get current prices based on scenario."""
        if self.scenario == PriceScenario.CUSTOM:
            return {
                'today': self.custom_prices_today or generate_15min_prices([0.05] * 24),
                'tomorrow': self.custom_prices_tomorrow or generate_15min_prices([0.05] * 24),
            }
        return generate_scenario_prices(self.scenario)

    def is_in_heating_window(self) -> bool:
        """Check if current (simulated) time is in heating window (21:00-07:00)."""
        hour = self.simulated_hour if self.simulated_hour is not None else datetime.now().hour
        return hour >= 21 or hour < 7

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for API response."""
        prices = self.get_prices()
        return {
            'parameters': {
                'minBlockDuration': self.min_block_duration,
                'maxBlockDuration': self.max_block_duration,
                'totalHours': self.total_hours,
                'maxCostEur': self.max_cost_eur,
                'minBreakDuration': self.min_break_duration,
                'coldWeatherMode': self.cold_weather_mode,
                'coldEnabledHours': self.cold_enabled_hours,
                'coldBlockDuration': self.cold_block_duration,
                'coldPreCirculation': self.cold_pre_circulation,
                'coldPostCirculation': self.cold_post_circulation,
            },
            'scenario': self.scenario.value,
            'currentPrice': self.current_price,
            'tomorrowValid': self.tomorrow_valid,
            'blocks': self.schedule_blocks,
            'nightComplete': self.night_complete,
            'blockEnabled': self.block_enabled,
            'isInHeatingWindow': self.is_in_heating_window(),
            'simulatedHour': self.simulated_hour,
            'priceCount': {
                'today': len(prices['today']),
                'tomorrow': len(prices['tomorrow']),
            },
            'totalCost': self.total_cost,
            'costLimitApplied': self.cost_limit_applied,
        }


# Global state
state = MockState()
connected_clients: List[WebSocket] = []

# HA WebSocket state manager and clients
ha_state_manager = MockStateManager()
ha_connected_clients: Dict[WebSocket, HAWebSocketHandler] = {}


# ============================================
# PYDANTIC MODELS
# ============================================

class ScheduleParameters(BaseModel):
    minBlockDuration: int = DEFAULT_MIN_BLOCK_MINUTES
    maxBlockDuration: int = DEFAULT_MAX_BLOCK_MINUTES
    totalHours: float = 2.0
    maxCostEur: Optional[float] = None  # Cost limit in EUR, None = no limit
    # Cold weather mode parameters
    coldWeatherMode: bool = False
    coldEnabledHours: str = "21,22,23,0,1,2,3,4,5,6"
    coldBlockDuration: int = 5
    coldPreCirculation: int = 5
    coldPostCirculation: int = 5


class CalculateRequest(BaseModel):
    parameters: Optional[ScheduleParameters] = None
    scenario: Optional[str] = None


class SetScenarioRequest(BaseModel):
    scenario: str
    customPricesToday: Optional[List[float]] = None
    customPricesTomorrow: Optional[List[float]] = None


class SimulateTimeRequest(BaseModel):
    hour: Optional[int] = None  # None = use real time


class BlockEnabledRequest(BaseModel):
    blockNumber: int
    enabled: bool


# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(
    title="Pool Heating Mock Server",
    description="Mock HA server for testing the pool heating web UI",
    version="1.0.0"
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def broadcast_state():
    """Broadcast state update to all connected WebSocket clients."""
    message = {
        'type': 'state_changed',
        'state': state.to_dict()
    }
    for client in connected_clients:
        try:
            await client.send_json(message)
        except Exception:
            pass


# ============================================
# REST ENDPOINTS
# ============================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "server": "pool-heating-mock", "time": datetime.now().isoformat()}


@app.get("/api/state")
async def get_state():
    """Get current mock state."""
    return state.to_dict()


@app.post("/api/parameters")
async def set_parameters(params: ScheduleParameters):
    """Set schedule parameters."""
    global state

    # Validate
    validated = validate_schedule_parameters(
        params.minBlockDuration,
        params.maxBlockDuration,
        params.totalHours
    )

    state.min_block_duration = validated['min_block_minutes']
    state.max_block_duration = validated['max_block_minutes']
    state.total_hours = validated['total_minutes'] / 60
    state.max_cost_eur = params.maxCostEur  # Can be None for no limit

    await broadcast_state()

    return {
        "success": True,
        "parameters": {
            "minBlockDuration": state.min_block_duration,
            "maxBlockDuration": state.max_block_duration,
            "totalHours": state.total_hours,
            "maxCostEur": state.max_cost_eur,
        },
        "fallbacks": validated['fallbacks']
    }


def generate_cold_weather_blocks(enabled_hours_str: str, block_duration: int, pre_circ: int, post_circ: int) -> list:
    """Generate cold weather schedule blocks at :05 past each enabled hour."""
    # Parse enabled hours
    hours = set()
    if enabled_hours_str:
        for h in enabled_hours_str.split(','):
            try:
                parsed = int(h.strip())
                if 0 <= parsed <= 23:
                    hours.add(parsed)
            except ValueError:
                pass

    if not hours:
        return []

    # Validate duration (5, 10, or 15)
    if block_duration not in [5, 10, 15]:
        block_duration = 5

    # Sort hours: overnight schedule (21-23 before 0-7)
    overnight_hours = sorted([h for h in hours if h >= 21])
    morning_hours = sorted([h for h in hours if h < 21])
    sorted_hours = overnight_hours + morning_hours

    # Generate blocks
    blocks = []
    now = datetime.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)

    for hour in sorted_hours:
        # Determine date based on hour (21-23 is today, 0-20 is tomorrow)
        block_date = today if hour >= 21 else tomorrow
        # Block starts at :05 past the hour
        heating_start = datetime.combine(block_date, datetime.min.time().replace(hour=hour, minute=5))
        # Pre-circulation before heating
        circ_start = heating_start - timedelta(minutes=pre_circ)
        # Heating ends after block_duration
        heating_end = heating_start + timedelta(minutes=block_duration)

        blocks.append({
            'start': circ_start.isoformat(),
            'heatingStart': heating_start.isoformat(),
            'end': heating_end.isoformat(),
            'duration': block_duration,
            'price': 0.0,  # No price optimization for cold weather
            'costEur': 0.0,
            'enabled': True,
            'costExceeded': False,
        })

    return blocks


@app.post("/api/calculate")
async def calculate_schedule(request: CalculateRequest = None):
    """Calculate optimal schedule using the real algorithm."""
    global state

    # Use request parameters or current state
    if request and request.parameters:
        min_block = request.parameters.minBlockDuration
        max_block = request.parameters.maxBlockDuration
        total_hours = request.parameters.totalHours
        max_cost_eur = request.parameters.maxCostEur
        cold_weather_mode = request.parameters.coldWeatherMode
        cold_enabled_hours = request.parameters.coldEnabledHours
        cold_block_duration = request.parameters.coldBlockDuration
        cold_pre_circ = request.parameters.coldPreCirculation
        cold_post_circ = request.parameters.coldPostCirculation
    else:
        min_block = state.min_block_duration
        max_block = state.max_block_duration
        total_hours = state.total_hours
        max_cost_eur = state.max_cost_eur
        cold_weather_mode = False
        cold_enabled_hours = "21,22,23,0,1,2,3,4,5,6"
        cold_block_duration = 5
        cold_pre_circ = 5
        cold_post_circ = 5

    # Get scenario
    if request and request.scenario:
        try:
            state.scenario = PriceScenario(request.scenario)
        except ValueError:
            raise HTTPException(400, f"Invalid scenario: {request.scenario}")

    # Get prices
    prices = state.get_prices()

    # Cold weather mode - generate fixed-time blocks
    if cold_weather_mode:
        state.schedule_blocks = generate_cold_weather_blocks(
            cold_enabled_hours,
            cold_block_duration,
            cold_pre_circ,
            cold_post_circ
        )
        state.total_cost = 0.0
        state.cost_limit_applied = False

        # Update HA state manager
        ha_state_manager.set_state("input_boolean.pool_heating_cold_weather_mode", "on")
        ha_state_manager.set_state("input_text.pool_heating_cold_enabled_hours", cold_enabled_hours)
        ha_state_manager.set_state("input_number.pool_heating_cold_block_duration", str(cold_block_duration))
        ha_state_manager.set_state("input_number.pool_heating_cold_pre_circulation", str(cold_pre_circ))
        ha_state_manager.set_state("input_number.pool_heating_cold_post_circulation", str(cold_post_circ))
        ha_state_manager.update_schedule_blocks(state.schedule_blocks)

        await broadcast_state()

        return {
            "success": True,
            "schedule": state.schedule_blocks,
            "stats": {
                "block_count": len(state.schedule_blocks),
                "total_minutes": len(state.schedule_blocks) * cold_block_duration,
            },
            "parameters": {
                "coldWeatherMode": True,
                "coldEnabledHours": cold_enabled_hours,
                "coldBlockDuration": cold_block_duration,
                "coldPreCirculation": cold_pre_circ,
                "coldPostCirculation": cold_post_circ,
            },
            "message": f"Cold weather mode: {len(state.schedule_blocks)} blocks at :05 past selected hours"
        }

    # Normal mode - validate parameters
    validated = validate_schedule_parameters(min_block, max_block, total_hours)

    # Handle disabled heating
    if validated['total_minutes'] == 0:
        state.schedule_blocks = []
        state.total_cost = 0.0
        state.cost_limit_applied = False
        await broadcast_state()
        return {
            "success": True,
            "schedule": [],
            "stats": calculate_schedule_stats([]),
            "message": "Heating disabled (0 hours)"
        }

    # Run the real algorithm
    schedule = find_best_heating_schedule(
        prices_today=prices['today'],
        prices_tomorrow=prices['tomorrow'],
        window_start=21,
        window_end=7,
        total_minutes=validated['total_minutes'],
        min_block_minutes=validated['min_block_minutes'],
        max_block_minutes=validated['max_block_minutes'],
        slot_minutes=15
    )

    # Apply cost constraint
    cost_result = apply_cost_constraint(schedule, max_cost_eur)

    # Convert to JSON-serializable format with cost data
    # Note: block['start'] is the heating start time, preheat is 15 min before
    PREHEAT_MINUTES = 15
    state.schedule_blocks = []
    for i, block in enumerate(cost_result['blocks']):
        heating_start = block['start']
        # Calculate preheat start (15 min before heating)
        if hasattr(heating_start, 'isoformat'):
            preheat_start = heating_start - timedelta(minutes=PREHEAT_MINUTES)
            preheat_start_str = preheat_start.isoformat()
            heating_start_str = heating_start.isoformat()
        else:
            preheat_start_str = heating_start  # Fallback
            heating_start_str = heating_start
        state.schedule_blocks.append({
            'start': preheat_start_str,  # Preheat start (15 min before heating)
            'heatingStart': heating_start_str,  # Actual heating start
            'end': block['end'].isoformat() if hasattr(block['end'], 'isoformat') else block['end'],
            'duration': block['duration_minutes'],
            'price': round(block['avg_price'] * 100, 2),  # Convert to cents
            'costEur': round(block['cost_eur'], 4),
            'enabled': block['enabled'],
            'costExceeded': block['cost_exceeded'],
        })

    # Update cost state
    state.total_cost = cost_result['total_cost']
    state.cost_limit_applied = cost_result['cost_limit_applied']

    # Update current price from first tomorrow slot
    if prices['tomorrow']:
        state.current_price = prices['tomorrow'][0]

    await broadcast_state()

    return {
        "success": True,
        "schedule": schedule_to_json(schedule),
        "stats": calculate_schedule_stats(schedule),
        "parameters": {
            "minBlockDuration": validated['min_block_minutes'],
            "maxBlockDuration": validated['max_block_minutes'],
            "totalMinutes": validated['total_minutes'],
            "maxCostEur": max_cost_eur,
        },
        "costConstraint": {
            "totalCost": cost_result['total_cost'],
            "scheduledCost": cost_result['scheduled_cost'],
            "costLimitApplied": cost_result['cost_limit_applied'],
            "enabledCount": cost_result['enabled_count'],
        },
        "fallbacks": validated['fallbacks']
    }


@app.post("/api/scenario")
async def set_scenario(request: SetScenarioRequest):
    """Set price scenario."""
    global state

    try:
        state.scenario = PriceScenario(request.scenario)
    except ValueError:
        raise HTTPException(400, f"Invalid scenario: {request.scenario}")

    if request.customPricesToday:
        state.custom_prices_today = request.customPricesToday
    if request.customPricesTomorrow:
        state.custom_prices_tomorrow = request.customPricesTomorrow

    await broadcast_state()

    return {"success": True, "scenario": state.scenario.value}


@app.get("/api/scenarios")
async def list_scenarios():
    """List available price scenarios."""
    return {
        "scenarios": [s.value for s in PriceScenario],
        "current": state.scenario.value
    }


@app.get("/api/prices")
async def get_prices():
    """Get current prices."""
    prices = state.get_prices()
    return {
        "today": prices['today'],
        "tomorrow": prices['tomorrow'],
        "scenario": state.scenario.value,
        "tomorrowValid": state.tomorrow_valid
    }


@app.post("/api/simulate-time")
async def simulate_time(request: SimulateTimeRequest):
    """Simulate a specific hour for testing heating window behavior."""
    global state
    state.simulated_hour = request.hour
    await broadcast_state()
    return {
        "success": True,
        "simulatedHour": state.simulated_hour,
        "isInHeatingWindow": state.is_in_heating_window()
    }


@app.post("/api/block-enabled")
async def set_block_enabled(request: BlockEnabledRequest):
    """Enable/disable a heating block."""
    global state

    if request.blockNumber < 1 or request.blockNumber > 10:
        raise HTTPException(400, "Block number must be 1-10")

    state.block_enabled[request.blockNumber] = request.enabled

    # Update schedule blocks
    for i, block in enumerate(state.schedule_blocks):
        if i + 1 == request.blockNumber:
            block['enabled'] = request.enabled

    await broadcast_state()

    return {"success": True, "blockNumber": request.blockNumber, "enabled": request.enabled}


@app.post("/api/reset")
async def reset_state():
    """Reset state to defaults."""
    global state
    state = MockState()
    await broadcast_state()
    return {"success": True, "message": "State reset to defaults"}


# ============================================
# ANALYTICS / HISTORY ENDPOINTS
# ============================================

@app.get("/api/states")
async def get_all_states():
    """Get all entity states - returns all entities from HA state manager."""
    # Return all entities from the HA state manager
    return ha_state_manager.get_all_entity_states()


@app.get("/api/history/period/{start_time}")
async def get_history(start_time: str, filter_entity_id: str = None, end_time: str = None):
    """Get entity history - used by analytics page."""
    # Return mock history for the night summary sensor
    if filter_entity_id == "sensor.pool_heating_night_summary":
        return [[
            {
                "entity_id": "sensor.pool_heating_night_summary",
                "state": "11.919",
                "attributes": {
                    "heating_date": "2025-12-05",
                    "cost": 0.4837,
                    "baseline": 0.6462,
                    "savings": 0.1625,
                    "duration": 180,
                    "blocks": 12,
                    "outdoor_temp": 6.0,
                    "pool_temp": 25.2,
                    "avg_price": 0.0406,
                    "unit_of_measurement": "kWh",
                    "device_class": "energy",
                    "state_class": "measurement",
                    "friendly_name": "Pool Heating Night Summary"
                },
                "last_changed": "2025-12-06T07:00:00+00:00",
                "last_updated": "2025-12-06T07:00:00+00:00"
            }
        ]]
    return [[]]


# ============================================
# WEBSOCKET ENDPOINT (Original - for useMockServer.ts)
# ============================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time state updates."""
    await websocket.accept()
    connected_clients.append(websocket)

    try:
        # Send initial state
        await websocket.send_json({
            'type': 'connected',
            'state': state.to_dict()
        })

        # Listen for commands
        while True:
            data = await websocket.receive_json()
            command = data.get('type')

            if command == 'get_state':
                await websocket.send_json({
                    'type': 'state',
                    'state': state.to_dict()
                })

            elif command == 'calculate':
                params = data.get('parameters', {})
                result = await calculate_schedule(CalculateRequest(
                    parameters=ScheduleParameters(**params) if params else None,
                    scenario=data.get('scenario')
                ))
                await websocket.send_json({
                    'type': 'schedule_calculated',
                    'result': result
                })

            elif command == 'set_parameters':
                params = data.get('parameters', {})
                result = await set_parameters(ScheduleParameters(**params))
                await websocket.send_json({
                    'type': 'parameters_updated',
                    'result': result
                })

            elif command == 'set_scenario':
                result = await set_scenario(SetScenarioRequest(
                    scenario=data.get('scenario', 'typical_winter')
                ))
                await websocket.send_json({
                    'type': 'scenario_updated',
                    'result': result
                })

            elif command == 'ping':
                await websocket.send_json({'type': 'pong'})

    except WebSocketDisconnect:
        pass
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


# ============================================
# HA WEBSOCKET API ENDPOINT (for useHomeAssistant.ts)
# ============================================

async def broadcast_ha_state_change(entity_id: str, old_state: dict, new_state: dict):
    """Broadcast state changes to all HA WebSocket clients."""
    for ws, handler in list(ha_connected_clients.items()):
        try:
            events = handler.create_state_changed_event(entity_id, old_state, new_state)
            for event in events:
                await ws.send_json(event)
        except Exception as e:
            logger.error(f"Error broadcasting to HA client: {e}")
            # Remove disconnected client
            ha_connected_clients.pop(ws, None)


# Register broadcaster with state manager
ha_state_manager.add_change_listener(broadcast_ha_state_change)


@app.websocket("/api/websocket")
async def ha_websocket_endpoint(websocket: WebSocket):
    """
    Home Assistant compatible WebSocket endpoint.

    Allows useHomeAssistant.ts to connect to the mock server using
    the same protocol as real HA.
    """
    await websocket.accept()

    # Create handler for this connection
    handler = HAWebSocketHandler(ha_state_manager)
    ha_connected_clients[websocket] = handler

    logger.info("HA WebSocket client connected")

    try:
        # Send auth_required immediately
        await websocket.send_json(HAWebSocketHandler.auth_required_message())

        # Process messages
        while True:
            raw = await websocket.receive_text()
            responses = await handler.handle_message(raw)

            for response in responses:
                await websocket.send_json(response)

    except WebSocketDisconnect:
        logger.info("HA WebSocket client disconnected")
    except Exception as e:
        logger.error(f"HA WebSocket error: {e}")
    finally:
        ha_connected_clients.pop(websocket, None)


# ============================================
# MAIN
# ============================================

def main():
    """Run the mock server."""
    print("=" * 60)
    print("Pool Heating Mock Server")
    print("=" * 60)
    print()
    print("REST Endpoints:")
    print("  GET  /              - Health check")
    print("  GET  /api/state     - Get current state")
    print("  GET  /api/states    - Get all HA entity states")
    print("  POST /api/parameters - Set schedule parameters")
    print("  POST /api/calculate  - Calculate optimal schedule")
    print("  POST /api/scenario   - Set price scenario")
    print("  GET  /api/scenarios  - List available scenarios")
    print("  GET  /api/prices     - Get current prices")
    print("  POST /api/simulate-time - Simulate time for testing")
    print("  POST /api/block-enabled - Enable/disable block")
    print("  POST /api/reset      - Reset to defaults")
    print()
    print("WebSocket Endpoints:")
    print("  WS   /ws            - Custom protocol (useMockServer.ts)")
    print("  WS   /api/websocket - HA protocol (useHomeAssistant.ts)")
    print()
    print(f"HA State Manager: {len(ha_state_manager.entities)} entities loaded")
    print()
    print("Starting server on http://localhost:8765")
    print()

    uvicorn.run(app, host="0.0.0.0", port=8765)


if __name__ == "__main__":
    main()
