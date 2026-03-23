"""Deterministic mock provider for testing and demos — no API keys needed."""

import json

from naturalsentinel.fetchers.sample_data import MOCK_ANALYSES
from naturalsentinel.providers.base import ModelProvider


class MockProvider(ModelProvider):
    """Returns pre-built structured JSON responses keyed by filing ID."""

    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        # Match on the FILING ID line specifically to avoid false matches
        # from memory context blocks that reference other filing IDs
        import re

        id_match = re.search(r"FILING ID:\s*(\S+)", user)
        if id_match:
            fid = id_match.group(1)
            if fid in MOCK_ANALYSES:
                return json.dumps(MOCK_ANALYSES[fid])

        # Fallback: check if any known ID appears in the prompt
        for fid, analysis in MOCK_ANALYSES.items():
            if fid in user:
                return json.dumps(analysis)

        return json.dumps(
            {
                "summary": "Unknown filing.",
                "severity": "low",
                "affected_business_lines": [],
                "affected_regulations": [],
                "compliance_deadline": None,
                "action_items": ["Manual review required"],
                "risk_summary": "N/A",
                "confidence": 0.3,
            }
        )

    def name(self) -> str:
        return "MockProvider/demo"
