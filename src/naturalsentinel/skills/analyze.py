"""Skill: Analyze a single filing with LLM-powered impact assessment.

This skill wraps the core LLM call and enriches its output with:

* **Source citations** — the LLM quotes the verbatim passage that supports
  each extracted field (severity, change_type, compliance_deadline, etc.).
* **Decision trace** — a step-by-step pipeline log with timing and token
  usage per step.
* **Model provenance** — provider / model / version / prompt hash recorded
  alongside every trace step.
* **Escalation policy** — post-analysis check against configured thresholds
  (critical severity, low confidence, calibration drift, extraction drift).
* **Audit event** — ANALYSIS_COMPLETED or ANALYSIS_FAILED event emitted to
  the immutable audit_log table.
"""

from naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)
from naturalsentinel.fetchers import DOMAIN_BUSINESS_LINES
from naturalsentinel.governance.audit import AuditEvent, AuditEventType, AuditSeverity
from naturalsentinel.governance.policy import EscalationPolicy, FallbackPolicy
from naturalsentinel.lineage.citation import parse_citations
from naturalsentinel.lineage.provenance import ModelProvenance
from naturalsentinel.lineage.trace import DecisionTrace
from naturalsentinel.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from naturalsentinel.utils.parsing import parse_llm_json


class AnalyzeFilingSkill(Skill):
    metadata = SkillMetadata(
        name="analyze_filing",
        description=(
            "Send a single regulatory filing to the LLM for structured impact "
            "analysis. Returns severity, affected business lines, compliance "
            "deadlines, action items, confidence score, source citations, "
            "decision trace, model provenance, and escalation decisions. "
            "Optionally enriches the prompt with memory context if the "
            "build_context skill provides it."
        ),
        version="2.0.0",
        permissions=Permission.LLM_READ | Permission.LLM_WRITE,
        latency=LatencyClass.MODERATE,
        parameters=[
            SkillParameter(
                "filing",
                "dict",
                "Serialised RegulatoryFiling with id, title, domain, raw_text, etc.",
            ),
            SkillParameter(
                "memory_context",
                "str",
                "Pre-built memory context block to append to the prompt.",
                required=False,
                default="",
            ),
            SkillParameter(
                "calibration_ece",
                "float",
                "Latest ECE from the calibration report — used by escalation policy.",
                required=False,
                default=None,
            ),
            SkillParameter(
                "drift_detected",
                "bool",
                "Whether extraction drift was flagged in the latest eval run.",
                required=False,
                default=None,
            ),
        ],
        returns=(
            "dict — parsed impact assessment with severity, action_items, citations "
            "(field → source_passage), trace_id, provenance, and escalation_reasons."
        ),
        dependencies=["build_context"],
        max_token_budget=4096,
        cacheable=False,
        tags=["analysis", "llm", "core", "lineage", "governance"],
    )

    _escalation_policy = EscalationPolicy.default()
    _fallback_policy = FallbackPolicy.default()

    def execute(self, context: SkillContext) -> SkillResult:
        if context.llm is None:
            return SkillResult(
                skill_name=self.metadata.name,
                success=False,
                data=None,
                error="LLM access denied — this skill requires LLM_READ permission",
            )

        filing = context.params["filing"]
        memory_context = context.params.get("memory_context", "")
        calibration_ece = context.params.get("calibration_ece")
        drift_detected = context.params.get("drift_detected")
        filing_id = filing.get("id", "UNKNOWN")
        domain = filing.get("domain", "")
        source_url = filing.get("source_url", "")
        domain_lines = DOMAIN_BUSINESS_LINES.get(domain, [])

        # ── 1. Start decision trace ──────────────────────────────────────
        trace = DecisionTrace.start(filing_id=filing_id)

        # ── 2. Build prompt ──────────────────────────────────────────────
        with trace.step("build_prompt") as step:
            user_prompt = USER_PROMPT_TEMPLATE.format(
                filing_id=filing_id,
                domain=domain.upper(),
                title=filing.get("title", ""),
                published_date=filing.get("published_date", ""),
                source_url=source_url,
                raw_text=filing.get("raw_text", ""),
                business_lines=", ".join(domain_lines),
            )
            if memory_context:
                user_prompt += "\n" + memory_context
            step.output_summary = f"prompt={len(user_prompt)} chars"

        # ── 3. LLM inference ─────────────────────────────────────────────
        raw: str = ""
        with trace.step(
            "llm_inference", input_summary=f"prompt={len(user_prompt)} chars"
        ) as step:
            try:
                raw = context.llm.complete(SYSTEM_PROMPT, user_prompt, temperature=0.1)
            except Exception as exc:
                step.status = "error"
                step.notes = str(exc)
                # Emit ANALYSIS_FAILED audit event if memory is available
                self._emit_audit(
                    context,
                    AuditEventType.ANALYSIS_FAILED,
                    filing_id,
                    trace.trace_id,
                    payload={"error": str(exc)},
                    severity=AuditSeverity.WARNING,
                )
                return SkillResult(
                    skill_name=self.metadata.name,
                    success=False,
                    data=None,
                    error=f"LLM inference failed: {exc}",
                )

            prov = ModelProvenance.from_context(
                context,
                prompt_template=SYSTEM_PROMPT,
                skill_version=self.metadata.version,
            )
            step.provider = prov.provider
            step.model = prov.model
            step.model_version = prov.model_version
            step.token_usage = len(user_prompt) // 4 + len(raw) // 4
            step.output_summary = f"response={len(raw)} chars"

        # ── 4. Parse response ─────────────────────────────────────────────
        with trace.step(
            "parse_response", input_summary=f"raw={len(raw)} chars"
        ) as step:
            fallback = {
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
                "citations": {},
            }
            parsed = parse_llm_json(raw, fallback=fallback)
            parsed["filing_id"] = filing_id
            parsed["domain"] = domain
            step.output_summary = (
                f"severity={parsed.get('severity')}, "
                f"confidence={parsed.get('confidence')}, "
                f"citations={len(parsed.get('citations', {}))}"
            )

        # ── 5. Extract citations ──────────────────────────────────────────
        with trace.step("extract_citations") as step:
            overall_conf = float(parsed.get("confidence", 0.0))
            bundle = parse_citations(
                parsed,
                filing_id=filing_id,
                source_url=source_url,
                overall_confidence=overall_conf,
            )
            parsed["citations"] = bundle.as_flat_dict()
            step.output_summary = f"{len(bundle.citations)} field citations"

        # ── 6. Escalation policy ──────────────────────────────────────────
        escalation_reasons: list[str] = []
        with trace.step("policy_check") as step:
            escalation_reasons = self._escalation_policy.evaluate(
                parsed,
                calibration_ece=calibration_ece,
                drift_detected=drift_detected,
            )
            parsed["escalation_reasons"] = escalation_reasons
            if escalation_reasons:
                step.status = "warning"
                step.notes = "; ".join(escalation_reasons)

        # ── 7. Record provenance on impact dict ───────────────────────────
        parsed["trace_id"] = trace.trace_id
        parsed["provenance"] = prov.to_dict()

        # ── 8. Finish trace and store ─────────────────────────────────────
        trace.finish()

        if context.memory:
            try:
                context.memory.store_decision_trace(trace)
                context.memory.store_citations(bundle)
            except Exception:
                pass  # Never fail an analysis due to lineage storage errors

        # ── 9. Emit audit event ───────────────────────────────────────────
        if escalation_reasons:
            self._emit_audit(
                context,
                AuditEventType.ESCALATION_TRIGGERED,
                filing_id,
                trace.trace_id,
                payload={
                    "reasons": escalation_reasons,
                    "severity": parsed.get("severity"),
                },
                severity=AuditSeverity.HIGH,
            )
        self._emit_audit(
            context,
            AuditEventType.ANALYSIS_COMPLETED,
            filing_id,
            trace.trace_id,
            payload={
                "severity": parsed.get("severity"),
                "confidence": parsed.get("confidence"),
                "n_citations": len(bundle.citations),
                "escalated": bool(escalation_reasons),
                "trace_duration_ms": trace.total_duration_ms,
            },
        )

        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data=parsed,
            token_usage=sum(s.token_usage for s in trace.steps),
            metadata={
                "filing_id": filing_id,
                "severity": parsed.get("severity"),
                "trace_id": trace.trace_id,
                "escalation_reasons": escalation_reasons,
                "n_citations": len(bundle.citations),
            },
        )

    # ── Helper ────────────────────────────────────────────────────────────

    @staticmethod
    def _emit_audit(
        context,
        event_type: AuditEventType,
        filing_id: str,
        trace_id: str,
        payload: dict | None = None,
        severity: AuditSeverity = AuditSeverity.INFO,
    ) -> None:
        if context.memory is None:
            return
        try:
            event = AuditEvent.create(
                event_type=event_type,
                filing_id=filing_id,
                trace_id=trace_id,
                payload=payload or {},
                severity=severity,
            )
            context.memory.emit_audit_event(event)
        except Exception:
            pass  # Never block analysis on audit write failures
