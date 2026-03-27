"""
Regulatory Change Monitor & Impact Mapper
==========================================
An agentic system that monitors regulatory filings (SEC, CFPB, Fed, FDA, EPA, USTR),
parses dense legal/regulatory language, and maps changes to affected business lines
or portfolio exposures.

Supports multiple agentic model backends: OpenAI, Anthropic, Google Gemini, local/Ollama.
"""

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memory import MemoryStore

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class RegulatoryDomain(Enum):
    SEC = "sec"
    CFPB = "cfpb"
    FED = "fed"
    FDA = "fda"
    EPA = "epa"
    USTR = "ustr"


class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeType(Enum):
    PROPOSED_RULE = "proposed_rule"
    FINAL_RULE = "final_rule"
    GUIDANCE = "guidance"
    ENFORCEMENT = "enforcement"
    NOTICE = "notice"
    AMENDMENT = "amendment"
    EXECUTIVE_ORDER = "executive_order"


@dataclass
class RegulatoryFiling:
    id: str
    title: str
    domain: RegulatoryDomain
    source_url: str
    published_date: str
    raw_text: str
    change_type: ChangeType = ChangeType.NOTICE
    summary: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ImpactAssessment:
    filing_id: str
    severity: Severity
    affected_business_lines: list[str]
    affected_regulations: list[str]
    compliance_deadline: str | None
    action_items: list[str]
    risk_summary: str
    confidence: float  # 0-1


@dataclass
class MonitorResult:
    filing: RegulatoryFiling
    impact: ImpactAssessment
    raw_analysis: str


# ---------------------------------------------------------------------------
# Model provider abstraction
# ---------------------------------------------------------------------------


class ModelProvider(ABC):
    """Abstract base for LLM providers used by the agent."""

    @abstractmethod
    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        """Send a prompt and return the model's text response."""

    @abstractmethod
    def name(self) -> str: ...


class AnthropicProvider(ModelProvider):
    """Claude via the Anthropic SDK."""

    def __init__(
        self, model: str = "claude-sonnet-4-20250514", api_key: str | None = None
    ):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("pip install anthropic")
        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model

    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text

    def name(self) -> str:
        return f"Anthropic/{self.model}"


class OpenAIProvider(ModelProvider):
    """GPT-4o / o1 / o3 via OpenAI SDK."""

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("pip install openai")
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model

    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content

    def name(self) -> str:
        return f"OpenAI/{self.model}"


class GeminiProvider(ModelProvider):
    """Google Gemini via the google-genai SDK."""

    def __init__(self, model: str = "gemini-2.0-flash", api_key: str | None = None):
        try:
            from google import genai
        except ImportError:
            raise ImportError("pip install google-genai")
        self.client = genai.Client(api_key=api_key or os.getenv("GOOGLE_API_KEY"))
        self.model = model

    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        from google.genai import types

        resp = self.client.models.generate_content(
            model=self.model,
            contents=f"{system}\n\n{user}",
            config=types.GenerateContentConfig(
                temperature=temperature, max_output_tokens=4096
            ),
        )
        return resp.text

    def name(self) -> str:
        return f"Gemini/{self.model}"


class OllamaProvider(ModelProvider):
    """Local models via Ollama REST API."""

    def __init__(
        self, model: str = "llama3.1", base_url: str = "http://localhost:11434"
    ):
        self.model = model
        self.base_url = base_url

    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        import urllib.request

        payload = json.dumps(
            {
                "model": self.model,
                "stream": False,
                "options": {"temperature": temperature},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        ).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        return data["message"]["content"]

    def name(self) -> str:
        return f"Ollama/{self.model}"


# ---------------------------------------------------------------------------
# Regulatory source fetchers (simulated for demo, real URLs included)
# ---------------------------------------------------------------------------

SAMPLE_FILINGS: list[dict] = [
    {
        "id": "SEC-2026-0312-A",
        "title": "Amendments to Regulation S-K: Climate-Related Disclosures",
        "domain": "sec",
        "source_url": "https://www.sec.gov/rules/proposed/2026/33-11275.htm",
        "published_date": "2026-03-10",
        "change_type": "final_rule",
        "raw_text": (
            "The Securities and Exchange Commission is adopting amendments to Regulation S-K "
            "and Regulation S-X to require registrants to provide certain climate-related "
            "information in their registration statements and annual reports. The final rules "
            "will require disclosure of material climate-related risks, greenhouse gas emissions "
            "(Scope 1, Scope 2, and for larger accelerated filers, Scope 3), transition plans, "
            "governance processes for climate oversight, and financial statement footnotes on "
            "climate impacts. Compliance is phased: Large Accelerated Filers must begin "
            "reporting in fiscal years beginning after December 15, 2026; Accelerated Filers "
            "after December 15, 2027; and Smaller Reporting Companies after December 15, 2028. "
            "Non-compliance may result in enforcement actions, comment letters, and potential "
            "delisting referrals."
        ),
    },
    {
        "id": "CFPB-2026-0228-B",
        "title": "Updated Supervisory Guidance on AI-Driven Credit Decisioning",
        "domain": "cfpb",
        "source_url": "https://www.consumerfinance.gov/rules-policy/notice-2026-02/",
        "published_date": "2026-02-28",
        "change_type": "guidance",
        "raw_text": (
            "The Consumer Financial Protection Bureau issues updated supervisory guidance "
            "clarifying that creditors using artificial intelligence or machine learning models "
            "in credit underwriting must provide specific and accurate adverse action notices "
            "under the Equal Credit Opportunity Act and Fair Credit Reporting Act. The Bureau "
            "expects that creditors will not rely on opaque or unexplainable model outputs. "
            "Creditors must demonstrate model validation, bias testing across protected classes, "
            "and ongoing monitoring with at least quarterly re-validation. Institutions with "
            "assets exceeding $10 billion are subject to immediate supervisory examination. "
            "Smaller institutions have 18 months to demonstrate compliance."
        ),
    },
    {
        "id": "FED-2026-0305-C",
        "title": "Enhanced Prudential Standards for Crypto-Asset Custody by Banking Organizations",
        "domain": "fed",
        "source_url": "https://www.federalreserve.gov/newsevents/pressreleases/bcreg20260305a.htm",
        "published_date": "2026-03-05",
        "change_type": "proposed_rule",
        "raw_text": (
            "The Board of Governors of the Federal Reserve System proposes enhanced prudential "
            "standards for state member banks and bank holding companies engaging in custody "
            "of crypto-assets. The proposed rule would require (1) segregation of customer "
            "crypto-assets from proprietary holdings, (2) capital charges reflecting the "
            "volatility of custodied assets using a modified Basel III framework, (3) quarterly "
            "stress testing of operational and cybersecurity resilience, and (4) board-level "
            "risk governance attestations. Comments are due within 90 days of Federal Register "
            "publication. The Board estimates compliance costs of $2-5 million for mid-size "
            "institutions."
        ),
    },
    {
        "id": "FDA-2026-0301-D",
        "title": "Draft Guidance on Predetermined Change Control Plans for AI/ML-Enabled Medical Devices",
        "domain": "fda",
        "source_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/2026-ai-ml-pccp",
        "published_date": "2026-03-01",
        "change_type": "guidance",
        "raw_text": (
            "The Food and Drug Administration issues draft guidance describing recommendations "
            "for Predetermined Change Control Plans (PCCPs) that manufacturers of AI/ML-enabled "
            "medical devices may include in premarket submissions. The PCCP framework allows "
            "manufacturers to describe planned modifications and the methodology for implementing "
            "those modifications without requiring new premarket submissions for each change. "
            "Manufacturers must specify (a) the description of planned modifications, (b) the "
            "modification protocol including validation and performance testing, and (c) the "
            "impact assessment methodology. This guidance applies to Software as a Medical "
            "Device (SaMD) classified as Class II or Class III. Comments are requested within "
            "60 days."
        ),
    },
    {
        "id": "EPA-2026-0215-E",
        "title": "Revised National Ambient Air Quality Standards for Particulate Matter (PM2.5)",
        "domain": "epa",
        "source_url": "https://www.epa.gov/naaqs/pm-naaqs-2026-revision",
        "published_date": "2026-02-15",
        "change_type": "final_rule",
        "raw_text": (
            "The Environmental Protection Agency finalizes revisions to the National Ambient "
            "Air Quality Standards for fine particulate matter (PM2.5), lowering the annual "
            "standard from 9.0 micrograms per cubic meter to 8.0 micrograms per cubic meter. "
            "The 24-hour standard remains at 35 micrograms per cubic meter. States must submit "
            "revised State Implementation Plans within 24 months. Non-attainment areas will be "
            "redesignated, potentially affecting industrial permitting for manufacturing, power "
            "generation, and transportation sectors. The EPA estimates the rule will prevent "
            "4,200 premature deaths annually. Affected industries should anticipate stricter "
            "Title V permit conditions and potential increases in emissions offset requirements."
        ),
    },
    {
        "id": "USTR-2026-0308-F",
        "title": "Section 301 Tariff Modifications on Semiconductor Equipment and Critical Minerals",
        "domain": "ustr",
        "source_url": "https://ustr.gov/issue-areas/enforcement/section-301-investigations/tariff-actions-2026",
        "published_date": "2026-03-08",
        "change_type": "amendment",
        "raw_text": (
            "The Office of the United States Trade Representative announces modifications to "
            "the Section 301 tariff actions affecting imports of semiconductor manufacturing "
            "equipment and critical minerals from the People's Republic of China. Effective "
            "April 15, 2026, ad valorem tariff rates will increase from 25% to 50% on "
            "lithography equipment (HTS 8486.20), etching machines (HTS 8486.10), and ion "
            "implantation equipment (HTS 8486.40). Additionally, tariffs on refined rare earth "
            "elements (HTS 2846) will increase from 0% to 25%. An exclusion process will be "
            "available for importers demonstrating no viable alternative source. These "
            "modifications are expected to impact semiconductor fabrication cost structures "
            "and supply chains for defense and consumer electronics sectors."
        ),
    },
]

# Maps domain -> list of portfolio/business lines typically affected
DOMAIN_BUSINESS_LINES: dict[str, list[str]] = {
    "sec": [
        "Public Equities",
        "Investment Banking",
        "Corporate Finance",
        "ESG / Sustainability",
        "Investor Relations",
        "Audit & Assurance",
    ],
    "cfpb": [
        "Consumer Lending",
        "Credit Cards",
        "Mortgage Banking",
        "Auto Finance",
        "Fintech Partnerships",
        "Collections",
    ],
    "fed": [
        "Commercial Banking",
        "Digital Assets / Crypto",
        "Treasury & ALM",
        "Risk Management",
        "Capital Markets",
        "Payments",
    ],
    "fda": [
        "Medical Devices",
        "Pharmaceuticals",
        "Biotech",
        "Digital Health / SaMD",
        "Clinical Trials",
        "Regulatory Affairs",
    ],
    "epa": [
        "Manufacturing",
        "Energy & Utilities",
        "Transportation",
        "Real Estate & Construction",
        "Agriculture",
        "Insurance (Environmental)",
    ],
    "ustr": [
        "Supply Chain / Procurement",
        "Semiconductor Manufacturing",
        "Defense Contracting",
        "Consumer Electronics",
        "Critical Minerals",
        "International Trade Finance",
    ],
}


def fetch_filings(
    domains: list[RegulatoryDomain] | None = None,
    since_days: int = 30,
) -> list[RegulatoryFiling]:
    """
    Fetch regulatory filings. In production this would hit real APIs:
      - SEC EDGAR Full-Text Search API
      - Federal Register API (federalregister.gov/api/v1)
      - CFPB regulatory publications
      - FDA guidance document feeds
      - EPA Federal Register notices
      - USTR Federal Register & press releases

    For this demo we return curated sample data.
    """
    cutoff = datetime.utcnow() - timedelta(days=since_days)
    results = []
    for raw in SAMPLE_FILINGS:
        pub = datetime.fromisoformat(raw["published_date"])
        domain = RegulatoryDomain(raw["domain"])
        if domains and domain not in domains:
            continue
        if pub >= cutoff:
            results.append(
                RegulatoryFiling(
                    id=raw["id"],
                    title=raw["title"],
                    domain=domain,
                    source_url=raw["source_url"],
                    published_date=raw["published_date"],
                    change_type=ChangeType(raw["change_type"]),
                    raw_text=raw["raw_text"],
                )
            )
    return results


# ---------------------------------------------------------------------------
# Agentic core: the regulatory monitor agent
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a senior regulatory analyst agent. Your role is to analyze regulatory \
filings and produce structured impact assessments for financial institutions, \
corporations, and portfolio managers.

You MUST respond with valid JSON only — no markdown fences, no commentary outside the JSON.

Output schema:
{
  "summary": "<2-3 sentence plain-English summary of the filing>",
  "change_type": "<proposed_rule|final_rule|guidance|enforcement|notice|amendment|executive_order>",
  "severity": "<low|medium|high|critical>",
  "affected_business_lines": ["<line1>", "<line2>", ...],
  "affected_regulations": ["<existing regulation or statute affected>", ...],
  "compliance_deadline": "<ISO date or null if not specified>",
  "action_items": ["<concrete action 1>", "<concrete action 2>", ...],
  "risk_summary": "<1-2 sentences on residual risk if no action is taken>",
  "confidence": <float 0-1 indicating your confidence in this assessment>
}

Guidelines:
- Identify ALL affected business lines, not just the obvious ones.
- Action items must be specific, actionable, and assigned to a function (Legal, Compliance, Risk, Ops, Tech).
- Severity: critical = immediate enforcement risk or large financial exposure; high = material change with near-term deadline; medium = significant but with reasonable compliance window; low = informational or minor.
- If the filing references other regulations, list them in affected_regulations.
"""

USER_PROMPT_TEMPLATE = """\
Analyze the following regulatory filing and produce a structured impact assessment.

FILING ID: {filing_id}
DOMAIN: {domain}
TITLE: {title}
PUBLISHED: {published_date}
SOURCE: {source_url}

--- BEGIN FILING TEXT ---
{raw_text}
--- END FILING TEXT ---

Context — the organization has exposure to these business lines: {business_lines}

Respond with JSON only.
"""


class RegulatoryMonitorAgent:
    """
    The core agentic loop:
      1. Fetch new filings from configured regulatory sources
      2. Deduplicate against previously seen filings
      3. For each new filing, invoke the LLM to parse & assess impact
      4. Return structured results with impact mappings
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
        self.memory: MemoryStore | None = memory  # Persistent memory (optional)
        self._load_state()
        self.logger = logging.getLogger("RegulatoryMonitor")

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
        # Append memory context to the user prompt
        if memory_context:
            user_prompt += "\n" + memory_context

        raw = self.provider.complete(SYSTEM_PROMPT, user_prompt, temperature=0.1)

        # Parse JSON from response (strip markdown fences if present)
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            self.logger.warning(
                "Model returned non-JSON for %s, wrapping raw output", filing.id
            )
            parsed = {
                "summary": raw[:500],
                "severity": "medium",
                "affected_business_lines": domain_lines,
                "affected_regulations": [],
                "compliance_deadline": None,
                "action_items": [
                    "Manual review required — model output was unstructured"
                ],
                "risk_summary": "Unable to parse structured assessment.",
                "confidence": 0.3,
            }

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
        """
        Execute one monitoring cycle:
          1. Fetch filings
          2. Filter to unseen
          3. Analyze each with the LLM
          4. Persist state
          5. Return results
        """
        self.logger.info(
            "Fetching filings from %s (last %d days)…",
            [d.value for d in self.domains],
            since_days,
        )

        filings = fetch_filings(domains=self.domains, since_days=since_days)
        new_filings = [f for f in filings if f.id not in self.seen_ids]

        self.logger.info("Found %d filings, %d new", len(filings), len(new_filings))

        results: list[MonitorResult] = []
        for filing in new_filings:
            self.logger.info("Analyzing: %s — %s", filing.id, filing.title)
            result = self._analyze_filing(filing)
            results.append(result)
            self.seen_ids.add(filing.id)

            # Persist to memory if available
            if self.memory:

                def _ser(obj):
                    if isinstance(obj, Enum):
                        return obj.value
                    return str(obj)

                f_dict = json.loads(
                    json.dumps(result.filing.model_dump(), default=_ser)
                )
                i_dict = json.loads(
                    json.dumps(result.impact.model_dump(), default=_ser)
                )
                self.memory.store_episodic(filing.id, f_dict, i_dict)

        self._save_state()
        self.logger.info("Cycle complete. %d results.", len(results))
        return results

    def run_json(self, since_days: int = 30) -> str:
        """Run and return results as JSON string."""
        results = self.run(since_days=since_days)

        def _serialize(obj):
            if isinstance(obj, Enum):
                return obj.value
            return str(obj)

        return json.dumps(
            [
                {
                    "filing": r.filing.model_dump(),
                    "impact": r.impact.model_dump(),
                }
                for r in results
            ],
            indent=2,
            default=_serialize,
        )

    def reset_state(self):
        """Clear seen filings to allow re-processing."""
        self.seen_ids.clear()
        self._save_state()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_provider(provider_name: str, model: str | None = None) -> ModelProvider:
    """Factory to build a provider from CLI args."""
    match provider_name.lower():
        case "anthropic":
            return AnthropicProvider(model=model or "claude-sonnet-4-20250514")
        case "openai":
            return OpenAIProvider(model=model or "gpt-4o")
        case "gemini":
            return GeminiProvider(model=model or "gemini-2.0-flash")
        case "ollama":
            return OllamaProvider(model=model or "llama3.1")
        case _:
            raise ValueError(f"Unknown provider: {provider_name}")


def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    parser = argparse.ArgumentParser(
        description="Regulatory Change Monitor & Impact Mapper"
    )
    parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic", "openai", "gemini", "ollama"],
        help="LLM provider to use",
    )
    parser.add_argument("--model", default=None, help="Specific model name override")
    parser.add_argument(
        "--domains",
        nargs="*",
        default=None,
        help="Regulatory domains to monitor (sec cfpb fed fda epa ustr)",
    )
    parser.add_argument("--days", type=int, default=60, help="Look-back window in days")
    parser.add_argument("--reset", action="store_true", help="Reset seen-filings state")
    parser.add_argument("--output", default=None, help="Write JSON output to file")
    args = parser.parse_args()

    provider = _build_provider(args.provider, args.model)
    domains = [RegulatoryDomain(d) for d in args.domains] if args.domains else None

    agent = RegulatoryMonitorAgent(provider=provider, domains=domains)
    if args.reset:
        agent.reset_state()

    output = agent.run_json(since_days=args.days)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Results written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
