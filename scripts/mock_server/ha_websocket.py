"""
Home Assistant WebSocket API handler for mock server.

Implements the HA WebSocket protocol so that useHomeAssistant.ts
can connect to the mock server directly.

Protocol flow:
1. Client connects
2. Server sends: {"type": "auth_required", "ha_version": "..."}
3. Client sends: {"type": "auth", "access_token": "..."}
4. Server sends: {"type": "auth_ok", "ha_version": "..."}
5. Client sends commands with incrementing IDs
6. Server responds with matching IDs
"""

import json
import logging
import math
import random
from datetime import datetime, timezone, timedelta
from typing import Any

from .state_manager import MockStateManager

logger = logging.getLogger(__name__)

HA_VERSION = "2024.12.0-mock"


class HAWebSocketHandler:
    """
    Handles HA WebSocket protocol messages.

    Supports:
    - auth flow (auth_required -> auth -> auth_ok)
    - get_states
    - subscribe_events
    - call_service
    - recorder/statistics_during_period (stub)
    """

    def __init__(self, state_manager: MockStateManager):
        self.state = state_manager
        self.subscriptions: dict[int, str] = {}  # msg_id -> event_type
        self.authenticated = False

    async def handle_message(self, raw: str) -> list[dict]:
        """
        Process incoming WebSocket message.

        Args:
            raw: Raw JSON string from client

        Returns:
            List of response messages to send back
        """
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            return [{"type": "error", "message": "Invalid JSON"}]

        msg_type = msg.get("type")
        msg_id = msg.get("id")

        responses = []

        # Auth flow
        if msg_type == "auth":
            # Accept any token in mock mode
            self.authenticated = True
            responses.append({
                "type": "auth_ok",
                "ha_version": HA_VERSION
            })
            logger.info("Client authenticated")

        # Commands require authentication
        elif not self.authenticated:
            responses.append({
                "type": "auth_invalid",
                "message": "Authentication required"
            })

        elif msg_type == "get_states":
            # Return all entity states
            states = self.state.get_all_entity_states()
            responses.append({
                "id": msg_id,
                "type": "result",
                "success": True,
                "result": states
            })
            logger.debug(f"get_states: returned {len(states)} entities")

        elif msg_type == "subscribe_events":
            # Subscribe to state changes
            event_type = msg.get("event_type", "state_changed")
            self.subscriptions[msg_id] = event_type
            responses.append({
                "id": msg_id,
                "type": "result",
                "success": True,
                "result": None
            })
            logger.debug(f"Subscribed to {event_type} (id={msg_id})")

        elif msg_type == "unsubscribe_events":
            # Unsubscribe from events
            subscription = msg.get("subscription")
            if subscription in self.subscriptions:
                del self.subscriptions[subscription]
            responses.append({
                "id": msg_id,
                "type": "result",
                "success": True,
                "result": None
            })

        elif msg_type == "call_service":
            # Handle service calls
            domain = msg.get("domain")
            service = msg.get("service")
            service_data = msg.get("service_data", {})
            target = msg.get("target", {})

            logger.info(f"Service call: {domain}.{service} target={target}")

            try:
                result = await self.state.call_service(domain, service, service_data, target)
                responses.append({
                    "id": msg_id,
                    "type": "result",
                    "success": True,
                    "result": result
                })
            except Exception as e:
                logger.error(f"Service call failed: {e}")
                responses.append({
                    "id": msg_id,
                    "type": "result",
                    "success": False,
                    "error": {
                        "code": "service_error",
                        "message": str(e)
                    }
                })

        elif msg_type == "recorder/statistics_during_period":
            # Stub for recorder statistics
            responses.append({
                "id": msg_id,
                "type": "result",
                "success": True,
                "result": {}
            })

        elif msg_type == "history/history_during_period":
            # Generate mock history data for entities
            start_time = msg.get("start_time")
            end_time = msg.get("end_time")
            entity_ids = msg.get("entity_ids", [])
            minimal_response = msg.get("minimal_response", True)

            logger.info(f"History request: {len(entity_ids)} entities, {start_time} to {end_time}")

            result = self._generate_mock_history(
                start_time, end_time, entity_ids, minimal_response
            )
            responses.append({
                "id": msg_id,
                "type": "result",
                "success": True,
                "result": result
            })

        elif msg_type == "config/entity_registry/list":
            # Entity registry - return empty for mock
            responses.append({
                "id": msg_id,
                "type": "result",
                "success": True,
                "result": []
            })

        elif msg_type == "config/device_registry/list":
            # Device registry - return empty for mock
            responses.append({
                "id": msg_id,
                "type": "result",
                "success": True,
                "result": []
            })

        elif msg_type == "get_config":
            # Return mock config
            responses.append({
                "id": msg_id,
                "type": "result",
                "success": True,
                "result": {
                    "components": ["input_boolean", "input_number", "input_datetime", "sensor", "switch"],
                    "latitude": 60.1699,
                    "longitude": 24.9384,
                    "elevation": 0,
                    "unit_system": {
                        "length": "km",
                        "temperature": "°C",
                        "mass": "kg",
                        "volume": "L"
                    },
                    "location_name": "Mock HA",
                    "time_zone": "Europe/Helsinki",
                    "version": HA_VERSION,
                    "state": "RUNNING"
                }
            })

        elif msg_type == "ping":
            responses.append({
                "id": msg_id,
                "type": "pong"
            })

        else:
            logger.warning(f"Unknown message type: {msg_type}")
            if msg_id:
                responses.append({
                    "id": msg_id,
                    "type": "result",
                    "success": False,
                    "error": {
                        "code": "unknown_command",
                        "message": f"Unknown command: {msg_type}"
                    }
                })

        return responses

    def create_state_changed_event(
        self,
        entity_id: str,
        old_state: dict | None,
        new_state: dict
    ) -> list[dict]:
        """
        Create state_changed event messages for all subscriptions.

        Args:
            entity_id: Entity that changed
            old_state: Previous state (None if new entity)
            new_state: New state

        Returns:
            List of event messages for each subscription
        """
        events = []

        for sub_id, event_type in self.subscriptions.items():
            if event_type == "state_changed":
                events.append({
                    "id": sub_id,
                    "type": "event",
                    "event": {
                        "event_type": "state_changed",
                        "data": {
                            "entity_id": entity_id,
                            "old_state": old_state,
                            "new_state": new_state
                        },
                        "origin": "LOCAL",
                        "time_fired": datetime.now(timezone.utc).isoformat(),
                        "context": {
                            "id": "mock_context",
                            "parent_id": None,
                            "user_id": None
                        }
                    }
                })

        return events

    def _generate_mock_history(
        self,
        start_time: str,
        end_time: str,
        entity_ids: list[str],
        minimal_response: bool
    ) -> dict:
        """
        Generate realistic mock history data for entities.

        Returns dict keyed by entity_id with list of state records.
        For minimal_response, uses abbreviated format: {s: state, lu: timestamp}
        """
        # Parse time range
        try:
            start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            start = datetime.now(timezone.utc) - timedelta(hours=24)
            end = datetime.now(timezone.utc)

        duration_hours = (end - start).total_seconds() / 3600

        # Generate ~60 data points per entity (1 per minute for short, less for long)
        if duration_hours <= 1:
            interval_minutes = 1
        elif duration_hours <= 6:
            interval_minutes = 2
        elif duration_hours <= 24:
            interval_minutes = 5
        elif duration_hours <= 168:  # 7 days
            interval_minutes = 15
        else:
            interval_minutes = 60

        result = {}

        for entity_id in entity_ids:
            states = []
            current_time = start
            interval = timedelta(minutes=interval_minutes)

            # Get entity config for realistic values
            config = self._get_entity_history_config(entity_id)

            # Generate time series
            t = 0  # Time index for wave generation
            while current_time <= end:
                value = self._generate_entity_value(entity_id, config, t, duration_hours)
                timestamp_unix = int(current_time.timestamp())

                if minimal_response:
                    # Minimal format: {s: state, lu: timestamp_unix_seconds}
                    states.append({
                        "s": str(round(value, 2)),
                        "lu": timestamp_unix
                    })
                else:
                    # Full format
                    states.append({
                        "entity_id": entity_id,
                        "state": str(round(value, 2)),
                        "attributes": {},
                        "last_changed": current_time.isoformat(),
                        "last_updated": current_time.isoformat()
                    })

                current_time += interval
                t += 1

            result[entity_id] = states

        return result

    def _get_entity_history_config(self, entity_id: str) -> dict:
        """
        Get history generation config for entity.
        Returns: {base, amplitude, period, noise, min, max}
        """
        # PID sum: oscillates around 0, sometimes dips negative
        if "external_heater_pid_sum" in entity_id:
            return {"base": 0, "amplitude": 8, "period": 2.0, "noise": 1.5, "min": -15, "max": 15}

        # Heating integral: slowly varies, mostly negative
        if "heating_season_integral" in entity_id:
            return {"base": -100, "amplitude": 80, "period": 6.0, "noise": 10, "min": -250, "max": 50}

        # Supply line temp difference: small delta around 0
        if "supply_line_temp_difference" in entity_id:
            return {"base": 1.0, "amplitude": 3.0, "period": 1.5, "noise": 0.5, "min": -8, "max": 8}

        # Pool heat exchanger delta: positive when heating
        if "pool_heat_exchanger_delta" in entity_id:
            return {"base": 3.0, "amplitude": 2.0, "period": 2.0, "noise": 0.3, "min": -2, "max": 10}

        # Start/stop thresholds: constant values
        if "external_additional_heater_start" in entity_id:
            return {"base": -10, "amplitude": 0, "period": 1, "noise": 0, "min": -20, "max": 0}
        if "external_additional_heater_stop" in entity_id:
            return {"base": 0, "amplitude": 0, "period": 1, "noise": 0, "min": -10, "max": 10}

        # Heater demand: mostly 0, sometimes spikes
        if "external_additional_heater_current_demand" in entity_id:
            return {"base": 5, "amplitude": 15, "period": 3.0, "noise": 3, "min": 0, "max": 100}

        # Supply temperatures
        if "system_supply_line_temperature" in entity_id:
            return {"base": 48, "amplitude": 8, "period": 4.0, "noise": 1, "min": 35, "max": 60}
        if "system_supply_line_calculated_set_point" in entity_id:
            return {"base": 50, "amplitude": 5, "period": 8.0, "noise": 0.5, "min": 40, "max": 58}

        # Condenser temperatures
        if "condenser_out_temperature" in entity_id:
            return {"base": 45, "amplitude": 10, "period": 3.0, "noise": 1, "min": 30, "max": 65}
        if "condenser_in_temperature" in entity_id:
            return {"base": 28, "amplitude": 5, "period": 3.0, "noise": 0.5, "min": 22, "max": 40}

        # Outdoor temperature
        if "outdoor_temperature" in entity_id:
            return {"base": 5, "amplitude": 8, "period": 24.0, "noise": 1, "min": -10, "max": 20}

        # Compressor
        if "compressor_speed" in entity_id:
            return {"base": 3000, "amplitude": 1500, "period": 2.0, "noise": 100, "min": 0, "max": 6000}
        if "compressor_current_gear" in entity_id:
            return {"base": 5, "amplitude": 3, "period": 2.0, "noise": 0.5, "min": 1, "max": 10}

        # Brine temperatures
        if "brine_in_temperature" in entity_id:
            return {"base": 2, "amplitude": 3, "period": 4.0, "noise": 0.3, "min": -5, "max": 10}
        if "brine_out_temperature" in entity_id:
            return {"base": -1, "amplitude": 2, "period": 4.0, "noise": 0.3, "min": -8, "max": 5}

        # Default: generic sensor
        return {"base": 25, "amplitude": 5, "period": 2.0, "noise": 1, "min": 0, "max": 100}

    def _generate_entity_value(
        self,
        entity_id: str,
        config: dict,
        t: int,
        duration_hours: float
    ) -> float:
        """Generate a realistic value for entity at time index t."""
        base = config["base"]
        amplitude = config["amplitude"]
        period = config["period"]
        noise = config["noise"]
        min_val = config["min"]
        max_val = config["max"]

        # Scale period based on duration (more variation for longer periods)
        scaled_period = period * (1 + duration_hours / 24)

        # Base wave with period
        wave = amplitude * math.sin(2 * math.pi * t / (scaled_period * 12))

        # Add secondary wave for more realism
        wave2 = (amplitude / 3) * math.sin(2 * math.pi * t / (scaled_period * 5))

        # Random noise
        noise_val = random.gauss(0, noise)

        # Combine
        value = base + wave + wave2 + noise_val

        # Clamp to min/max
        return max(min_val, min(max_val, value))

    @staticmethod
    def auth_required_message() -> dict:
        """Get the initial auth_required message."""
        return {
            "type": "auth_required",
            "ha_version": HA_VERSION
        }
