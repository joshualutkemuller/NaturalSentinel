"""
Basic demo — runs the full pipeline with mock provider.
No API keys needed.

    python examples/basic_demo.py
"""

import json
from naturalsentinel import RegulatoryMonitorAgent, MockProvider, MemoryStore


def main():
    memory = MemoryStore(":memory:")
    agent = RegulatoryMonitorAgent(
        provider=MockProvider(),
        memory=memory,
        state_path="/tmp/naturalsentinel_basic_state.json",
    )
    agent.reset_state()

    results = agent.run(since_days=90)

    sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}

    print(f"\n{'=' * 66}")
    print(f"  Regulatory Monitor — {len(results)} filings analyzed")
    print(f"{'=' * 66}\n")

    for r in results:
        sev = r.impact.severity.value
        print(f"  {sev_icon.get(sev, '⚪')} [{sev.upper()}] {r.filing.title}")
        print(f"     {r.filing.domain.value.upper()} | {r.filing.change_type.value} | {r.filing.published_date}")
        print(f"     {r.impact.risk_summary[:100]}…")
        print(f"     Actions: {len(r.impact.action_items)} | Confidence: {r.impact.confidence:.0%}")
        if r.impact.compliance_deadline:
            print(f"     ⏰ Deadline: {r.impact.compliance_deadline}")
        print()

    print(f"  Memory: {memory.count()} episodic, {memory.stats()['total_relations']} relations\n")
    memory.close()


if __name__ == "__main__":
    main()
