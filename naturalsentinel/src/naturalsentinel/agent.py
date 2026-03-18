"""Core regulatory monitoring agent — orchestrates fetch → analyze → store."""

import json
import logging
import re
from dataclasses import asdict
from enum import Enum
from pathlib import Path

from naturalsentinel.models import (
    ChangeType,
    ImpactAssessment,
    MonitorResult,
    RegulatoryDomain,
    RegulatoryFiling,
    Severity,
)
from naturalsentinel.providers.base import ModelProvider
from naturalsentinel.fetchers import fetch_filings, DOMAIN_BUSINESS_LINES
from naturalsentinel.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from naturalsentinel.utils.parsing import parse_llm_json
from naturalsentinel.utils.serialization import enum_serializer, serialize_result

logger = logging.getLogger(__name__)


class RegulatoryMonitorAgent:
    """
    The core agentic loop:

      1. Fetch new filings from configured regulatory sources
      2. Deduplicate against previously seen filings
      3. For each new filing, invoke the LLM to parse & assess impact
      4. Store results in persistent memory (if attached)
      5. Return structured results with impact mappings
    """

    def __init__(
        self,
        provider: ModelProvider,
        domains: list[RegulatoryDomain] | None = None,
        custom_business_lines: dict[str, list[str]] | None = None,
        state_path: str = "monitor_state.json",
        memory: "MemoryStore | None" = None,
    ):
        self.provider = provider
        self.domains = domains or list(RegulatoryDomain)
        self.business_lines = {**DOMAIN_BUSINESS_LINES, **(custom_business_lines or {})}
        self.state_path = Path(state_path)
        self.seen_ids: set[str] = set()
        self.memory = memory
        self._load_state()

    # -- State persistence --------------------------------------------------

    def _load_state(self):
        if self.state_path.exists():
            data = json.loads(self.state_path.read_text())
            self.seen_ids = set(data.get("seen_ids", []))

    def _save_state(self):
        self.state_path.write_text(json.dumps({"seen_ids": sorted(self.seen_ids)}))

    # -- Analysis -----------------------------------------------------------

    def _analyze_filing(self, filing: RegulatoryFiling) -> MonitorResult:
        """Send a single filing to the LLM for structured impact analysis."""
        domain_lines = self.business_lines.get(filing.domain.value, [])

        # Build memory context if available
        memory_context = ""
        if self.memory:
            memory_context = self.memory.build_context_block(
                filing.domain.value, filing.raw_text
            )

        user_prompt = USER_PROMPT_TEMPLATE.format(
            filing_id=filing.id,
            domain=filing.domain.value.upper(),
            title=filing.title,
            published_date=filing.published_date,
            source_url=filing.source_url,
            raw_text=filing.raw_text,
            business_lines=", ".join(domain_lines),
        )
        if memory_context:
            user_prompt += "\n" + memory_context

        raw = self.provider.complete(SYSTEM_PROMPT, user_prompt, temperature=0.1)

        fallback = {
            "summary": raw[:500],
            "severity": "medium",
            "affected_business_lines": domain_lines,
            "affected_regulations": [],
            "compliance_deadline": None,
            "action_items": ["Manual review required — model output was unstructured"],
            "risk_summary": "Unable to parse structured assessment.",
            "confidence": 0.3,
        }
        parsed = parse_llm_json(raw, fallback=fallback)

        filing.summary = parsed.get("summary", "")
        if ct := parsed.get("change_type"):
            try:
                filing.change_type = ChangeType(ct)
            except ValueError:
                pass

        impact = ImpactAssessment(
            filing_id=filing.id,
            severity=Severity(parsed.get("severity", "medium")),
            affected_business_lines=parsed.get("affected_business_lines", []),
            affected_regulations=parsed.get("affected_regulations", []),
            compliance_deadline=parsed.get("compliance_deadline"),
            action_items=parsed.get("action_items", []),
            risk_summary=parsed.get("risk_summary", ""),
            confidence=float(parsed.get("confidence", 0.5)),
        )

        return MonitorResult(filing=filing, impact=impact, raw_analysis=raw)

    # -- Public API ---------------------------------------------------------

    def run(self, since_days: int = 30) -> list[MonitorResult]:
        """Execute one monitoring cycle."""
        logger.info(
            "Fetching filings from %s (last %d days)…",
            [d.value for d in self.domains],
            since_days,
        )
        filings = fetch_filings(domains=self.domains, since_days=since_days)
        new_filings = [f for f in filings if f.id not in self.seen_ids]
        logger.info("Found %d filings, %d new", len(filings), len(new_filings))

        results: list[MonitorResult] = []
        for filing in new_filings:
            logger.info("Analyzing: %s — %s", filing.id, filing.title)
            result = self._analyze_filing(filing)
            results.append(result)
            self.seen_ids.add(filing.id)

            if self.memory:
                sr = serialize_result(result)
                self.memory.store_episodic(filing.id, sr["filing"], sr["impact"])

        self._save_state()
        logger.info("Cycle complete. %d results.", len(results))
        return results

    def run_json(self, since_days: int = 30) -> str:
        """Run and return results as a JSON string."""
        results = self.run(since_days=since_days)
        return json.dumps(
            [serialize_result(r) for r in results], indent=2, default=enum_serializer
        )

    def reset_state(self):
        """Clear seen filings to allow re-processing."""
        self.seen_ids.clear()
        if self.state_path.exists():
            self._save_state()
