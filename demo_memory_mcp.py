"""
demo_memory_mcp.py — Full demo of the Memory + MCP-enhanced Regulatory Monitor
================================================================================
Runs without any API keys (uses mock provider) and demonstrates:

  1. First scan cycle → populates episodic memory + entity graph
  2. Human feedback → creates precedent memories
  3. Second scan cycle → memory context injected into prompts
  4. Memory recall → semantic search across all memory types
  5. Entity graph traversal
  6. MCP standalone mode → JSON-RPC tool invocations
  7. Memory export/import
"""

import json
import logging
import os
import sys

# Ensure we can import from the same directory
sys.path.insert(0, os.path.dirname(__file__))

# Reuse the mock provider from the original demo
from demo import MockProvider

from agent import RegulatoryMonitorAgent
from mcp_server import StandaloneServer
from memory import MemoryStore, MemoryType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("MemoryMCPDemo")


def divider(title: str):
    print(f"\n{'━' * 70}")
    print(f"  {title}")
    print(f"{'━' * 70}\n")


def main():
    db_path = "/tmp/demo_regmon_memory.db"
    # Clean slate
    if os.path.exists(db_path):
        os.remove(db_path)

    # ──────────────────────────────────────────────────────────────────
    # STEP 1: Initialize with memory
    # ──────────────────────────────────────────────────────────────────
    divider("STEP 1: Initialize Agent with Persistent Memory")

    memory = MemoryStore(db_path)
    provider = MockProvider()
    agent = RegulatoryMonitorAgent(
        provider=provider,
        memory=memory,
        state_path="/tmp/demo_mcp_state.json",
    )
    agent.reset_state()

    print(f"  Provider: {provider.name()}")
    print(f"  Memory DB: {db_path}")
    print(f"  Initial memory stats: {json.dumps(memory.stats(), indent=4)}")

    # ──────────────────────────────────────────────────────────────────
    # STEP 2: First scan — populates episodic memory + entity graph
    # ──────────────────────────────────────────────────────────────────
    divider("STEP 2: First Scan Cycle (populates memory)")

    results = agent.run(since_days=90)
    print(f"  Analyzed {len(results)} filings")
    print("\n  Memory after scan:")
    stats = memory.stats()
    print(f"    Episodic memories:  {stats['by_type'].get('episodic', 0)}")
    print(f"    Entity relations:   {stats['total_relations']}")
    print(f"    Total memories:     {stats['total_memories']}")

    # ──────────────────────────────────────────────────────────────────
    # STEP 3: Record human feedback → creates precedent memories
    # ──────────────────────────────────────────────────────────────────
    divider("STEP 3: Record Human Feedback (teaches the agent)")

    feedbacks = [
        {
            "filing_id": "SEC-2026-0312-A",
            "field": "severity",
            "old_value": "critical",
            "new_value": "critical",
            "reason": "Confirmed correct — SEC climate rules carry real enforcement teeth.",
        },
        {
            "filing_id": "CFPB-2026-0228-B",
            "field": "affected_business_lines",
            "old_value": "Consumer Lending, Credit Cards, Auto Finance",
            "new_value": "Consumer Lending, Credit Cards, Auto Finance, Student Loans, BNPL",
            "reason": "Student loans and Buy Now Pay Later also use AI/ML decisioning.",
        },
        {
            "filing_id": "FED-2026-0305-C",
            "field": "severity",
            "old_value": "high",
            "new_value": "critical",
            "reason": "Our institution has $500M in crypto custody — this is existential.",
        },
    ]

    for fb in feedbacks:
        memory.record_feedback(**fb)
        print(f"  ✓ Feedback: {fb['filing_id']}.{fb['field']} → {fb['new_value'][:50]}…")

    stats = memory.stats()
    print("\n  Memory after feedback:")
    print(f"    Precedent memories: {stats['by_type'].get('precedent', 0)}")
    print(f"    Feedback log:       {stats['total_feedback']}")

    # ──────────────────────────────────────────────────────────────────
    # STEP 4: Demonstrate memory recall (semantic search)
    # ──────────────────────────────────────────────────────────────────
    divider("STEP 4: Memory Recall — Semantic Search")

    queries = [
        ("climate disclosure SEC ESG", None),
        ("AI credit model bias testing", None),
        ("crypto custody capital requirements", None),
        ("tariff semiconductor supply chain", None),
        ("severity correction", MemoryType.PRECEDENT),
    ]

    for query, mt in queries:
        label = f" [{mt.value}]" if mt else ""
        print(f'  Query: "{query}"{label}')
        results = memory.recall(query, top_k=2, memory_type=mt)
        for r in results:
            print(f"    → [{r.memory_type.value}] {r.key}  (relevance: {r.relevance_score:.3f})")
        print()

    # ──────────────────────────────────────────────────────────────────
    # STEP 5: Entity graph traversal
    # ──────────────────────────────────────────────────────────────────
    divider("STEP 5: Entity Relationship Graph")

    entities_to_explore = [
        "Regulation S-K",
        "Consumer Lending",
        "Basel III Framework",
    ]

    for entity in entities_to_explore:
        relations = memory.get_related_entities(entity)
        print(f'  Entity: "{entity}"  ({len(relations)} relations)')
        for rel in relations[:5]:
            src = rel["source"]
            tgt = rel["target"]
            rtype = rel["relation"]
            other = tgt if src == entity else src
            print(f"    ─{rtype}→ {other}  (weight: {rel['weight']})")
        print()

    # ──────────────────────────────────────────────────────────────────
    # STEP 6: Memory context injection (what the LLM sees)
    # ──────────────────────────────────────────────────────────────────
    divider("STEP 6: Memory Context Block (injected into LLM prompts)")

    context = memory.build_context_block(
        "sec", "New SEC proposed rule on cybersecurity incident reporting for public companies"
    )
    print(context if context else "  (no context available)")

    # ──────────────────────────────────────────────────────────────────
    # STEP 7: MCP standalone mode — simulated tool calls
    # ──────────────────────────────────────────────────────────────────
    divider("STEP 7: MCP Standalone Server — Simulated Tool Calls")

    # Temporarily redirect the global memory
    import mcp_server

    mcp_server._memory = memory

    standalone = StandaloneServer()

    mcp_requests = [
        {"method": "tools/list", "params": {}},
        {"method": "tools/call", "params": {"name": "get_memory_stats", "arguments": {}}},
        {
            "method": "tools/call",
            "params": {
                "name": "recall_memory",
                "arguments": {
                    "query": "climate disclosure",
                    "top_k": 2,
                },
            },
        },
        {
            "method": "tools/call",
            "params": {
                "name": "get_entity_relations",
                "arguments": {
                    "entity": "Consumer Lending",
                },
            },
        },
        {"method": "resources/list", "params": {}},
    ]

    for req in mcp_requests:
        print(f"  → {req['method']}", end="")
        if req["params"].get("name"):
            print(f" ({req['params']['name']})", end="")
        resp = standalone.handle_request(req)
        # Compact print
        resp_str = json.dumps(resp, default=str)
        if len(resp_str) > 200:
            resp_str = resp_str[:200] + "…"
        print(f"\n    ← {resp_str}\n")

    # ──────────────────────────────────────────────────────────────────
    # STEP 8: Export / Import
    # ──────────────────────────────────────────────────────────────────
    divider("STEP 8: Memory Export")

    export = memory.export_json()
    export_data = json.loads(export)
    print(
        f"  Exported {len(export_data['memories'])} memories, "
        f"{len(export_data['relations'])} relations, "
        f"{len(export_data['feedback'])} feedback entries"
    )
    print(f"  Export size: {len(export):,} bytes")

    # ──────────────────────────────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────────────────────────────
    divider("SUMMARY")

    final_stats = memory.stats()
    print(f"  Database:           {final_stats['db_path']}")
    print(f"  Total memories:     {final_stats['total_memories']}")
    print(f"    Episodic:         {final_stats['by_type'].get('episodic', 0)}")
    print(f"    Entity:           {final_stats['by_type'].get('entity', 0)}")
    print(f"    Precedent:        {final_stats['by_type'].get('precedent', 0)}")
    print(f"  Entity relations:   {final_stats['total_relations']}")
    print(f"  Feedback entries:   {final_stats['total_feedback']}")
    print(f"  Namespaces:         {list(final_stats['by_namespace'].keys())}")
    print()
    print("  The agent now has persistent memory that will improve")
    print("  future analyses through recalled context and learned corrections.")
    print()

    memory.close()


if __name__ == "__main__":
    main()
