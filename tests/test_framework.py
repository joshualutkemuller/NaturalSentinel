"""Tests for the agent framework, skill registry, and built-in skills."""

import json
import os
import tempfile
import unittest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from naturalsentinel import (
    AgentRuntime, SecurityPolicy, Permission, SkillRegistry,
    Skill, SkillMetadata, SkillParameter, SkillContext, SkillResult,
    LatencyClass, MockProvider, MemoryStore, READONLY, STANDARD, FULL,
    ExecutionPlan, PlanStep,
)
from naturalsentinel.skills import ALL_SKILLS
from naturalsentinel.fetchers import fetch_filings
from naturalsentinel.fetchers.sample_data import SAMPLE_FILINGS
from naturalsentinel.agent import RegulatoryMonitorAgent


# ── FRAMEWORK ─────────────────────────────────────────────────────────────

class TestPermissions(unittest.TestCase):
    def test_flag_combinations(self):
        combo = Permission.LLM_READ | Permission.MEMORY_READ
        self.assertTrue(combo & Permission.LLM_READ)
        self.assertFalse(combo & Permission.FILE_WRITE)

    def test_readonly_preset(self):
        self.assertTrue(READONLY & Permission.LLM_READ)
        self.assertTrue(READONLY & Permission.MEMORY_READ)
        self.assertFalse(READONLY & Permission.MEMORY_WRITE)
        self.assertFalse(READONLY & Permission.FETCH_NETWORK)

    def test_standard_includes_write(self):
        self.assertTrue(STANDARD & Permission.MEMORY_WRITE)
        self.assertTrue(STANDARD & Permission.LLM_WRITE)
        self.assertFalse(STANDARD & Permission.FETCH_NETWORK)

    def test_full_includes_network(self):
        self.assertTrue(FULL & Permission.FETCH_NETWORK)
        self.assertTrue(FULL & Permission.FILE_WRITE)


class TestSecurityPolicy(unittest.TestCase):
    def test_default_policy_allows_standard(self):
        policy = SecurityPolicy()
        granted = policy.resolve_permissions(STANDARD)
        self.assertTrue(granted & Permission.LLM_READ)
        self.assertTrue(granted & Permission.MEMORY_WRITE)

    def test_deny_overrides_allow(self):
        policy = SecurityPolicy(allowed=FULL, denied=Permission.FETCH_NETWORK)
        granted = policy.resolve_permissions(FULL)
        self.assertFalse(granted & Permission.FETCH_NETWORK)
        self.assertTrue(granted & Permission.LLM_READ)

    def test_skill_deny_list(self):
        policy = SecurityPolicy(denied_skills={"dangerous_skill"})
        ok, _ = policy.check_skill("safe_skill")
        self.assertTrue(ok)
        ok, reason = policy.check_skill("dangerous_skill")
        self.assertFalse(ok)
        self.assertIn("denied", reason)

    def test_skill_allow_list(self):
        policy = SecurityPolicy(allowed_skills={"only_this"})
        ok, _ = policy.check_skill("only_this")
        self.assertTrue(ok)
        ok, _ = policy.check_skill("anything_else")
        self.assertFalse(ok)

    def test_budget_enforcement(self):
        policy = SecurityPolicy(max_llm_calls_per_run=2)
        policy.record_usage(llm_calls=2)
        ok, reason = policy.check_budget()
        self.assertFalse(ok)
        self.assertIn("exhausted", reason)

    def test_budget_reset(self):
        policy = SecurityPolicy(max_llm_calls_per_run=1)
        policy.record_usage(llm_calls=1)
        policy.reset_counters()
        ok, _ = policy.check_budget()
        self.assertTrue(ok)


class TestSkillRegistry(unittest.TestCase):
    def _make_dummy(self, name="dummy", perms=Permission.NONE, deps=None):
        class DummySkill(Skill):
            metadata = SkillMetadata(
                name=name, description="test", version="0.0.1",
                permissions=perms, latency=LatencyClass.INSTANT,
                parameters=[], returns="None",
                dependencies=deps or [], tags=["test"],
            )
            def execute(self, ctx):
                return SkillResult(skill_name=name, success=True, data="ok")
        return DummySkill()

    def test_register_and_get(self):
        reg = SkillRegistry()
        skill = self._make_dummy("my_skill")
        reg.register(skill)
        self.assertIsNotNone(reg.get("my_skill"))
        self.assertIsNone(reg.get("nonexistent"))

    def test_list_skills(self):
        reg = SkillRegistry()
        reg.register(self._make_dummy("a"))
        reg.register(self._make_dummy("b"))
        self.assertEqual(len(reg.list_skills()), 2)

    def test_find_by_tag(self):
        reg = SkillRegistry()
        reg.register(self._make_dummy("a"))
        self.assertEqual(len(reg.find_by_tag("test")), 1)
        self.assertEqual(len(reg.find_by_tag("nonexistent")), 0)

    def test_dependency_validation(self):
        reg = SkillRegistry()
        reg.register(self._make_dummy("child", deps=["parent"]))
        errors = reg.validate_dependencies()
        self.assertEqual(len(errors), 1)
        self.assertIn("parent", errors[0])

        reg.register(self._make_dummy("parent"))
        self.assertEqual(len(reg.validate_dependencies()), 0)

    def test_catalog(self):
        reg = SkillRegistry()
        reg.register(self._make_dummy("x"))
        cat = reg.catalog()
        self.assertEqual(len(cat), 1)
        self.assertEqual(cat[0]["name"], "x")


# ── RUNTIME ───────────────────────────────────────────────────────────────

class TestAgentRuntime(unittest.TestCase):
    def setUp(self):
        self.memory = MemoryStore(":memory:")
        self.tmpdir = tempfile.mkdtemp()
        self.runtime = AgentRuntime(
            provider=MockProvider(),
            memory=self.memory,
            state_path=os.path.join(self.tmpdir, "state.json"),
            policy=SecurityPolicy(allowed=FULL),
        )
        self.runtime.register_skills(*ALL_SKILLS)

    def tearDown(self):
        self.memory.close()

    def test_all_skills_registered(self):
        skills = self.runtime.registry.list_skills()
        self.assertGreaterEqual(len(skills), 9)
        names = {s.name for s in skills}
        self.assertIn("scan_cycle", names)
        self.assertIn("fetch_filings", names)
        self.assertIn("analyze_filing", names)

    def test_dependency_graph_valid(self):
        errors = self.runtime.registry.validate_dependencies()
        self.assertEqual(errors, [], f"Broken deps: {errors}")

    def test_unknown_skill(self):
        result = self.runtime.execute_skill("nonexistent", {})
        self.assertFalse(result.success)
        self.assertIn("Unknown", result.error)

    def test_policy_denied_skill(self):
        self.runtime.policy.denied_skills.add("fetch_filings")
        result = self.runtime.execute_skill("fetch_filings", {"since_days": 90})
        self.assertFalse(result.success)
        self.assertIn("denied", result.error)

    def test_missing_required_param(self):
        result = self.runtime.execute_skill("analyze_filing", {})  # missing 'filing'
        self.assertFalse(result.success)
        self.assertIn("Missing required parameter", result.error)

    def test_audit_log(self):
        self.runtime.execute_skill("fetch_filings", {"since_days": 90})
        self.assertGreaterEqual(len(self.runtime.audit.entries), 1)
        summary = self.runtime.audit.summary()
        self.assertGreaterEqual(summary["total_invocations"], 1)


class TestLegacyRuntimeParity(unittest.TestCase):
    def setUp(self):
        self.agent_memory = MemoryStore(":memory:")
        self.runtime_memory = MemoryStore(":memory:")
        self.tmpdir = tempfile.mkdtemp()

        self.agent = RegulatoryMonitorAgent(
            provider=MockProvider(),
            memory=self.agent_memory,
            state_path=os.path.join(self.tmpdir, "agent_state.json"),
        )
        self.runtime = AgentRuntime(
            provider=MockProvider(),
            memory=self.runtime_memory,
            state_path=os.path.join(self.tmpdir, "runtime_state.json"),
            policy=SecurityPolicy(allowed=FULL),
        )
        self.runtime.register_skills(*ALL_SKILLS)

    def tearDown(self):
        self.agent_memory.close()
        self.runtime_memory.close()

    def test_scan_cycle_matches_legacy_agent_outputs(self):
        agent_results = self.agent.run(since_days=90)
        runtime_result = self.runtime.execute_skill("scan_cycle", {"since_days": 90})

        self.assertTrue(runtime_result.success)

        agent_by_id = {r.filing.id: r for r in agent_results}
        runtime_by_id = {item["filing"]["id"]: item for item in runtime_result.data["results"]}

        self.assertEqual(set(agent_by_id), set(runtime_by_id))
        self.assertEqual(len(agent_results), runtime_result.data["stats"]["new_analyzed"])

        for filing_id, agent_result in agent_by_id.items():
            runtime_item = runtime_by_id[filing_id]
            self.assertEqual(runtime_item["impact"]["severity"], agent_result.impact.severity.value)
            self.assertEqual(runtime_item["impact"]["filing_id"], filing_id)

        from naturalsentinel.memory.types import MemoryType
        self.assertEqual(
            self.agent_memory.count(MemoryType.EPISODIC),
            self.runtime_memory.count(MemoryType.EPISODIC),
        )


class TestFrameworkInvariants(unittest.TestCase):
    def _make_filing(self, filing_id="SEC-2026-0312-A"):
        return {
            "id": filing_id,
            "title": "Climate",
            "domain": "sec",
            "published_date": "2026-03-10",
            "source_url": "https://x.com",
            "raw_text": "SEC climate disclosure rule text.",
        }

    def test_budget_exhaustion_is_audited(self):
        runtime = AgentRuntime(
            provider=MockProvider(),
            policy=SecurityPolicy(allowed=FULL, max_llm_calls_per_run=1),
        )
        runtime.register_skills(*ALL_SKILLS)

        first = runtime.execute_skill("analyze_filing", {"filing": self._make_filing()})
        second = runtime.execute_skill("analyze_filing", {"filing": self._make_filing("SEC-2026-0312-A-2")})

        self.assertTrue(first.success)
        self.assertFalse(second.success)
        self.assertIn("Budget exceeded", second.error)

        failures = runtime.audit.failures()
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0].skill_name, "analyze_filing")
        self.assertIn("Budget exceeded", failures[0].error)

    def test_dependency_failure_propagates_and_is_linked_in_audit(self):
        class FailingChildSkill(Skill):
            metadata = SkillMetadata(
                name="failing_child",
                description="Always fails",
                version="0.0.1",
                permissions=Permission.NONE,
                latency=LatencyClass.INSTANT,
                parameters=[],
                returns="None",
            )

            def execute(self, context):
                raise RuntimeError("child boom")

        class ParentSkill(Skill):
            metadata = SkillMetadata(
                name="parent_skill",
                description="Invokes child",
                version="0.0.1",
                permissions=Permission.NONE,
                latency=LatencyClass.INSTANT,
                parameters=[],
                returns="dict",
                dependencies=["failing_child"],
            )

            def execute(self, context):
                child = context.invoke_skill("failing_child", {})
                if not child.success:
                    return SkillResult(
                        skill_name="parent_skill",
                        success=False,
                        data=None,
                        error=f"Child failed: {child.error}",
                    )
                return SkillResult(skill_name="parent_skill", success=True, data={"child": child.data})

        runtime = AgentRuntime(policy=SecurityPolicy(allowed=FULL))
        runtime.register_skill(FailingChildSkill())
        runtime.register_skill(ParentSkill())

        result = runtime.execute_skill("parent_skill", {})

        self.assertFalse(result.success)
        self.assertIn("Child failed: RuntimeError: child boom", result.error)

        child_entries = runtime.audit.for_skill("failing_child")
        parent_entries = runtime.audit.for_skill("parent_skill")
        self.assertEqual(len(child_entries), 1)
        self.assertEqual(len(parent_entries), 1)
        self.assertEqual(child_entries[0].parent_invocation_id, parent_entries[0].invocation_id)
        self.assertFalse(child_entries[0].success)
        self.assertFalse(parent_entries[0].success)


class TestStableFixtureSubset(unittest.TestCase):
    FIXTURE_IDS = ["SEC-2026-0312-A", "CFPB-2026-0228-B"]

    def _subset_filings(self):
        return [f for f in SAMPLE_FILINGS if f["id"] in self.FIXTURE_IDS]

    def test_fixture_subset_exact_mock_severities(self):
        runtime = AgentRuntime(provider=MockProvider(), policy=SecurityPolicy(allowed=FULL))
        runtime.register_skills(*ALL_SKILLS)

        expected = {
            "SEC-2026-0312-A": "critical",
            "CFPB-2026-0228-B": "high",
        }

        for filing in self._subset_filings():
            result = runtime.execute_skill("analyze_filing", {"filing": filing})
            self.assertTrue(result.success)
            self.assertEqual(result.data["severity"], expected[filing["id"]])

    def test_fixture_subset_dedup_counts_are_exact(self):
        runtime = AgentRuntime(
            state_path=os.path.join(tempfile.mkdtemp(), "subset_state.json"),
            policy=SecurityPolicy(allowed=FULL),
        )
        runtime.register_skills(*ALL_SKILLS)

        subset = [{"id": filing["id"]} for filing in self._subset_filings()]
        first = runtime.execute_skill("detect_duplicates", {"filings": subset, "mark_seen": True})
        second = runtime.execute_skill("detect_duplicates", {"filings": subset, "mark_seen": True})

        self.assertEqual(len(first.data["new_filings"]), 2)
        self.assertEqual(first.data["duplicates_skipped"], 0)
        self.assertEqual(len(second.data["new_filings"]), 0)
        self.assertEqual(second.data["duplicates_skipped"], 2)


# ── INDIVIDUAL SKILLS ─────────────────────────────────────────────────────

class TestFetchFilingsSkill(unittest.TestCase):
    def setUp(self):
        self.runtime = AgentRuntime(policy=SecurityPolicy(allowed=FULL))
        self.runtime.register_skills(*ALL_SKILLS)

    def test_fetch_all(self):
        result = self.runtime.execute_skill("fetch_filings", {"since_days": 365})
        self.assertTrue(result.success)
        self.assertEqual(len(result.data), len(SAMPLE_FILINGS))

    def test_fetch_filtered(self):
        result = self.runtime.execute_skill("fetch_filings", {"domains": ["sec"], "since_days": 365})
        self.assertTrue(result.success)
        self.assertTrue(all(f["domain"] == "sec" for f in result.data))

    def test_cacheable(self):
        r1 = self.runtime.execute_skill("fetch_filings", {"since_days": 365})
        r2 = self.runtime.execute_skill("fetch_filings", {"since_days": 365})
        self.assertTrue(r2.metadata.get("cached", False))


class TestAnalyzeFilingSkill(unittest.TestCase):
    def setUp(self):
        self.runtime = AgentRuntime(
            provider=MockProvider(),
            policy=SecurityPolicy(allowed=FULL),
        )
        self.runtime.register_skills(*ALL_SKILLS)

    def test_analyze(self):
        filing = {
            "id": "SEC-2026-0312-A", "title": "Climate", "domain": "sec",
            "published_date": "2026-03-10", "source_url": "https://x.com",
            "raw_text": "SEC climate disclosure rule text.",
        }
        result = self.runtime.execute_skill("analyze_filing", {"filing": filing})
        self.assertTrue(result.success)
        self.assertEqual(result.data["severity"], "critical")
        self.assertGreater(result.token_usage, 0)

    def test_denied_without_llm(self):
        runtime = AgentRuntime(provider=None, policy=SecurityPolicy(allowed=FULL))
        runtime.register_skills(*ALL_SKILLS)
        result = runtime.execute_skill("analyze_filing", {"filing": {"id": "X", "domain": "sec", "raw_text": "t", "title": "t", "published_date": "2026-01-01", "source_url": "x"}})
        self.assertFalse(result.success)
        self.assertIn("LLM access denied", result.error)


class TestMemorySkills(unittest.TestCase):
    def setUp(self):
        self.memory = MemoryStore(":memory:")
        self.runtime = AgentRuntime(memory=self.memory, policy=SecurityPolicy(allowed=FULL))
        self.runtime.register_skills(*ALL_SKILLS)

    def tearDown(self):
        self.memory.close()

    def test_store_and_recall(self):
        store_r = self.runtime.execute_skill("store_memory", {
            "filing_id": "T-001",
            "filing": {"title": "Climate SEC Test", "domain": "sec"},
            "impact": {"severity": "high", "affected_business_lines": ["ESG"], "affected_regulations": ["Reg S-K"], "risk_summary": "Risk"},
        })
        self.assertTrue(store_r.success)

        recall_r = self.runtime.execute_skill("recall_memory", {"query": "climate SEC"})
        self.assertTrue(recall_r.success)
        self.assertGreater(len(recall_r.data), 0)

    def test_feedback(self):
        self.runtime.execute_skill("store_memory", {
            "filing_id": "T-001", "filing": {"title": "A"}, "impact": {"severity": "low"},
        })
        fb = self.runtime.execute_skill("record_feedback", {
            "filing_id": "T-001", "field": "severity",
            "old_value": "low", "new_value": "high", "reason": "enforcement risk",
        })
        self.assertTrue(fb.success)

    def test_build_context(self):
        self.runtime.execute_skill("store_memory", {
            "filing_id": "SEC-001",
            "filing": {"id": "SEC-001", "title": "Climate Rule", "domain": "sec"},
            "impact": {"severity": "critical", "affected_business_lines": ["ESG"], "affected_regulations": [], "risk_summary": "Risk"},
        })
        ctx = self.runtime.execute_skill("build_context", {"domain": "sec", "filing_text": "climate disclosure"})
        self.assertTrue(ctx.success)
        self.assertIn("RELEVANT PAST ANALYSES", ctx.data)

    def test_denied_without_memory(self):
        runtime = AgentRuntime(memory=None, policy=SecurityPolicy(allowed=FULL))
        runtime.register_skills(*ALL_SKILLS)
        r = self.runtime.execute_skill("store_memory", {"filing_id": "X", "filing": {}, "impact": {}})
        # This should work since self.runtime HAS memory — test the other runtime
        r2 = runtime.execute_skill("recall_memory", {"query": "test"})
        self.assertFalse(r2.success)


class TestDedupSkill(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.runtime = AgentRuntime(
            state_path=os.path.join(self.tmpdir, "state.json"),
            policy=SecurityPolicy(allowed=FULL),
        )
        self.runtime.register_skills(*ALL_SKILLS)

    def test_first_run_all_new(self):
        filings = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
        r = self.runtime.execute_skill("detect_duplicates", {"filings": filings})
        self.assertTrue(r.success)
        self.assertEqual(len(r.data["new_filings"]), 3)
        self.assertEqual(r.data["duplicates_skipped"], 0)

    def test_second_run_deduped(self):
        filings = [{"id": "A"}, {"id": "B"}]
        self.runtime.execute_skill("detect_duplicates", {"filings": filings})
        r2 = self.runtime.execute_skill("detect_duplicates", {"filings": filings})
        self.assertEqual(len(r2.data["new_filings"]), 0)
        self.assertEqual(r2.data["duplicates_skipped"], 2)


class TestScanCycleSkill(unittest.TestCase):
    def setUp(self):
        self.memory = MemoryStore(":memory:")
        self.tmpdir = tempfile.mkdtemp()
        self.runtime = AgentRuntime(
            provider=MockProvider(),
            memory=self.memory,
            state_path=os.path.join(self.tmpdir, "state.json"),
            policy=SecurityPolicy(allowed=FULL),
        )
        self.runtime.register_skills(*ALL_SKILLS)

    def tearDown(self):
        self.memory.close()

    def test_full_cycle(self):
        result = self.runtime.execute_skill("scan_cycle", {"since_days": 90})
        self.assertTrue(result.success)
        stats = result.data["stats"]
        expected = len(fetch_filings(since_days=90))
        self.assertEqual(stats["total_fetched"], expected)
        self.assertEqual(stats["new_analyzed"], expected)
        self.assertGreater(result.token_usage, 0)

        # Memory should be populated
        from naturalsentinel.memory.types import MemoryType
        self.assertEqual(self.memory.count(MemoryType.EPISODIC), expected)

    def test_second_cycle_deduped(self):
        self.runtime.execute_skill("scan_cycle", {"since_days": 90})
        r2 = self.runtime.execute_skill("scan_cycle", {"since_days": 90})
        self.assertTrue(r2.success)
        self.assertEqual(r2.data["stats"].get("new_analyzed", r2.data["stats"].get("new", 0)), 0)

    def test_audit_trail(self):
        self.runtime.execute_skill("scan_cycle", {"since_days": 90})
        summary = self.runtime.audit.summary()
        # scan_cycle invokes: fetch + dedup + (build_context + analyze + store) * 6 = 20
        self.assertGreaterEqual(summary["total_invocations"], 20)
        self.assertEqual(summary["failures"], 0)
        self.assertIn("scan_cycle", summary["skills_used"])
        self.assertIn("fetch_filings", summary["skills_used"])

    def test_domain_filter(self):
        result = self.runtime.execute_skill("scan_cycle", {"domains": ["sec"], "since_days": 90})
        self.assertTrue(result.success)
        for r in result.data["results"]:
            if "error" not in r:
                self.assertEqual(r["filing"]["domain"], "sec")


class TestExecutionPlan(unittest.TestCase):
    def setUp(self):
        self.memory = MemoryStore(":memory:")
        self.runtime = AgentRuntime(
            provider=MockProvider(), memory=self.memory,
            state_path=os.path.join(tempfile.mkdtemp(), "state.json"),
            policy=SecurityPolicy(allowed=FULL),
        )
        self.runtime.register_skills(*ALL_SKILLS)

    def tearDown(self):
        self.memory.close()

    def test_multi_step_plan(self):
        plan = ExecutionPlan(
            goal="Scan and brief",
            steps=[
                PlanStep(skill_name="scan_cycle", params={"since_days": 90}),
                PlanStep(skill_name="generate_briefing", params={"audience": "board"}),
            ],
        )
        results = self.runtime.execute_plan(plan)
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].success)  # scan
        self.assertTrue(results[1].success)  # briefing


if __name__ == "__main__":
    unittest.main()
