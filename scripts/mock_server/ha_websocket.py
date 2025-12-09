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
from datetime import datetime, timezone
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

    @staticmethod
    def auth_required_message() -> dict:
        """Get the initial auth_required message."""
        return {
            "type": "auth_required",
            "ha_version": HA_VERSION
        }
