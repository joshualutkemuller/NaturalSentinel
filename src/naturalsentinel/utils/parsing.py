"""Helpers for parsing structured data from LLM responses."""

import json
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


def extract_json_block(text: str) -> str:
    """
    Strip markdown fences and surrounding prose to isolate a JSON block.

    Handles common LLM output patterns:
      - ```json ... ```
      - ``` ... ```
      - Raw JSON with preamble text
    """
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")

    # If it still doesn't start with { or [, try to find the first JSON object
    if cleaned and cleaned[0] not in ("{", "["):
        match = re.search(r"(\{[\s\S]*\})", cleaned)
        if match:
            cleaned = match.group(1)

    return cleaned


def parse_llm_json(text: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Parse a JSON response from an LLM, with robust error handling.

    Args:
        text: Raw LLM output that should contain JSON.
        fallback: Default dict to return if parsing fails. If None, raises.

    Returns:
        Parsed dict, or fallback if parsing fails and fallback is provided.
    """
    cleaned = extract_json_block(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse LLM JSON: %s (input: %.200s…)", exc, text)
        if fallback is not None:
            return fallback
        raise ValueError(f"LLM returned unparseable JSON: {exc}") from exc
