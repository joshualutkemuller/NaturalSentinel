"""
Memory + feedback demo — shows the learning loop.

    python examples/memory_feedback_demo.py
"""

from naturalsentinel import MemoryStore, MemoryType, MockProvider, RegulatoryMonitorAgent


def section(title):
    print(f"\n{'━' * 60}\n  {title}\n{'━' * 60}\n")


def main():
    memory = MemoryStore(":memory:")
    agent = RegulatoryMonitorAgent(
        provider=MockProvider(),
        memory=memory,
        state_path="/tmp/naturalsentinel_mem_state.json",
    )
    agent.reset_state()

    # Step 1: Initial scan
    section("STEP 1: First Scan")
    results = agent.run(since_days=90)
    print(f"  Analyzed {len(results)} filings")
    print(f"  Memory: {memory.count()} records, {memory.stats()['total_relations']} relations")

    # Step 2: Human feedback
    section("STEP 2: Human Feedback")
    feedbacks = [
        (
            "CFPB-2026-0228-B",
            "affected_business_lines",
            "6 lines",
            "6 lines + Student Loans + BNPL",
            "BNPL uses AI decisioning too",
        ),
        (
            "FED-2026-0305-C",
            "severity",
            "high",
            "critical",
            "We have $500M crypto custody exposure",
        ),
    ]
    for fid, field, old, new, reason in feedbacks:
        memory.record_feedback(fid, field, old, new, reason)
        print(f"  ✓ {fid}.{field}: {old} → {new}")

    print(f"\n  Precedents: {memory.count(MemoryType.PRECEDENT)}")

    # Step 3: Semantic recall
    section("STEP 3: Semantic Recall")
    queries = [
        "climate disclosure SEC",
        "AI credit bias CFPB",
        "crypto custody capital",
    ]
    for q in queries:
        results = memory.recall(q, top_k=2)
        print(f'  "{q}"')
        for r in results:
            print(f"    → [{r.memory_type.value}] {r.key}  (score: {r.relevance_score:.3f})")
        print()

    # Step 4: Context block
    section("STEP 4: Memory Context (what the LLM sees)")
    ctx = memory.build_context_block("sec", "new SEC proposed rule on cybersecurity reporting")
    print(ctx or "  (empty)")

    # Step 5: Entity graph
    section("STEP 5: Entity Graph")
    for entity in ["Regulation S-K", "NAAQS"]:
        rels = memory.get_related_entities(entity)
        print(f'  "{entity}" — {len(rels)} relations')
        for r in rels[:4]:
            other = r["target"] if r["source"] == entity else r["source"]
            print(f"    ─{r['relation']}→ {other}  (weight: {r['weight']})")
        print()

    memory.close()


if __name__ == "__main__":
    main()
