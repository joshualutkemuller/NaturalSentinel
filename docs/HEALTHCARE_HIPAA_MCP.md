# NaturalSentinel in Healthcare — HIPAA-Safe MCP Use Cases

NaturalSentinel monitors public regulatory filings from HHS, CMS, FDA, ONC,
DEA, and SAMHSA.  Because all source material is drawn from the Federal
Register and public agency websites, the system can deliver high-value
healthcare compliance intelligence without ever touching Protected Health
Information (PHI).

---

## HIPAA Compliance Boundary

The critical design principle is that **MCP tool calls receive only regulatory
metadata** — never patient, member, or beneficiary data.

### What CAN be sent to MCP tools

| Field | Example value |
|---|---|
| `regulation_id` | `"45 CFR § 164.400"` |
| `agency` | `"OCR"`, `"CMS"`, `"FDA"` |
| `rule_type` | `"final_rule"`, `"enforcement"` |
| `publication_date` | `"2025-03-01"` |
| `effective_date` | `"2025-06-01"` |
| `title` | `"HIPAA Security Rule Technical Safeguards"` |
| `fr_citation` | `"89 FR 32976"` |
| `docket_id` | `"HHS-OCR-0945-AA08"` |
| `severity` | `"high"` |
| `affected_functions` | `["billing", "EHR", "telehealth"]` |
| `aggregate_penalty_range_usd` | `"$100–$50,000 per violation"` |

### What must NEVER be sent (the 18 HIPAA Safe Harbor identifiers)

Names · geographic data below state level · dates linked to individuals ·
phone numbers · fax numbers · email addresses · SSNs · medical record numbers ·
health plan beneficiary numbers · account numbers · certificate/license numbers ·
VINs · device identifiers · URLs containing PII · IP addresses ·
biometric identifiers · full-face photographs · any other unique identifier

All tool call metadata is validated by `validate_hipaa_safe()` in
`src/naturalsentinel/mcp/healthcare_servers.py` before dispatch.

---

## Healthcare Regulatory Sources

| Agency | Focus | Monitoring Priority |
|---|---|---|
| **OCR** | HIPAA Privacy, Security & Breach enforcement | Critical |
| **CMS** | Medicare/Medicaid billing, coverage, prior auth | High |
| **FDA** | Drug/device approvals, recalls, labeling | High |
| **ONC** | Interoperability, information blocking, EHR certification | High |
| **DEA** | Controlled substance prescribing (telehealth rules) | Medium |
| **SAMHSA** | 42 CFR Part 2 — SUD records confidentiality | Medium |

All sources publish to the Federal Register or maintain public web pages.
No access to non-public payer, provider, or patient databases is required.

---

## Five MCP Use Cases

### 1. OCR Enforcement Feed — Fetch MCP

**Tool:** `fetch`
**Server:** `@modelcontextprotocol/server-fetch`

Retrieves the HHS OCR resolution agreements page to detect new civil monetary
penalties and corrective action plans.  OCR enforcement documents are fully
public — they identify covered entities by name but never include individual
patient records.

**Metadata sent to tool:**
```python
{
    "url": "https://www.hhs.gov/hipaa/for-professionals/compliance-enforcement/agreements/index.html",
    "max_length": 3000
}
```

**Value:** Alert compliance teams to new OCR enforcement patterns (e.g.,
surge in Right of Access violations) before the next audit cycle.

---

### 2. Healthcare Regulatory News — Brave Search MCP

**Tool:** `brave_web_search`
**Server:** `@modelcontextprotocol/server-brave-search`
**Env var:** `BRAVE_API_KEY`

Searches for breaking CMS, FDA, ONC, and DEA rulemaking news using
regulatory topic terms only — no patient-identifying information in queries.

**Sample queries (all HIPAA-safe):**
```python
{"query": "HHS OCR HIPAA resolution agreement 2025", "count": 5}
{"query": "CMS final rule 2025 prior authorization FHIR", "count": 5}
{"query": "ONC information blocking enforcement action 2025", "count": 5}
{"query": "FDA medical device cybersecurity guidance 2025",  "count": 5}
{"query": "DEA telemedicine controlled substance rule 2025", "count": 5}
```

**Value:** Surface guidance issued via press release or blog post before it
appears in the Federal Register — critical for fast-moving areas like
telehealth DEA rules and CMS prior auth FHIR deadlines.

---

### 3. HIPAA Breach Notification Deadline — Time MCP

**Tool:** `get_current_time`, `convert_time`
**Server:** `mcp-server-time`

Calculates the 60-day breach notification deadline (45 CFR § 164.408) in
Eastern Time (HHS reference timezone).  The tool receives only an ISO
timestamp and a timezone name — no breach details, entity names, or
patient counts.

**Metadata sent to tool:**
```python
# Step 1 — current UTC time
{"timezone": "UTC"}

# Step 2 — convert discovery time to Eastern
{
    "source_timezone": "UTC",
    "time": "09:00",          # HH:MM only — no date, no entity reference
    "target_timezone": "America/New_York"
}
```

**Value:** Ensures deadline calculations are correct regardless of the
server's local timezone.  The 60-day window is a hard legal requirement —
missing it triggers automatic HHS reporting obligations.

---

### 4. HIPAA Compliance Tracking Database — SQLite MCP

**Tool:** `list_tables`, `read_query`
**Server:** `mcp-server-sqlite`

Queries a compliance obligation database that stores **regulatory rules and
control assessment results only** — never individual patient records.

**HIPAA-safe schema:**

```sql
-- Regulatory obligations (rule IDs, deadlines, compliance functions)
CREATE TABLE regulatory_obligations (
    id                   INTEGER PRIMARY KEY,
    agency               TEXT,   -- "OCR", "CMS", "FDA"
    regulation_id        TEXT,   -- "45 CFR § 164.312"
    title                TEXT,
    effective_date       TEXT,
    compliance_function  TEXT,   -- "IT Security", "Billing", "HIM"
    status               TEXT    -- "open", "remediated"
);

-- Control assessments (framework references, gap descriptions, deadlines)
CREATE TABLE hipaa_control_assessments (
    id                    INTEGER PRIMARY KEY,
    control_domain        TEXT,   -- "Access Control", "Encryption"
    control_ref           TEXT,   -- "§ 164.312(a)(1)"
    last_assessed_date    TEXT,
    assessment_result     TEXT,   -- "pass", "fail", "partial"
    gap_description       TEXT,   -- technical description, no PHI
    remediation_deadline  TEXT
);
```

**Sample queries (HIPAA-safe):**
```sql
-- Open obligations sorted by effective date
SELECT agency, regulation_id, title, compliance_function
FROM regulatory_obligations
WHERE status = 'open'
ORDER BY effective_date;

-- Controls with gaps needing remediation
SELECT control_domain, control_ref, assessment_result,
       gap_description, remediation_deadline
FROM hipaa_control_assessments
WHERE assessment_result IN ('fail', 'partial')
ORDER BY remediation_deadline;
```

**Value:** Cross-references new regulatory impact assessments from
NaturalSentinel against existing open obligations — no ETL pipeline needed.

---

### 5. Healthcare Regulatory Knowledge Graph — Memory MCP

**Tool:** `create_entities`, `create_relations`, `search_nodes`
**Server:** `@modelcontextprotocol/server-memory`

Builds a shared knowledge graph of healthcare regulatory entities using only
public information: agency names, regulation citations, and Federal Register text.

**Entities created (all public regulatory text):**
- HIPAA Security Rule (45 CFR Part 164 Subpart C)
- HIPAA Breach Notification Rule (45 CFR §§ 164.400–414)
- CMS Interoperability & Prior Authorization Rule (CMS-9904-F)
- ONC Information Blocking Rule (45 CFR Part 171)
- 42 CFR Part 2 (SAMHSA SUD records confidentiality)
- HHS Office for Civil Rights (enforcement agency)

**Relations created:**
```
OCR  ──enforces──►  HIPAA Security Rule
OCR  ──enforces──►  HIPAA Breach Notification Rule
Breach Notification  ──supplements──►  Security Rule
CMS Interoperability  ──coordinates_with──►  ONC Information Blocking
```

**Value:** Any MCP-compatible tool (Claude Desktop, Cursor, internal
dashboards) can query this graph for regulatory context without re-fetching
the same public sources.  Complements NaturalSentinel's SQLite `memory.py`
with a portable, cross-client graph.

---

## Running the Demo

```bash
# Install Python MCP servers
pip install 'naturalsentinel[mcp]' mcp-server-sqlite mcp-server-time

# Run all five use cases
python examples/healthcare_hipaa_demo.py

# Run a single use case
python examples/healthcare_hipaa_demo.py --use-case breach-deadline
python examples/healthcare_hipaa_demo.py --use-case compliance-db

# Print the HIPAA-safe metadata schema
python examples/healthcare_hipaa_demo.py --show-schema

# Print the regulatory source registry
python examples/healthcare_hipaa_demo.py --show-sources
```

---

## What NaturalSentinel Does NOT Do in Healthcare

To maintain HIPAA compliance, NaturalSentinel is explicitly scoped to
public regulatory intelligence:

| Prohibited use | Why |
|---|---|
| Query EHR systems for patient records | PHI — requires BAA and access controls |
| Ingest payer claims data | PHI — individual health information |
| Store breach incident details with affected individual counts | PHI if < 500, reportable if > 500 |
| Send provider NPI numbers linked to individual patients | Could constitute PHI in context |
| Search for news about specific patients or plan members | PHI |

NaturalSentinel monitors the **rules** — not the records governed by them.
