"""
State manager for Home Assistant entity states.

Manages all pool heating entities in HA-compatible format, enabling
the mock server to speak the real HA WebSocket protocol.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# Load entity signatures for initialization
SIGNATURE_FILE = Path(__file__).parent / "entity_signatures.json"


class MockStateManager:
    """
    Manages entity states for mock HA.

    Provides HA-compatible state format and handles service calls
    that mutate state.
    """

    def __init__(self):
        self.entities: dict[str, dict[str, Any]] = {}
        self.change_listeners: list[Callable[[str, dict, dict], Awaitable[None]]] = []
        self._init_entities()

    def _init_entities(self):
        """Initialize all pool heating entities with defaults."""
        # Load signatures to get complete entity list
        signatures = self._load_signatures()

        for sig in signatures.get("entities", []):
            entity_id = sig["entity_id"]
            domain = sig["domain"]

            # Determine default state based on domain/type
            default_state = self._get_default_state(sig)
            attrs = self._get_default_attributes(sig)

            self._add_entity(entity_id, default_state, **attrs)

        # Add any missing essential entities not in signatures
        self._add_essential_entities()

        logger.info(f"Initialized {len(self.entities)} entities")

    def _load_signatures(self) -> dict:
        """Load entity signatures from file."""
        if not SIGNATURE_FILE.exists():
            logger.warning(f"Signature file not found: {SIGNATURE_FILE}")
            return {"entities": []}
        with open(SIGNATURE_FILE) as f:
            return json.load(f)

    def _get_default_state(self, sig: dict) -> str:
        """Get default state value for an entity."""
        entity_id = sig["entity_id"]
        domain = sig["domain"]
        state_type = sig.get("state_type", "string")

        # Boolean entities
        if state_type == "boolean":
            # Most booleans default to off
            if "enabled" in entity_id:
                return "off"
            if "cost_exceeded" in entity_id:
                return "off"
            if "night_complete" in entity_id:
                return "off"
            if "cost_limit" in entity_id:
                return "off"
            if "active" in entity_id:
                return "off"
            if "heating_window" in entity_id:
                return "off"
            if "tomorrow_available" in entity_id:
                return "on"
            return "off"

        # Numeric entities
        if state_type == "numeric":
            # Schedule parameters
            if "min_block_duration" in entity_id:
                return "30"
            if "max_block_duration" in entity_id:
                return "45"
            if "total_hours" in entity_id:
                return "2"
            if "max_cost" in entity_id:
                return "0"

            # Block data
            if "_price" in entity_id:
                return "5.0"
            if "_cost" in entity_id:
                return "0"

            # Temperatures
            if "temperature" in entity_id or "temp" in entity_id:
                if "outdoor" in entity_id:
                    return "5.0"
                if "pool" in entity_id or "return" in entity_id:
                    return "25.0"
                if "condenser_out" in entity_id:
                    return "35.0"
                if "condenser_in" in entity_id:
                    return "30.0"
                if "system_supply_line_temperature" in entity_id:
                    return "32.5"
                if "system_supply_line_calculated_set_point" in entity_id:
                    return "35.0"
                if "tap_water" in entity_id:
                    if "start" in entity_id:
                        return "45"
                    if "stop" in entity_id:
                        return "55"
                    return "50.0"
                if "discharge_pipe" in entity_id:
                    return "65.0"
                if "hot_gas" in entity_id:
                    if "pump_start" in entity_id:
                        return "70"
                    if "lower" in entity_id:
                        return "60"
                    if "upper" in entity_id:
                        return "100"
                if "heat_curve" in entity_id:
                    if "max" in entity_id:
                        return "55"
                    if "min" in entity_id:
                        return "25"
                return "20.0"

            # Fixed supply set point
            if "fixed_system_supply_set_point" in entity_id:
                return "30"

            # Gear limits
            if "gear" in entity_id:
                if "minimum" in entity_id:
                    return "1"
                if "maximum" in entity_id:
                    return "10"
                return "5"

            # Sensors
            if "block_count" in entity_id:
                return "0"
            if "nordpool" in entity_id:
                return "5.0"
            if "compressor_speed" in entity_id:
                return "0"
            if "thermal_power" in entity_id:
                return "0"
            if "electrical_power" in entity_id:
                return "0"
            if "cost_rate" in entity_id:
                return "0"
            if "_daily" in entity_id:
                return "0"

            # Default numeric
            min_val = sig.get("min_value")
            if min_val is not None:
                return str(min_val)
            return "0"

        # Datetime entities
        if state_type == "datetime":
            return ""

        # String entities
        if "schedule_info" in entity_id:
            return "No schedule"
        if "next_heating" in entity_id:
            return "unknown"
        if "debug" in entity_id:
            return ""

        return "unknown"

    def _get_default_attributes(self, sig: dict) -> dict:
        """Get default attributes for an entity."""
        entity_id = sig["entity_id"]
        domain = sig["domain"]
        attrs = {}

        # Friendly name from entity_id
        friendly_name = entity_id.split(".")[-1].replace("_", " ").title()
        attrs["friendly_name"] = friendly_name

        # Unit of measurement
        if sig.get("unit_of_measurement"):
            attrs["unit_of_measurement"] = sig["unit_of_measurement"]
        elif "temperature" in entity_id or "temp" in entity_id:
            attrs["unit_of_measurement"] = "°C"
        elif "_price" in entity_id:
            attrs["unit_of_measurement"] = "c/kWh"
        elif "_cost" in entity_id:
            attrs["unit_of_measurement"] = "€"
        elif "power" in entity_id:
            attrs["unit_of_measurement"] = "kW"
        elif "energy" in entity_id or "kwh" in entity_id.lower():
            attrs["unit_of_measurement"] = "kWh"

        # Min/max for input_number and number domains
        if sig.get("min_value") is not None:
            attrs["min"] = sig["min_value"]
        if sig.get("max_value") is not None:
            attrs["max"] = sig["max_value"]
        if sig.get("step") is not None:
            attrs["step"] = sig["step"]

        # Device class
        if domain == "binary_sensor":
            if "active" in entity_id or "heating" in entity_id:
                attrs["device_class"] = "running"
            elif "window" in entity_id:
                attrs["device_class"] = "window"

        # Nordpool sensor special attributes
        if "nordpool" in entity_id and domain == "sensor":
            attrs["current_price"] = 5.0
            attrs["raw_today"] = [5.0] * 24
            attrs["raw_tomorrow"] = [5.0] * 24
            attrs["tomorrow_valid"] = True

        return attrs

    def _add_essential_entities(self):
        """Add essential entities that may not be in signatures."""
        # Ensure switches exist
        if "switch.altaan_lammityksen_esto" not in self.entities:
            self._add_entity("switch.altaan_lammityksen_esto", "off",
                           friendly_name="Pool Heating Prevention")
        if "switch.altaan_kiertovesipumppu" not in self.entities:
            self._add_entity("switch.altaan_kiertovesipumppu", "off",
                           friendly_name="Pool Circulation Pump")

    def _add_entity(self, entity_id: str, state: str, **attrs):
        """Add an entity with state and attributes."""
        now = datetime.now(timezone.utc).isoformat()
        self.entities[entity_id] = {
            "entity_id": entity_id,
            "state": state,
            "attributes": {
                "friendly_name": entity_id.split(".")[-1].replace("_", " ").title(),
                **attrs
            },
            "last_changed": now,
            "last_updated": now,
            "context": {
                "id": "mock_context",
                "parent_id": None,
                "user_id": None
            }
        }

    def get_state(self, entity_id: str) -> dict | None:
        """Get state for a single entity."""
        return self.entities.get(entity_id)

    def get_all_entity_states(self) -> list[dict]:
        """Return all entity states in HA format."""
        return list(self.entities.values())

    def set_state(self, entity_id: str, state: str, attributes: dict | None = None) -> dict:
        """Set state for an entity, notifying listeners."""
        if entity_id not in self.entities:
            # Create entity if it doesn't exist
            self._add_entity(entity_id, state, **(attributes or {}))
            return self.entities[entity_id]

        old_state = dict(self.entities[entity_id])
        now = datetime.now(timezone.utc).isoformat()

        # Update state
        if self.entities[entity_id]["state"] != state:
            self.entities[entity_id]["state"] = state
            self.entities[entity_id]["last_changed"] = now

        self.entities[entity_id]["last_updated"] = now

        # Update attributes if provided
        if attributes:
            self.entities[entity_id]["attributes"].update(attributes)

        return self.entities[entity_id]

    async def call_service(
        self,
        domain: str,
        service: str,
        data: dict | None = None,
        target: dict | None = None
    ) -> dict | None:
        """
        Handle service calls, update entity states.

        Args:
            domain: Service domain (input_boolean, switch, etc.)
            service: Service name (turn_on, turn_off, set_value, etc.)
            data: Service data
            target: Target entities

        Returns:
            Service call result
        """
        data = data or {}
        target = target or {}

        # Get target entity IDs
        entity_ids = target.get("entity_id", [])
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]

        # If no target, check data for entity_id
        if not entity_ids and "entity_id" in data:
            entity_ids = data["entity_id"]
            if isinstance(entity_ids, str):
                entity_ids = [entity_ids]

        results = []

        for entity_id in entity_ids:
            if entity_id not in self.entities:
                logger.warning(f"Service call to unknown entity: {entity_id}")
                continue

            old_state = dict(self.entities[entity_id])
            entity_domain = entity_id.split(".")[0]

            # Handle different service types
            if service == "turn_on":
                new_state = "on"
            elif service == "turn_off":
                new_state = "off"
            elif service == "toggle":
                current = self.entities[entity_id]["state"]
                new_state = "off" if current == "on" else "on"
            elif service == "set_value":
                value = data.get("value")
                if value is not None:
                    new_state = str(value)
                else:
                    continue
            elif service == "set_datetime":
                # Handle datetime setting
                dt = data.get("datetime") or data.get("time") or data.get("date")
                new_state = str(dt) if dt else ""
            else:
                logger.warning(f"Unknown service: {domain}.{service}")
                continue

            # Update state
            now = datetime.now(timezone.utc).isoformat()
            if self.entities[entity_id]["state"] != new_state:
                self.entities[entity_id]["state"] = new_state
                self.entities[entity_id]["last_changed"] = now
            self.entities[entity_id]["last_updated"] = now

            new_state_dict = self.entities[entity_id]
            results.append(new_state_dict)

            # Notify listeners
            for listener in self.change_listeners:
                try:
                    await listener(entity_id, old_state, new_state_dict)
                except Exception as e:
                    logger.error(f"Listener error: {e}")

        return {"success": True, "results": results}

    def add_change_listener(self, listener: Callable[[str, dict, dict], Awaitable[None]]):
        """Add a listener for state changes."""
        self.change_listeners.append(listener)

    def remove_change_listener(self, listener: Callable[[str, dict, dict], Awaitable[None]]):
        """Remove a state change listener."""
        if listener in self.change_listeners:
            self.change_listeners.remove(listener)

    def update_schedule_blocks(self, blocks: list[dict]):
        """
        Update block entities from schedule calculation.

        Args:
            blocks: List of block dicts with start, end, price, cost, enabled, costExceeded
        """
        # Update block count
        self.set_state("sensor.pool_heating_block_count", str(len(blocks)))
        enabled_count = sum(1 for b in blocks if b.get("enabled", True))
        self.set_state("sensor.pool_heating_enabled_block_count", str(enabled_count))

        # Update individual blocks
        for i in range(1, 11):
            if i <= len(blocks):
                block = blocks[i - 1]
                start = block.get("start", "")
                end = block.get("end", "")
                price = block.get("price", 0)
                cost = block.get("costEur", 0)
                enabled = block.get("enabled", True)
                cost_exceeded = block.get("costExceeded", False)

                self.set_state(f"input_datetime.pool_heat_block_{i}_start", str(start))
                self.set_state(f"input_datetime.pool_heat_block_{i}_end", str(end))
                self.set_state(f"input_number.pool_heat_block_{i}_price", str(price))
                self.set_state(f"input_number.pool_heat_block_{i}_cost", str(cost))
                self.set_state(f"input_boolean.pool_heat_block_{i}_enabled",
                             "on" if enabled else "off")
                self.set_state(f"input_boolean.pool_heat_block_{i}_cost_exceeded",
                             "on" if cost_exceeded else "off")
            else:
                # Clear unused blocks
                self.set_state(f"input_datetime.pool_heat_block_{i}_start", "")
                self.set_state(f"input_datetime.pool_heat_block_{i}_end", "")
                self.set_state(f"input_number.pool_heat_block_{i}_price", "0")
                self.set_state(f"input_number.pool_heat_block_{i}_cost", "0")
                self.set_state(f"input_boolean.pool_heat_block_{i}_enabled", "off")
                self.set_state(f"input_boolean.pool_heat_block_{i}_cost_exceeded", "off")

    def update_schedule_parameters(self, min_block: int, max_block: int, total_hours: float, max_cost: float | None):
        """Update schedule parameter entities."""
        self.set_state("input_number.pool_heating_min_block_duration", str(min_block))
        self.set_state("input_number.pool_heating_max_block_duration", str(max_block))
        self.set_state("input_number.pool_heating_total_hours", str(total_hours))
        self.set_state("input_number.pool_heating_max_cost_eur", str(max_cost or 0))

    def update_cost_state(self, total_cost: float, cost_limit_applied: bool):
        """Update cost-related entities."""
        self.set_state("input_boolean.pool_heating_cost_limit_applied",
                      "on" if cost_limit_applied else "off")
        # Note: total_cost might be stored in a sensor if needed
