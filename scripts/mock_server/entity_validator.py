"""
Entity signature validation for mock server.

Validates mock server entities against committed signatures to ensure
consistency between mock and live Home Assistant.

Supports:
- Offline mode: Uses committed signatures when HA is unreachable
- Development entities: Entities marked deployed=false are skipped in strict mode
- Validation modes: STRICT (fail), WARN (log), SKIP (ignore)
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ValidationMode(Enum):
    """Validation strictness level."""
    STRICT = "strict"  # Fail on any mismatch (deployed entities only)
    WARN = "warn"      # Log warnings but don't fail
    SKIP = "skip"      # Skip validation entirely


@dataclass
class ValidationResult:
    """Result of entity validation."""
    errors: list[str] = field(default_factory=list)       # Hard failures (deployed entity mismatch)
    warnings: list[str] = field(default_factory=list)     # Soft issues (extra mock entities, dev entities)
    dev_entities: list[str] = field(default_factory=list) # Entities marked as not deployed

    @property
    def passed(self) -> bool:
        """True if no errors."""
        return len(self.errors) == 0


SIGNATURE_FILE = Path(__file__).parent / "entity_signatures.json"


def load_signatures(path: Path | None = None) -> dict:
    """
    Load entity signatures from committed file.
    This file is always available (committed to git), enabling offline development.
    """
    if path is None:
        path = SIGNATURE_FILE

    if not path.exists():
        logger.warning(f"Signature file not found: {path}")
        return {"entities": [], "version": 0}

    with open(path) as f:
        return json.load(f)


def validate_mock_entities(
    mock_entities: dict[str, dict[str, Any]],
    mode: ValidationMode = ValidationMode.WARN,
    signature_path: Path | None = None,
) -> ValidationResult:
    """
    Compare mock server entities against committed signatures.

    Args:
        mock_entities: Dict of entity_id -> state dict from MockStateManager
        mode: Validation strictness level
        signature_path: Optional path to signatures file (defaults to SIGNATURE_FILE)

    Returns:
        ValidationResult with errors, warnings, and dev entity list
    """
    if mode == ValidationMode.SKIP:
        return ValidationResult()

    result = ValidationResult()
    signatures = load_signatures(signature_path)
    sig_map = {s["entity_id"]: s for s in signatures.get("entities", [])}

    # Check all signature entities exist in mock
    for sig in signatures.get("entities", []):
        entity_id = sig["entity_id"]
        is_deployed = sig.get("deployed", True)

        # Track development entities
        if not is_deployed:
            result.dev_entities.append(entity_id)

        if entity_id not in mock_entities:
            if is_deployed:
                result.errors.append(f"Missing deployed entity: {entity_id}")
            else:
                result.warnings.append(f"Dev entity not in mock: {entity_id}")
            continue

        mock_state = mock_entities[entity_id]
        state_value = mock_state.get("state", "")

        # Validate state type (only for deployed entities)
        if is_deployed and sig.get("state_type") == "numeric":
            if state_value not in ("unavailable", "unknown", ""):
                try:
                    float(state_value)
                except (ValueError, TypeError):
                    result.errors.append(
                        f"{entity_id}: expected numeric state, got '{state_value}'"
                    )

        # Validate min/max for input_number (deployed only, as warning)
        if is_deployed and sig.get("min_value") is not None:
            try:
                val = float(state_value)
                min_val = sig["min_value"]
                max_val = sig.get("max_value")
                if val < min_val or (max_val is not None and val > max_val):
                    result.warnings.append(
                        f"{entity_id}: value {val} outside [{min_val}, {max_val}]"
                    )
            except (ValueError, TypeError):
                pass

    # Check for extra entities in mock (informational)
    for entity_id in mock_entities:
        if entity_id not in sig_map:
            # Only warn for entities that look like pool heating entities
            if any(prefix in entity_id for prefix in ["pool_heat", "pool_heating", "nordpool", "condenser"]):
                result.warnings.append(f"Mock has undocumented entity: {entity_id}")

    return result


def validate_or_warn(
    mock_entities: dict[str, dict[str, Any]],
    strict: bool = False,
    signature_path: Path | None = None,
) -> bool:
    """
    Convenience function for mock server startup.

    Args:
        mock_entities: Entity states from MockStateManager
        strict: If True, raise exception on errors; if False, just log

    Returns:
        True if validation passed (no errors), False otherwise
    """
    mode = ValidationMode.STRICT if strict else ValidationMode.WARN
    result = validate_mock_entities(mock_entities, mode, signature_path)

    # Log dev entities
    if result.dev_entities:
        logger.info(f"Development entities (not deployed): {len(result.dev_entities)}")
        for eid in result.dev_entities:
            logger.debug(f"  - {eid}")

    # Log warnings
    for warning in result.warnings:
        logger.warning(f"Entity validation: {warning}")

    # Handle errors
    if result.errors:
        msg = f"Entity validation failed with {len(result.errors)} errors:\n"
        msg += "\n".join(f"  - {e}" for e in result.errors)

        if strict:
            raise ValueError(msg)
        else:
            logger.error(msg)
            return False

    logger.info(f"Entity validation passed ({len(result.warnings)} warnings)")
    return True
