"""JSON serialization helpers for enum-rich dataclasses."""

import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from naturalsentinel.models import MonitorResult


def enum_serializer(obj: Any) -> Any:
    """Default serializer that converts Enum members to their value."""
    if isinstance(obj, Enum):
        return obj.value
    return str(obj)


def serialize_result(result: MonitorResult) -> dict:
    """Convert a MonitorResult into a clean JSON-safe dict with enum values resolved."""
    raw = {
        "filing": asdict(result.filing),
        "impact": asdict(result.impact),
    }
    # Round-trip through JSON to resolve all enums
    return json.loads(json.dumps(raw, default=enum_serializer))


def serialize_results(results: list[MonitorResult]) -> str:
    """Serialize a list of MonitorResults to a JSON string."""
    return json.dumps(
        [serialize_result(r) for r in results],
        indent=2,
        default=enum_serializer,
    )
