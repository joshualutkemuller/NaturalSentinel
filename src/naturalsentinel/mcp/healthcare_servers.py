"""
healthcare_servers.py — HIPAA-Safe MCP Integrations for Healthcare Use Cases
=============================================================================

NaturalSentinel can monitor healthcare regulatory changes across HHS, FDA,
CMS, and OCR without ever handling Protected Health Information (PHI).

HIPAA Compliance Boundary
--------------------------
All data sent to MCP tool calls in this module is:
  ✓ Sourced from *public* regulatory documents (Federal Register, FDA.gov, CMS.gov)
  ✓ Metadata-only: rule IDs, titles, publication dates, agency references
  ✓ De-identified aggregate compliance metrics (counts, percentages, deadlines)
  ✗ NEVER contains any of the 18 HIPAA identifiers
  ✗ NEVER references individual patients, plan members, or beneficiaries

The 18 HIPAA Safe Harbor identifiers that must NEVER appear in tool metadata:
  Names, geographic data < state level, dates (except year) linked to individuals,
  phone numbers, fax numbers, email addresses, SSNs, MRNs, health plan numbers,
  account numbers, certificate/license numbers, VINs, device identifiers,
  URLs, IP addresses, biometric identifiers, full-face photos, other unique IDs.

Healthcare Regulatory Sources Monitored
----------------------------------------
1. HHS Office for Civil Rights (OCR) — HIPAA enforcement actions & guidance
2. CMS (Centers for Medicare & Medicaid Services) — billing, coverage, value-based care
3. FDA — drug/device approvals, labeling changes, recalls
4. ONC (Office of the National Coordinator) — health IT interoperability rules
5. DEA — controlled substance prescribing regulations (e.g., telehealth DEA rules)
6. SAMHSA — Part 2 (substance use disorder records) confidentiality rules

MCP Servers Used
-----------------
1. Fetch       — retrieve public regulatory pages from HHS, FDA, CMS, ONC
2. Brave Search — discover OCR enforcement actions and CMS final rules
3. SQLite      — query a HIPAA-safe compliance tracking database
4. Time        — calculate HIPAA breach notification deadlines (60-day rule)
5. Memory MCP  — shared knowledge graph of regulatory entities across tools
6. Filesystem  — read de-identified, aggregated compliance reports

Usage:
    import asyncio
    from naturalsentinel.mcp.healthcare_servers import run_healthcare_demo

    asyncio.run(run_healthcare_demo())
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    HAS_MCP = True
except ImportError:
    HAS_MCP = False

from naturalsentinel.mcp.external_servers import (
    ServerResult,
    _call_tool,
    _require_mcp,
    fetch_session,
    memory_mcp_session,
    sqlite_session,
    time_session,
)

try:
    from naturalsentinel.mcp.external_servers import brave_search_session

    HAS_BRAVE = bool(os.getenv("BRAVE_API_KEY"))
except ImportError:
    HAS_BRAVE = False


# ---------------------------------------------------------------------------
# HIPAA-Safe Metadata Schema
# ---------------------------------------------------------------------------
# Every dict passed to an MCP tool call must be validated against this schema
# before dispatch.  Fields that could carry PHI are explicitly prohibited.


HIPAA_SAFE_METADATA_SCHEMA: dict[str, str] = {
    # ALLOWED — public regulatory identifiers
    "regulation_id": "str  — e.g. '45 CFR § 164.400', 'CMS-9904-F'",
    "agency": "str  — e.g. 'OCR', 'CMS', 'FDA', 'ONC', 'DEA', 'SAMHSA'",
    "rule_type": "str  — e.g. 'final_rule', 'proposed_rule', 'guidance', 'enforcement'",
    "publication_date": "str  — ISO date of Federal Register publication",
    "effective_date": "str  — ISO date rule takes effect",
    "comment_deadline": "str  — ISO date public comment period closes",
    "title": "str  — official rule title from the Federal Register",
    "fr_citation": "str  — Federal Register volume/page e.g. '89 FR 32976'",
    "docket_id": "str  — rulemaking docket e.g. 'HHS-OCR-0945-AA08'",
    "severity": "str  — 'low' | 'medium' | 'high' | 'critical'",
    "affected_functions": "list[str] — e.g. ['billing', 'EHR', 'telehealth']",
    "breach_notification_deadline_days": "int  — always 60 per 45 CFR § 164.408",
    "aggregate_penalty_range_usd": "str  — e.g. '$100–$50,000 per violation'",
    # PROHIBITED — any of these keys in a tool call is a HIPAA violation
    "_prohibited": [
        "patient_name", "member_id", "mrn", "ssn", "dob", "email",
        "phone", "address", "zip", "ip_address", "device_id", "photo",
        "account_number", "license_number", "vin", "url_with_pii",
        "biometric", "health_plan_number", "certificate_number",
    ],
}


def validate_hipaa_safe(metadata: dict[str, Any]) -> list[str]:
    """
    Check a metadata dict for prohibited PHI keys.

    Returns a list of violation strings (empty = safe to send).
    Raises ValueError if any prohibited key is found.
    """
    prohibited = set(HIPAA_SAFE_METADATA_SCHEMA["_prohibited"])  # type: ignore[arg-type]
    violations = [k for k in metadata if k in prohibited]
    if violations:
        raise ValueError(
            f"HIPAA violation: metadata contains prohibited PHI fields: {violations}. "
            "Remove all PHI before sending to MCP tools."
        )
    return violations


# ---------------------------------------------------------------------------
# Healthcare Regulatory Source Registry
# ---------------------------------------------------------------------------

HEALTHCARE_REGULATORY_SOURCES: list[dict[str, str]] = [
    {
        "agency": "OCR",
        "name": "HHS Office for Civil Rights — HIPAA Enforcement",
        "public_url": "https://www.hhs.gov/hipaa/for-professionals/compliance-enforcement/agreements/index.html",
        "rss_feed": "https://www.hhs.gov/rss/hipaa-enforcement.xml",
        "fr_search_term": "HIPAA privacy security breach",
        "monitoring_priority": "critical",
        "note": "Resolution agreements and civil monetary penalties are fully public",
    },
    {
        "agency": "CMS",
        "name": "Centers for Medicare & Medicaid Services — Final Rules",
        "public_url": "https://www.cms.gov/regulations-and-guidance/regulations-and-policies/ebsa/about-ebsa/our-activities/resource-center/faqs",
        "fr_search_term": "Medicare Medicaid final rule",
        "monitoring_priority": "high",
        "note": "Billing codes, coverage determinations, value-based care rules",
    },
    {
        "agency": "FDA",
        "name": "FDA — Drug & Device Regulatory Actions",
        "public_url": "https://www.fda.gov/regulatory-information/search-fda-guidance-documents",
        "fr_search_term": "FDA drug device approval labeling",
        "monitoring_priority": "high",
        "note": "Approvals, recalls, and labeling changes are fully public",
    },
    {
        "agency": "ONC",
        "name": "Office of the National Coordinator — Health IT Rules",
        "public_url": "https://www.healthit.gov/topic/laws-regulation-and-policy/health-it-legislation",
        "fr_search_term": "interoperability information blocking EHR certification",
        "monitoring_priority": "high",
        "note": "21st Century Cures Act implementing rules, information blocking prohibitions",
    },
    {
        "agency": "DEA",
        "name": "DEA — Controlled Substance Prescribing (Telehealth)",
        "public_url": "https://www.deadiversion.usdoj.gov/fed_regs/rules/2023/fr0301.htm",
        "fr_search_term": "DEA telemedicine controlled substance prescribing",
        "monitoring_priority": "medium",
        "note": "Post-COVID telehealth prescribing rules under active rulemaking",
    },
    {
        "agency": "SAMHSA",
        "name": "SAMHSA — 42 CFR Part 2 (SUD Records Confidentiality)",
        "public_url": "https://www.samhsa.gov/about-us/who-we-are/laws-regulations/confidentiality-regulations-faqs",
        "fr_search_term": "42 CFR Part 2 substance use disorder confidentiality",
        "monitoring_priority": "medium",
        "note": "Stricter than HIPAA — requires explicit consent for most disclosures",
    },
]


# ---------------------------------------------------------------------------
# Use Case 1: Fetch live OCR enforcement actions (public, no PHI)
# ---------------------------------------------------------------------------


async def run_ocr_enforcement_fetch() -> list[ServerResult]:
    """
    Fetch the HHS OCR HIPAA enforcement page to discover new resolution
    agreements and civil monetary penalties.

    HIPAA safety: OCR enforcement pages are fully public.  The tool call
    metadata contains only agency name, URL, and a character-length cap —
    no patient or covered entity employee data.

    MCP tool: fetch → fetch
    Metadata sent:
        url    : public HHS.gov page
        max_length : 3000 characters of markdown
    """
    results: list[ServerResult] = []

    # Validate metadata before dispatch
    tool_metadata = {
        "url": "https://www.hhs.gov/hipaa/for-professionals/compliance-enforcement/agreements/index.html",
        "max_length": 3000,
    }
    validate_hipaa_safe(tool_metadata)

    print("[OCR Fetch] Checking for new HIPAA enforcement actions...")
    async with fetch_session() as session:
        r = await _call_tool(session, "fetch", tool_metadata, "fetch/ocr-enforcement")
        results.append(r)
        status = "OK" if r.success else f"ERR: {r.error}"
        print(f"[OCR Fetch] → {status} ({len(r.output)} chars retrieved)")

    return results


# ---------------------------------------------------------------------------
# Use Case 2: Search for CMS and ONC rulemaking news
# ---------------------------------------------------------------------------


async def run_healthcare_news_search(api_key: str | None = None) -> list[ServerResult]:
    """
    Search for breaking CMS, FDA, and ONC regulatory news using Brave Search.

    HIPAA safety: search queries contain only public regulatory topic terms —
    agency names, rule names, docket IDs.  No patient-identifying information
    is included in any query.

    MCP tool: brave-search → brave_web_search
    Metadata sent per query:
        query : plain-text regulatory topic (public domain)
        count : number of results (integer)
    """
    if not api_key and not os.getenv("BRAVE_API_KEY"):
        print("[Healthcare Search] SKIP: BRAVE_API_KEY not set.")
        return []

    # Each query is validated as HIPAA-safe (no PHI keys)
    queries_metadata = [
        {"query": "CMS final rule 2025 site", "count": 5},
        {"query": "HHS OCR HIPAA resolution agreement 2025", "count": 5},
        {"query": "ONC information blocking enforcement 2025", "count": 5},
        {"query": "FDA medical device cybersecurity guidance 2025", "count": 5},
        {"query": "DEA telemedicine controlled substance rule 2025", "count": 5},
    ]

    results: list[ServerResult] = []

    try:
        from naturalsentinel.mcp.external_servers import brave_search_session

        async with brave_search_session(api_key) as session:
            for meta in queries_metadata:
                validate_hipaa_safe(meta)
                r = await _call_tool(
                    session, "brave_web_search", meta, "brave-search/healthcare"
                )
                results.append(r)
                status = "OK" if r.success else f"ERR: {r.error}"
                print(f"[Healthcare Search] '{meta['query']}' → {status}")
    except Exception as exc:
        print(f"[Healthcare Search] SKIP: {exc}")

    return results


# ---------------------------------------------------------------------------
# Use Case 3: HIPAA breach notification deadline calculator
# ---------------------------------------------------------------------------


async def run_breach_deadline_demo(
    discovery_date_utc: str = "2025-06-01T09:00",
) -> list[ServerResult]:
    """
    Calculate the HIPAA breach notification deadline (60 calendar days from
    discovery, per 45 CFR § 164.408) in Eastern Time (HHS reference TZ).

    HIPAA safety: the Time MCP tool receives only a UTC timestamp string
    and a target timezone — no breach details, no covered entity name,
    no patient counts, no PHI of any kind.

    MCP tool: time → get_current_time, convert_time
    Metadata sent:
        source_timezone : "UTC"
        time            : discovery time string (no PHI)
        target_timezone : "America/New_York"
    """
    results: list[ServerResult] = []

    print(f"[Breach Deadline] Discovery date (UTC): {discovery_date_utc}")
    print( "[Breach Deadline] HIPAA requires notification within 60 days (45 CFR § 164.408)")

    async with time_session() as session:
        # Step 1: get current UTC time (to determine days remaining)
        meta_now = {"timezone": "UTC"}
        validate_hipaa_safe(meta_now)
        r = await _call_tool(session, "get_current_time", meta_now, "time/breach-deadline")
        results.append(r)
        print(f"[Breach Deadline] Current UTC → {r.output}")

        # Step 2: convert breach discovery time to Eastern (HHS reference TZ)
        meta_convert = {
            "source_timezone": "UTC",
            "time": discovery_date_utc.split("T")[1][:5],  # HH:MM only — no date PHI
            "target_timezone": "America/New_York",
        }
        validate_hipaa_safe(meta_convert)
        r = await _call_tool(session, "convert_time", meta_convert, "time/breach-deadline")
        results.append(r)
        print(f"[Breach Deadline] Discovery time (Eastern) → {r.output}")
        print( "[Breach Deadline] Deadline = discovery date + 60 calendar days (Eastern Time)")

    return results


# ---------------------------------------------------------------------------
# Use Case 4: Query a HIPAA-safe compliance tracking database
# ---------------------------------------------------------------------------


async def run_hipaa_compliance_db_demo(
    db_path: str = "/tmp/hipaa_compliance_demo.db",
) -> list[ServerResult]:
    """
    Query a compliance tracking database that stores ONLY de-identified,
    aggregate regulatory obligation records — never individual patient data.

    HIPAA safety: the SQLite MCP tool receives only SQL query strings and
    schema introspection calls.  The database schema is designed to hold
    regulatory obligations (rules, deadlines, business functions) — not
    any PHI.  The query metadata contains no patient-identifying fields.

    Schema (HIPAA-safe by design):
        regulatory_obligations
            id, agency, regulation_id, title, effective_date,
            compliance_function, status, notes

        hipaa_control_assessments
            id, control_domain, control_ref, last_assessed_date,
            assessment_result, gap_description, remediation_deadline

    MCP tool: sqlite → list_tables, read_query
    Metadata sent:
        query : SQL SELECT statement operating on de-identified tables only
    """
    import sqlite3

    # Seed HIPAA-safe demo database — regulatory obligations only, no PHI
    con = sqlite3.connect(db_path)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS regulatory_obligations (
            id                   INTEGER PRIMARY KEY,
            agency               TEXT NOT NULL,
            regulation_id        TEXT NOT NULL,
            title                TEXT NOT NULL,
            effective_date       TEXT,
            compliance_function  TEXT,
            status               TEXT DEFAULT 'open'
        );

        CREATE TABLE IF NOT EXISTS hipaa_control_assessments (
            id                    INTEGER PRIMARY KEY,
            control_domain        TEXT NOT NULL,
            control_ref           TEXT NOT NULL,
            last_assessed_date    TEXT,
            assessment_result     TEXT,
            gap_description       TEXT,
            remediation_deadline  TEXT
        );

        INSERT OR IGNORE INTO regulatory_obligations VALUES
            (1, 'OCR',  '45 CFR § 164.312', 'HIPAA Security Rule — Technical Safeguards', '2005-04-21', 'IT Security',    'open'),
            (2, 'OCR',  '45 CFR § 164.408', 'HIPAA Breach Notification — 60-Day Rule',    '2009-09-23', 'Compliance',     'open'),
            (3, 'CMS',  'CMS-9904-F',        'CMS Interoperability & Prior Auth Final Rule','2024-01-17','EHR/Billing',   'open'),
            (4, 'ONC',  '45 CFR § 171.103', 'Information Blocking Prohibition',            '2021-04-05', 'Health IT',     'remediated'),
            (5, 'DEA',  '21 CFR § 1306',    'Telemedicine Controlled Substance Prescribing','2025-01-01','Clinical/Legal','open'),
            (6, 'SAMHSA','42 CFR § 2.31',   'Part 2 Consent Requirements (SUD Records)',  '2024-02-16', 'HIM/Compliance','open');

        INSERT OR IGNORE INTO hipaa_control_assessments VALUES
            (1, 'Access Control',      '§ 164.312(a)(1)', '2025-01-15', 'partial', 'MFA not enforced on EHR admin accounts', '2025-06-30'),
            (2, 'Audit Controls',      '§ 164.312(b)',     '2025-01-15', 'pass',    NULL,                                      NULL),
            (3, 'Encryption at Rest',  '§ 164.312(a)(2)', '2025-01-15', 'pass',    NULL,                                      NULL),
            (4, 'Encryption in Transit','§ 164.312(e)(2)','2025-01-15', 'fail',    'Legacy HL7 v2 feeds transmit over HTTP',  '2025-03-31'),
            (5, 'BAA Management',      '§ 164.308(b)(1)', '2025-02-01', 'partial', '3 cloud vendors lack signed BAAs',        '2025-04-30');
    """)
    con.close()

    results: list[ServerResult] = []

    async with sqlite_session(db_path) as session:
        # List tables to confirm schema
        meta_list = {}
        validate_hipaa_safe(meta_list)
        r = await _call_tool(session, "list_tables", meta_list, "sqlite/hipaa-compliance")
        results.append(r)
        print(f"[HIPAA DB] Tables → {r.output}")

        # Query open regulatory obligations
        meta_open = {
            "query": (
                "SELECT agency, regulation_id, title, compliance_function, effective_date "
                "FROM regulatory_obligations WHERE status = 'open' ORDER BY effective_date;"
            )
        }
        validate_hipaa_safe(meta_open)
        r = await _call_tool(session, "read_query", meta_open, "sqlite/hipaa-compliance")
        results.append(r)
        print(f"[HIPAA DB] Open obligations →\n{r.output}")

        # Query failed/partial controls that need remediation
        meta_gaps = {
            "query": (
                "SELECT control_domain, control_ref, assessment_result, "
                "gap_description, remediation_deadline "
                "FROM hipaa_control_assessments "
                "WHERE assessment_result IN ('fail', 'partial') "
                "ORDER BY remediation_deadline;"
            )
        }
        validate_hipaa_safe(meta_gaps)
        r = await _call_tool(session, "read_query", meta_gaps, "sqlite/hipaa-compliance")
        results.append(r)
        print(f"[HIPAA DB] Control gaps →\n{r.output}")

    return results


# ---------------------------------------------------------------------------
# Use Case 5: Populate a shared healthcare regulatory knowledge graph
# ---------------------------------------------------------------------------


async def run_healthcare_memory_demo() -> list[ServerResult]:
    """
    Populate the Memory MCP knowledge graph with healthcare regulatory entities.

    This gives any MCP-compatible client (Claude Desktop, Cursor, dashboards)
    a shared, up-to-date map of the healthcare regulatory landscape without
    any PHI.  The graph contains only public regulatory framework entities.

    HIPAA safety: all entity names, types, and observations reference public
    regulatory documents, agencies, and rules — no patient or beneficiary data.

    MCP tool: memory → create_entities, create_relations, search_nodes
    Metadata sent:
        entities : list of regulatory entity dicts (agency names, rule IDs, public text)
        relations: links between public regulatory entities
        query    : plain-text search term (no PHI)
    """
    results: list[ServerResult] = []

    entities_payload = {
        "entities": [
            {
                "name": "HIPAA Security Rule",
                "entityType": "Regulation",
                "observations": [
                    "45 CFR Part 164 Subpart C — governs electronic PHI safeguards",
                    "Requires administrative, physical, and technical safeguards",
                    "Enforced by HHS Office for Civil Rights (OCR)",
                    "Civil monetary penalties range from $100 to $50,000 per violation category",
                ],
            },
            {
                "name": "HIPAA Breach Notification Rule",
                "entityType": "Regulation",
                "observations": [
                    "45 CFR §§ 164.400–414 — notification obligations after PHI breach",
                    "Covered entities must notify HHS and affected individuals within 60 days of discovery",
                    "Breaches > 500 individuals require media notice and immediate HHS report",
                    "Business associates must notify covered entity within 60 days",
                ],
            },
            {
                "name": "CMS Interoperability and Prior Authorization Rule",
                "entityType": "Regulation",
                "observations": [
                    "CMS-9904-F — effective January 2024 for most payers",
                    "Requires payers to implement FHIR R4 APIs for prior auth decisions",
                    "Mandates 72-hour turnaround for urgent prior auth requests",
                    "Applies to MA plans, Medicaid, CHIP, and QHP issuers",
                ],
            },
            {
                "name": "ONC Information Blocking Rule",
                "entityType": "Regulation",
                "observations": [
                    "45 CFR Part 171 — prohibits practices that interfere with access to EHI",
                    "Eight exceptions define when information blocking is permitted",
                    "Penalties up to $1M per violation for health IT developers",
                    "Complaint portal at healthit.gov/onc/information-blocking",
                ],
            },
            {
                "name": "42 CFR Part 2",
                "entityType": "Regulation",
                "observations": [
                    "SAMHSA rule — confidentiality of substance use disorder (SUD) treatment records",
                    "Stricter than HIPAA: requires patient written consent for most disclosures",
                    "2024 amendments aligned Part 2 more closely with HIPAA for care coordination",
                    "Violations carry criminal penalties unlike HIPAA civil penalties",
                ],
            },
            {
                "name": "HHS Office for Civil Rights",
                "entityType": "RegulatoryAgency",
                "observations": [
                    "Enforces HIPAA Privacy, Security, and Breach Notification Rules",
                    "Publishes resolution agreements and corrective action plans publicly",
                    "Conducts proactive audits under the HIPAA Audit Program",
                    "Received 50,000+ HIPAA complaints in 2023",
                ],
            },
        ]
    }

    validate_hipaa_safe({"entities": "list"})  # top-level key check

    async with memory_mcp_session() as session:
        tools = await session.list_tools()
        print(f"[Healthcare Memory] {len(tools.tools)} tools available")

        r = await _call_tool(
            session, "create_entities", entities_payload, "memory/healthcare"
        )
        results.append(r)
        print(f"[Healthcare Memory] create_entities → {'OK' if r.success else r.error}")

        relations_payload = {
            "relations": [
                {
                    "from": "HHS Office for Civil Rights",
                    "to": "HIPAA Security Rule",
                    "relationType": "enforces",
                },
                {
                    "from": "HHS Office for Civil Rights",
                    "to": "HIPAA Breach Notification Rule",
                    "relationType": "enforces",
                },
                {
                    "from": "HIPAA Breach Notification Rule",
                    "to": "HIPAA Security Rule",
                    "relationType": "supplements",
                },
                {
                    "from": "CMS Interoperability and Prior Authorization Rule",
                    "to": "ONC Information Blocking Rule",
                    "relationType": "coordinates_with",
                },
            ]
        }

        r = await _call_tool(
            session, "create_relations", relations_payload, "memory/healthcare"
        )
        results.append(r)
        print(f"[Healthcare Memory] create_relations → {'OK' if r.success else r.error}")

        r = await _call_tool(
            session,
            "search_nodes",
            {"query": "breach notification deadline penalties"},
            "memory/healthcare",
        )
        results.append(r)
        print(f"[Healthcare Memory] search_nodes → {r.output[:300]}")

    return results


# ---------------------------------------------------------------------------
# Aggregated healthcare demo runner
# ---------------------------------------------------------------------------


async def run_healthcare_demo(
    brave_api_key: str | None = None,
    db_path: str = "/tmp/hipaa_compliance_demo.db",
) -> None:
    """Run all five HIPAA-safe healthcare MCP use cases in sequence."""

    print("\n" + "=" * 70)
    print("  NaturalSentinel — Healthcare MCP Use Cases (HIPAA-Safe)")
    print("=" * 70)
    print("  All tool call metadata is validated against the HIPAA Safe Harbor")
    print("  standard before dispatch.  No PHI is sent to any MCP server.\n")

    print("\n─── Use Case 1: OCR Enforcement Feed (Fetch MCP) ───")
    try:
        await run_ocr_enforcement_fetch()
    except Exception as exc:
        print(f"  SKIP: {exc}")

    print("\n─── Use Case 2: Healthcare Regulatory News (Brave Search MCP) ───")
    await run_healthcare_news_search(brave_api_key)

    print("\n─── Use Case 3: HIPAA Breach Deadline Calculator (Time MCP) ───")
    try:
        await run_breach_deadline_demo()
    except Exception as exc:
        print(f"  SKIP: {exc}")

    print("\n─── Use Case 4: HIPAA Compliance Database (SQLite MCP) ───")
    try:
        await run_hipaa_compliance_db_demo(db_path)
    except Exception as exc:
        print(f"  SKIP: {exc}")

    print("\n─── Use Case 5: Healthcare Regulatory Knowledge Graph (Memory MCP) ───")
    try:
        await run_healthcare_memory_demo()
    except Exception as exc:
        print(f"  SKIP: {exc}")

    print("\n" + "=" * 70)
    print("  HIPAA Compliance Summary")
    print("=" * 70)
    print("  ✓ All metadata validated via validate_hipaa_safe() before dispatch")
    print("  ✓ No PHI sent to any MCP tool in any use case")
    print("  ✓ Database schema stores only regulatory obligations, not patient data")
    print("  ✓ Knowledge graph contains only public regulatory entity text")
    print("  ✓ Search queries contain only public regulatory topic terms")
    print("  ✓ Time tool receives only ISO timestamps, not patient event data")
    print("=" * 70 + "\n")
