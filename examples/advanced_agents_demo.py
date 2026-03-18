"""
Advanced Agents Demo — showcases the new intelligence skills and agents.

Demonstrates:
  1. AlertAgent              — scan + threshold-based alerting with trend analysis
  2. ComplianceTrackerAgent  — deadline calendar with markdown report export
  3. TrendAnalysisSkill      — regulatory escalation pattern detection
  4. CrossDomainCorrelationSkill — multi-agency overlap identification
  5. ExportReportSkill       — rendering a CSV compliance register

No API keys needed — uses MockProvider throughout.

    PYTHONPATH=src python examples/advanced_agents_demo.py
"""

import sys
from naturalsentinel.providers import MockProvider
from naturalsentinel.memory import MemoryStore
from naturalsentinel.agent_framework import AgentRuntime
from naturalsentinel.skills import ALL_SKILLS
from naturalsentinel.agents import AlertAgent, ComplianceTrackerAgent


# ── Shared helpers ────────────────────────────────────────────────────────────

def _header(title: str) -> None:
    width = 68
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}\n")


def _section(label: str) -> None:
    print(f"  ── {label} {'─' * (60 - len(label))}")


def _build_runtime() -> AgentRuntime:
    """Build a pre-loaded runtime: scan sample data → 6 analyses in memory."""
    import os
    state_path = "/tmp/naturalsentinel_adv_state.json"
    # Remove stale state so all sample filings are treated as new each run
    try:
        os.remove(state_path)
    except FileNotFoundError:
        pass

    runtime = AgentRuntime(
        provider=MockProvider(),
        memory=MemoryStore(":memory:"),
        state_path=state_path,
    )
    for skill in ALL_SKILLS:
        runtime.register_skill(skill)

    print("  Priming memory with mock scan cycle…")
    result = runtime.execute_skill("scan_cycle", {"domains": [], "since_days": 90})
    if result.success:
        stats = result.data.get("stats", {})
        print(f"  Scanned {stats.get('total_fetched', 0)} filings, "
              f"analyzed {stats.get('new_analyzed', 0)} new.\n")
    else:
        print(f"  Scan failed: {result.error}\n", file=sys.stderr)
    return runtime


# ── Demo sections ─────────────────────────────────────────────────────────────

def demo_alert_agent(runtime: AgentRuntime) -> None:
    _header("1 / 5  AlertAgent — Threshold Monitoring + Trend Analysis")

    agent = AlertAgent(runtime)
    report = agent.check(threshold="medium", include_trends=True)

    alerts = report["alerts"]
    summary = report["summary"]

    _section("Alert Summary")
    print(f"  Threshold:       {summary.get('threshold', '?').upper()}")
    print(f"  Total inspected: {summary.get('total_inspected', 0)}")
    print(f"  Alerts raised:   {summary.get('alerts_raised', 0)}")
    print(f"  Severity dist:   {summary.get('severity_distribution', {})}")

    _section("Active Alerts (top 3)")
    for alert in alerts[:3]:
        tier = alert.get("urgency_tier", "?")
        print(f"  [{alert['severity'].upper()}] [{tier.upper()}] {alert['title']}")
        print(f"    Domain: {alert['domain']} | Deadline: {alert.get('deadline') or 'none'}")
        if alert.get("action_items"):
            print(f"    Action: {alert['action_items'][0]}")
        print()

    _section("Deduplicated Immediate Actions")
    for i, action in enumerate(report["immediate_actions"][:5], 1):
        print(f"  {i}. {action}")

    trends = report.get("trends")
    if trends:
        _section("Trend Signals")
        for sig in trends.get("trend_signals", [])[:4]:
            arrow = {"escalating": "▲", "stable": "→", "de-escalating": "▼"}.get(sig["signal"], "?")
            print(f"  {arrow} {sig['domain']}: {sig['signal']} "
                  f"(older={sig['avg_severity_older']}, recent={sig['avg_severity_recent']})")


def demo_compliance_tracker(runtime: AgentRuntime) -> None:
    _header("2 / 5  ComplianceTrackerAgent — Deadline Calendar")

    tracker = ComplianceTrackerAgent(runtime)
    result = tracker.run(look_ahead_days=60, export_format="markdown")

    cal = result["calendar"]
    summary = cal.get("summary", {})

    _section("Compliance Calendar")
    print(f"  Total analyzed:  {summary.get('total_analyzed', 0)}")
    print(f"  Overdue:         {summary.get('overdue_count', 0)}")
    print(f"  Due soon (≤60d): {summary.get('due_soon_count', 0)}")
    print(f"  Upcoming:        {summary.get('upcoming_count', 0)}")
    print(f"  No deadline:     {summary.get('no_deadline_count', 0)}")

    if cal.get("overdue"):
        _section("OVERDUE Items")
        for item in cal["overdue"]:
            print(f"  ! [{item['severity'].upper()}] {item['title']}")
            print(f"    Deadline: {item['deadline']} ({item['days_until']}d overdue)")

    if cal.get("due_soon"):
        _section("Due Soon")
        for item in cal["due_soon"][:3]:
            print(f"  > [{item['severity'].upper()}] {item['title']}")
            print(f"    Domain: {item['domain']} | In {item['days_until']}d")

    _section("Markdown Report (first 600 chars)")
    report_content = result["report"].get("content", "")
    print(report_content[:600])
    if len(report_content) > 600:
        print(f"  … ({len(report_content) - 600} more chars) …")


def demo_trend_analysis(runtime: AgentRuntime) -> None:
    _header("3 / 5  TrendAnalysisSkill — Regulatory Escalation Patterns")

    result = runtime.execute_skill("trend_analysis", {"limit": 50, "include_narrative": False})
    if not result.success:
        print(f"  Failed: {result.error}")
        return

    data = result.data
    stats = data.get("statistics", {})

    _section("Severity Distribution")
    for sev, count in stats.get("severity_distribution", {}).items():
        bar = "█" * count
        print(f"  {sev.upper():<10} {bar} ({count})")

    _section("Trend Signals")
    for sig in data.get("trend_signals", []):
        arrow = {"escalating": "▲", "stable": "→", "de-escalating": "▼"}.get(sig["signal"], "?")
        print(f"  {arrow} {sig['domain']:<6} {sig['signal']:<15} Δ={sig['delta']:+.2f}")


def demo_cross_domain(runtime: AgentRuntime) -> None:
    _header("4 / 5  CrossDomainCorrelationSkill — Multi-Agency Overlaps")

    result = runtime.execute_skill("cross_domain_correlation", {
        "min_domains": 2, "limit": 100, "include_assessment": False,
    })
    if not result.success:
        print(f"  Failed: {result.error}")
        return

    data = result.data
    summary = data.get("summary", {})

    _section("Summary")
    print(f"  Business lines checked: {summary.get('total_business_lines_checked', 0)}")
    print(f"  Intersections found:    {summary.get('intersections_found', 0)}")

    intersections = data.get("intersections", [])
    if intersections:
        _section("Top Intersections")
        for ix in intersections[:5]:
            domains_str = " × ".join(d.upper() for d in ix["domains"])
            print(f"  [{ix['max_severity'].upper()}] {ix['business_line']}")
            print(f"    Agencies: {domains_str} | Filings: {ix['filing_count']}")
    else:
        print("  No multi-agency overlaps found in current data set.")
        print("  (With more filings from real APIs, overlaps across SEC+CFPB+FED would appear here.)")


def demo_export_report(runtime: AgentRuntime) -> None:
    _header("5 / 5  ExportReportSkill — CSV Compliance Register")

    result = runtime.execute_skill("export_report", {
        "format": "csv", "limit": 10, "min_severity": "low",
    })
    if not result.success:
        print(f"  Failed: {result.error}")
        return

    data = result.data
    _section(f"CSV Export — {data['row_count']} rows")
    lines = data["content"].splitlines()
    for line in lines[:7]:
        print(f"  {line[:100]}")
    if len(lines) > 7:
        print(f"  … ({len(lines) - 7} more rows) …")

    # JSON sample
    json_result = runtime.execute_skill("export_report", {
        "format": "json", "limit": 2, "min_severity": "high",
    })
    if json_result.success:
        _section("JSON Export Sample (high+ severity)")
        import json as _json
        try:
            records = _json.loads(json_result.data["content"])
            for rec in records[:2]:
                print(f"  {rec.get('filing_id')} | {rec.get('severity', '').upper()} | {rec.get('title', '')[:55]}")
        except Exception:
            pass


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 68)
    print("  NaturalSentinel — Advanced Agents & Intelligence Skills Demo")
    print("=" * 68)

    runtime = _build_runtime()

    demo_alert_agent(runtime)
    demo_compliance_tracker(runtime)
    demo_trend_analysis(runtime)
    demo_cross_domain(runtime)
    demo_export_report(runtime)

    _header("Audit Summary — All Skill Invocations")
    audit = runtime.audit.summary()
    print(f"  Total invocations: {audit['total_invocations']}")
    print(f"  Success rate:      {audit['success_rate']:.0%}")
    print(f"  Total duration:    {audit['total_duration_ms']:.0f}ms")
    print(f"  Skills used:       {', '.join(sorted(audit['skills_used']))}")
    print()

    runtime.memory.close()


if __name__ == "__main__":
    main()
