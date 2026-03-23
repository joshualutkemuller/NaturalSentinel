"""
healthcare_hipaa_demo.py — HIPAA-Safe Healthcare MCP Use Cases
==============================================================

Demonstrates five NaturalSentinel use cases in healthcare settings, each
using MCP tool calls that contain ZERO Protected Health Information (PHI).

Use cases:
  1. OCR enforcement feed      — Fetch MCP → live HHS enforcement page
  2. Regulatory news discovery — Brave Search MCP → CMS/FDA/ONC headlines
  3. Breach deadline calc      — Time MCP → 60-day HIPAA notification window
  4. Compliance DB queries     — SQLite MCP → de-identified obligation tracking
  5. Regulatory knowledge graph— Memory MCP → shared healthcare entity graph

Prerequisites:
  pip install 'naturalsentinel[mcp]' mcp-server-sqlite mcp-server-time
  Node.js >= 18  (for fetch and memory MCP servers)

Run:
  python examples/healthcare_hipaa_demo.py
  python examples/healthcare_hipaa_demo.py --use-case breach-deadline
  python examples/healthcare_hipaa_demo.py --show-schema
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from naturalsentinel.mcp.healthcare_servers import (
    HEALTHCARE_REGULATORY_SOURCES,
    HIPAA_SAFE_METADATA_SCHEMA,
    run_breach_deadline_demo,
    run_healthcare_demo,
    run_healthcare_memory_demo,
    run_healthcare_news_search,
    run_hipaa_compliance_db_demo,
    run_ocr_enforcement_fetch,
)

USE_CASES = {
    "ocr-enforcement":  ("OCR Enforcement Feed (Fetch MCP)",           run_ocr_enforcement_fetch),
    "news":             ("Healthcare Regulatory News (Brave Search)",   run_healthcare_news_search),
    "breach-deadline":  ("HIPAA Breach Deadline Calculator (Time MCP)", run_breach_deadline_demo),
    "compliance-db":    ("HIPAA Compliance Database (SQLite MCP)",      run_hipaa_compliance_db_demo),
    "knowledge-graph":  ("Regulatory Knowledge Graph (Memory MCP)",     run_healthcare_memory_demo),
}


def print_hipaa_schema() -> None:
    print("\n" + "=" * 70)
    print("  HIPAA-Safe Metadata Schema")
    print("  (fields allowed in MCP tool call arguments)")
    print("=" * 70)
    prohibited = HIPAA_SAFE_METADATA_SCHEMA.pop("_prohibited")
    for key, desc in HIPAA_SAFE_METADATA_SCHEMA.items():
        print(f"  ✓  {key:<40} {desc}")
    print("\n  PROHIBITED keys (PHI — never send to any MCP tool):")
    for key in prohibited:
        print(f"  ✗  {key}")
    HIPAA_SAFE_METADATA_SCHEMA["_prohibited"] = prohibited
    print("=" * 70 + "\n")


def print_regulatory_sources() -> None:
    print("\n" + "=" * 70)
    print("  Healthcare Regulatory Sources Monitored")
    print("=" * 70)
    for src in HEALTHCARE_REGULATORY_SOURCES:
        print(f"\n  [{src['agency']}] {src['name']}")
        print(f"    Priority : {src['monitoring_priority'].upper()}")
        print(f"    Search   : \"{src['fr_search_term']}\"")
        print(f"    Note     : {src['note']}")
    print("=" * 70 + "\n")


async def main(use_case: str | None = None) -> None:
    if use_case:
        if use_case not in USE_CASES:
            print(f"Unknown use case '{use_case}'. Choose from: {list(USE_CASES)}")
            return
        label, fn = USE_CASES[use_case]
        print(f"\n{'=' * 70}")
        print(f"  {label}")
        print(f"{'=' * 70}\n")
        try:
            await fn()
        except Exception as exc:
            print(f"  SKIP: {exc}")
    else:
        await run_healthcare_demo(brave_api_key=os.getenv("BRAVE_API_KEY"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="HIPAA-safe healthcare MCP use cases for NaturalSentinel"
    )
    parser.add_argument(
        "--use-case",
        choices=list(USE_CASES),
        help="Run a single use case",
    )
    parser.add_argument(
        "--show-schema",
        action="store_true",
        help="Print the HIPAA-safe metadata schema and exit",
    )
    parser.add_argument(
        "--show-sources",
        action="store_true",
        help="Print the healthcare regulatory source registry and exit",
    )
    args = parser.parse_args()

    if args.show_schema:
        print_hipaa_schema()
        sys.exit(0)

    if args.show_sources:
        print_regulatory_sources()
        sys.exit(0)

    asyncio.run(main(use_case=args.use_case))
