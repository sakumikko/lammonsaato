#!/usr/bin/env python3
"""
Home Assistant API Client for External Testing

Provides a clean interface to interact with Home Assistant from outside HAOS.
Supports both REST API and WebSocket connections.

Usage:
    from ha_client import HAClient

    client = HAClient("http://homeassistant.local:8123", "your_token")

    # Read sensor
    price = client.get_state("sensor.nordpool_kwh_fi_eur_3_10_024")

    # Call service
    client.call_service("switch", "turn_on", {"entity_id": "switch.pool_heating"})

    # Subscribe to changes
    async for event in client.subscribe_events("state_changed"):
        print(event)
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List, AsyncIterator
from dataclasses import dataclass, field

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


# ============================================
# DATA CLASSES
# ============================================

@dataclass
class EntityState:
    """Represents a Home Assistant entity state."""
    entity_id: str
    state: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    last_changed: Optional[str] = None
    last_updated: Optional[str] = None

    @property
    def as_float(self) -> float:
        """Get state as float."""
        try:
            return float(self.state)
        except (ValueError, TypeError):
            return 0.0

    @property
    def as_int(self) -> int:
        """Get state as int."""
        try:
            return int(float(self.state))
        except (ValueError, TypeError):
            return 0

    @property
    def is_on(self) -> bool:
        """Check if entity is on."""
        return self.state.lower() in ('on', 'true', 'home', 'open')

    @property
    def is_available(self) -> bool:
        """Check if entity is available."""
        return self.state.lower() not in ('unavailable', 'unknown')


@dataclass
class ServiceResponse:
    """Response from a service call."""
    success: bool
    changed_states: List[EntityState] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class StateChangedEvent:
    """Represents a state changed event."""
    entity_id: str
    old_state: Optional[EntityState]
    new_state: Optional[EntityState]
    timestamp: datetime = field(default_factory=datetime.now)


# ============================================
# SYNCHRONOUS CLIENT (requests)
# ============================================

class HAClient:
    """
    Synchronous Home Assistant API client.

    Uses requests library for REST API calls.
    """

    def __init__(self, url: str = None, token: str = None):
        """
        Initialize HA client.

        Args:
            url: Home Assistant URL (e.g., http://homeassistant.local:8123)
            token: Long-lived access token
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library required. Install with: pip install requests")

        self.url = (url or os.environ.get("HA_URL", "http://homeassistant.local:8123")).rstrip("/")
        self.token = token or os.environ.get("HA_TOKEN", "")
        self.dry_run = os.environ.get("TEST_DRY_RUN", "false").lower() == "true"

        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def _api_url(self, endpoint: str) -> str:
        """Build full API URL."""
        return f"{self.url}/api/{endpoint.lstrip('/')}"

    def check_connection(self, verbose: bool = False) -> bool:
        """
        Check if HA is reachable and token is valid.

        Args:
            verbose: Print detailed debug info on failure

        Returns:
            True if connection successful
        """
        try:
            url = self._api_url("")
            if verbose:
                print(f"  Connecting to: {url}")
                print(f"  Token: {self.token[:20]}...{self.token[-10:]}" if len(self.token) > 30 else f"  Token: {self.token[:10]}...")

            response = requests.get(url, headers=self._headers, timeout=10)

            if verbose:
                print(f"  Response status: {response.status_code}")
                if response.status_code != 200:
                    print(f"  Response body: {response.text[:500]}")

            return response.status_code == 200

        except requests.exceptions.ConnectionError as e:
            if verbose:
                print(f"  Connection error: {e}")
                print(f"  Is Home Assistant running and accessible at {self.url}?")
            return False
        except requests.exceptions.Timeout as e:
            if verbose:
                print(f"  Timeout error: {e}")
                print(f"  Request to {self.url} timed out after 10 seconds")
            return False
        except requests.RequestException as e:
            if verbose:
                print(f"  Request error: {type(e).__name__}: {e}")
            return False

    def get_state(self, entity_id: str) -> Optional[EntityState]:
        """
        Get state of a single entity.

        Args:
            entity_id: Entity ID (e.g., sensor.temperature)

        Returns:
            EntityState or None if not found
        """
        try:
            response = requests.get(
                self._api_url(f"states/{entity_id}"),
                headers=self._headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return EntityState(
                    entity_id=data["entity_id"],
                    state=data["state"],
                    attributes=data.get("attributes", {}),
                    last_changed=data.get("last_changed"),
                    last_updated=data.get("last_updated")
                )
            elif response.status_code == 404:
                return None
            else:
                print(f"Error getting state: {response.status_code}")
                return None

        except requests.RequestException as e:
            print(f"Request error: {e}")
            return None

    def get_states(self, entity_ids: List[str] = None) -> Dict[str, EntityState]:
        """
        Get states of multiple entities.

        Args:
            entity_ids: List of entity IDs, or None for all entities

        Returns:
            Dict mapping entity_id to EntityState
        """
        try:
            response = requests.get(
                self._api_url("states"),
                headers=self._headers,
                timeout=30
            )

            if response.status_code != 200:
                return {}

            states = {}
            for data in response.json():
                if entity_ids is None or data["entity_id"] in entity_ids:
                    states[data["entity_id"]] = EntityState(
                        entity_id=data["entity_id"],
                        state=data["state"],
                        attributes=data.get("attributes", {}),
                        last_changed=data.get("last_changed"),
                        last_updated=data.get("last_updated")
                    )

            return states

        except requests.RequestException as e:
            print(f"Request error: {e}")
            return {}

    def set_state(self, entity_id: str, state: str, attributes: Dict = None) -> bool:
        """
        Set state of an entity (for testing/mocking).

        Note: This sets the state representation in HA, not the actual device.

        Args:
            entity_id: Entity ID
            state: New state value
            attributes: Optional attributes dict

        Returns:
            True if successful
        """
        if self.dry_run:
            print(f"[DRY RUN] Would set {entity_id} to {state}")
            return True

        try:
            payload = {"state": state}
            if attributes:
                payload["attributes"] = attributes

            response = requests.post(
                self._api_url(f"states/{entity_id}"),
                headers=self._headers,
                json=payload,
                timeout=10
            )

            return response.status_code in (200, 201)

        except requests.RequestException as e:
            print(f"Request error: {e}")
            return False

    def call_service(self, domain: str, service: str,
                     data: Dict = None, return_response: bool = False) -> ServiceResponse:
        """
        Call a Home Assistant service.

        Args:
            domain: Service domain (e.g., switch, light, script)
            service: Service name (e.g., turn_on, turn_off)
            data: Service data (e.g., {"entity_id": "switch.pool"})
            return_response: Request response data from service

        Returns:
            ServiceResponse with success status and changed states
        """
        if self.dry_run:
            print(f"[DRY RUN] Would call {domain}.{service} with {data}")
            return ServiceResponse(success=True)

        try:
            url = self._api_url(f"services/{domain}/{service}")
            if return_response:
                url += "?return_response"

            response = requests.post(
                url,
                headers=self._headers,
                json=data or {},
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                changed = []
                if isinstance(result, list):
                    for item in result:
                        if "entity_id" in item:
                            changed.append(EntityState(
                                entity_id=item["entity_id"],
                                state=item.get("state", ""),
                                attributes=item.get("attributes", {})
                            ))
                return ServiceResponse(success=True, changed_states=changed)
            else:
                return ServiceResponse(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}"
                )

        except requests.RequestException as e:
            return ServiceResponse(success=False, error=str(e))

    def turn_on(self, entity_id: str) -> ServiceResponse:
        """Turn on an entity."""
        domain = entity_id.split(".")[0]
        return self.call_service(domain, "turn_on", {"entity_id": entity_id})

    def turn_off(self, entity_id: str) -> ServiceResponse:
        """Turn off an entity."""
        domain = entity_id.split(".")[0]
        return self.call_service(domain, "turn_off", {"entity_id": entity_id})

    def trigger_automation(self, entity_id: str) -> ServiceResponse:
        """Trigger an automation."""
        return self.call_service("automation", "trigger", {"entity_id": entity_id})

    def run_script(self, entity_id: str) -> ServiceResponse:
        """Run a script."""
        return self.call_service("script", "turn_on", {"entity_id": entity_id})

    def fire_event(self, event_type: str, event_data: Dict = None) -> bool:
        """
        Fire a custom event.

        Args:
            event_type: Event type name
            event_data: Event data dict

        Returns:
            True if successful
        """
        if self.dry_run:
            print(f"[DRY RUN] Would fire event {event_type} with {event_data}")
            return True

        try:
            response = requests.post(
                self._api_url(f"events/{event_type}"),
                headers=self._headers,
                json=event_data or {},
                timeout=10
            )
            return response.status_code == 200

        except requests.RequestException:
            return False

    def get_services(self, domain: str = None) -> Dict:
        """Get available services."""
        try:
            response = requests.get(
                self._api_url("services"),
                headers=self._headers,
                timeout=10
            )

            if response.status_code == 200:
                services = response.json()
                if domain:
                    for svc in services:
                        if svc.get("domain") == domain:
                            return svc
                    return {}
                return services
            return {}

        except requests.RequestException:
            return {}

    def render_template(self, template: str) -> Optional[str]:
        """
        Render a Jinja2 template.

        Args:
            template: Template string

        Returns:
            Rendered template result
        """
        try:
            response = requests.post(
                self._api_url("template"),
                headers=self._headers,
                json={"template": template},
                timeout=10
            )

            if response.status_code == 200:
                return response.text
            return None

        except requests.RequestException:
            return None


# ============================================
# ASYNC CLIENT (aiohttp + websockets)
# ============================================

class AsyncHAClient:
    """
    Asynchronous Home Assistant API client.

    Supports both REST API and WebSocket connections.
    """

    def __init__(self, url: str = None, token: str = None):
        """Initialize async HA client."""
        if not AIOHTTP_AVAILABLE:
            raise ImportError("aiohttp required. Install with: pip install aiohttp")

        self.url = (url or os.environ.get("HA_URL", "http://homeassistant.local:8123")).rstrip("/")
        self.token = token or os.environ.get("HA_TOKEN", "")
        self.dry_run = os.environ.get("TEST_DRY_RUN", "false").lower() == "true"

        self._ws_url = self.url.replace("http://", "ws://").replace("https://", "wss://")
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(headers={
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        })
        return self

    async def __aexit__(self, *args):
        """Async context manager exit."""
        if self._session:
            await self._session.close()

    async def get_state(self, entity_id: str) -> Optional[EntityState]:
        """Get state of an entity asynchronously."""
        async with self._session.get(f"{self.url}/api/states/{entity_id}") as response:
            if response.status == 200:
                data = await response.json()
                return EntityState(
                    entity_id=data["entity_id"],
                    state=data["state"],
                    attributes=data.get("attributes", {}),
                    last_changed=data.get("last_changed"),
                    last_updated=data.get("last_updated")
                )
            return None

    async def call_service(self, domain: str, service: str, data: Dict = None) -> ServiceResponse:
        """Call a service asynchronously."""
        if self.dry_run:
            print(f"[DRY RUN] Would call {domain}.{service}")
            return ServiceResponse(success=True)

        async with self._session.post(
            f"{self.url}/api/services/{domain}/{service}",
            json=data or {}
        ) as response:
            if response.status == 200:
                return ServiceResponse(success=True)
            else:
                text = await response.text()
                return ServiceResponse(success=False, error=f"HTTP {response.status}: {text}")

    async def subscribe_events(self, event_type: str = "state_changed") -> AsyncIterator[StateChangedEvent]:
        """
        Subscribe to Home Assistant events via WebSocket.

        Args:
            event_type: Event type to subscribe to

        Yields:
            StateChangedEvent objects
        """
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets required. Install with: pip install websockets")

        ws_url = f"{self._ws_url}/api/websocket"

        async with websockets.connect(ws_url) as websocket:
            # Wait for auth required message
            await websocket.recv()

            # Authenticate
            await websocket.send(json.dumps({
                "type": "auth",
                "access_token": self.token
            }))

            auth_result = json.loads(await websocket.recv())
            if auth_result.get("type") != "auth_ok":
                raise Exception(f"Authentication failed: {auth_result}")

            # Subscribe to events
            await websocket.send(json.dumps({
                "id": 1,
                "type": "subscribe_events",
                "event_type": event_type
            }))

            # Listen for events
            async for message in websocket:
                event = json.loads(message)

                if event.get("type") == "event":
                    data = event.get("event", {}).get("data", {})
                    entity_id = data.get("entity_id", "")

                    old_state = None
                    new_state = None

                    if data.get("old_state"):
                        old = data["old_state"]
                        old_state = EntityState(
                            entity_id=old.get("entity_id", entity_id),
                            state=old.get("state", ""),
                            attributes=old.get("attributes", {})
                        )

                    if data.get("new_state"):
                        new = data["new_state"]
                        new_state = EntityState(
                            entity_id=new.get("entity_id", entity_id),
                            state=new.get("state", ""),
                            attributes=new.get("attributes", {})
                        )

                    yield StateChangedEvent(
                        entity_id=entity_id,
                        old_state=old_state,
                        new_state=new_state
                    )


# ============================================
# CONVENIENCE FUNCTIONS
# ============================================

def create_client(url: str = None, token: str = None) -> HAClient:
    """Create a synchronous HA client."""
    return HAClient(url, token)


def create_async_client(url: str = None, token: str = None) -> AsyncHAClient:
    """Create an asynchronous HA client."""
    return AsyncHAClient(url, token)


# ============================================
# CLI TESTING
# ============================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test HA API connection")
    parser.add_argument("--url", help="Home Assistant URL")
    parser.add_argument("--token", help="Long-lived access token")
    parser.add_argument("--entity", help="Entity to read")
    parser.add_argument("--service", help="Service to call (format: domain.service)")
    parser.add_argument("--list-services", action="store_true", help="List available services")
    args = parser.parse_args()

    client = HAClient(args.url, args.token)

    print(f"Connecting to {client.url}...")
    if client.check_connection():
        print("Connected successfully!")

        if args.entity:
            state = client.get_state(args.entity)
            if state:
                print(f"\n{state.entity_id}:")
                print(f"  State: {state.state}")
                print(f"  Attributes: {json.dumps(state.attributes, indent=4)}")
            else:
                print(f"Entity {args.entity} not found")

        if args.service:
            domain, service = args.service.split(".")
            result = client.call_service(domain, service)
            print(f"\nService {args.service}: {'OK' if result.success else result.error}")

        if args.list_services:
            services = client.get_services()
            for svc in services:
                print(f"\n{svc['domain']}:")
                for name in svc.get("services", {}).keys():
                    print(f"  - {name}")
    else:
        print("Connection failed!")
        print("Check URL and token are correct")
