"""JSON serialization helpers for enum-rich models."""

import json
from enum import Enum
from typing import Any


def enum_serializer(obj: Any) -> Any:
    """Default serializer that converts Enum members to their value."""
    if isinstance(obj, Enum):
        return obj.value
    return str(obj)


def serialize_result(result: Any) -> dict:
    """Convert a MonitorResult into a clean JSON-safe dict with enum values resolved."""
    raw = {
        "filing": result.filing.model_dump(),
        "impact": result.impact.model_dump(),
        "decision": result.decision.model_dump(),
        "evidence_ledger": [item.model_dump() for item in result.evidence_ledger],
    }
    # Round-trip through JSON to resolve all enums
    return json.loads(json.dumps(raw, default=enum_serializer))


def serialize_results(results: list[Any]) -> str:
    """Serialize a list of MonitorResults to a JSON string."""
    return json.dumps(
        [serialize_result(r) for r in results],
        indent=2,
        default=enum_serializer,
    )
