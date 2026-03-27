"""Decision trace — step-by-step record of the analysis pipeline execution.

A :class:`DecisionTrace` captures every step from filing ingestion through
LLM inference, response parsing, policy checks, and memory writes.  Together
with :class:`~naturalsentinel.lineage.provenance.ModelProvenance` it provides
a complete audit trail showing *how* each impact assessment was produced.

Usage::

    trace = DecisionTrace.start(filing_id="SEC-001")
    with trace.step("build_prompt") as s:
        prompt = build_prompt(filing)
        s.output_summary = f"prompt={len(prompt)} chars"

    with trace.step("llm_inference") as s:
        response = llm.complete(...)
        s.token_usage = 1234
        s.model = "claude-sonnet-4-6"

    trace.finish()
    memory.store_decision_trace(trace)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass
class TraceStep:
    """A single named step within a :class:`DecisionTrace`."""

    step_name: str
    started_at: str
    finished_at: str = ""
    duration_ms: float = 0.0
    status: str = "ok"  # "ok" | "warning" | "error"
    input_summary: str = ""
    output_summary: str = ""
    provider: str | None = None
    model: str | None = None
    model_version: str | None = None
    token_usage: int = 0
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class _StepContext:
    """Context-manager wrapper returned by :meth:`DecisionTrace.step`."""

    def __init__(self, step: TraceStep):
        self._step = step
        self._start: float = 0.0

    def __enter__(self) -> TraceStep:
        self._start = time.monotonic()
        return self._step

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (time.monotonic() - self._start) * 1000
        self._step.finished_at = datetime.utcnow().isoformat()
        self._step.duration_ms = round(elapsed, 2)
        if exc_type is not None:
            self._step.status = "error"
            self._step.notes = f"{exc_type.__name__}: {exc_val}"
        return False  # Do not suppress exceptions


@dataclass
class DecisionTrace:
    """Complete execution trace for a single filing analysis."""

    trace_id: str
    filing_id: str
    started_at: str
    steps: list[TraceStep] = field(default_factory=list)
    finished_at: str = ""
    total_duration_ms: float = 0.0
    total_tokens: int = 0
    overall_status: str = "ok"  # "ok" | "warning" | "error"
    _start_mono: float = field(default=0.0, repr=False, compare=False)

    def step(self, step_name: str, input_summary: str = "") -> _StepContext:
        """Return a context manager for a named pipeline step.

        Usage::

            with trace.step("llm_inference", input_summary="prompt=4k") as s:
                response = llm.complete(...)
                s.token_usage = 900
        """
        ts = TraceStep(
            step_name=step_name,
            started_at=datetime.utcnow().isoformat(),
            input_summary=input_summary,
        )
        self.steps.append(ts)
        return _StepContext(ts)

    def finish(self):
        """Finalise the trace — compute totals and set overall status."""
        self.finished_at = datetime.utcnow().isoformat()
        elapsed = (time.monotonic() - self._start_mono) * 1000
        self.total_duration_ms = round(elapsed, 2)
        self.total_tokens = sum(s.token_usage for s in self.steps)
        error_steps = [s for s in self.steps if s.status == "error"]
        warning_steps = [s for s in self.steps if s.status == "warning"]
        if error_steps:
            self.overall_status = "error"
        elif warning_steps:
            self.overall_status = "warning"
        else:
            self.overall_status = "ok"

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "filing_id": self.filing_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_duration_ms": self.total_duration_ms,
            "total_tokens": self.total_tokens,
            "overall_status": self.overall_status,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def start(cls, filing_id: str, trace_id: str | None = None) -> DecisionTrace:
        """Create and start a new trace."""
        t = cls(
            trace_id=trace_id or str(uuid.uuid4()),
            filing_id=filing_id,
            started_at=datetime.utcnow().isoformat(),
            _start_mono=time.monotonic(),
        )
        return t
