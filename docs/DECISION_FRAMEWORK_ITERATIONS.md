# Decision Framework Iterations for NaturalSentinel

## Purpose

This document focuses on **decision-framework upgrades** rather than feature sprawl. The goal is to help NaturalSentinel evolve from a strong regulatory monitoring prototype into a system that better supports how a professional **Quant / Data Scientist in a large institutional environment such as State Street** would frame, compare, and defend decisions.

The core idea: move from **"what changed?"** and **"what might this impact?"** toward **"what is the evidence-weighted decision surface, what are the assumptions, and how should confidence evolve as new evidence arrives?"**

---

## Current strengths worth preserving

NaturalSentinel already has several strong foundations that are unusually aligned with good decision systems:

1. **Typed pipeline decomposition**
   - The five-stage classification → decomposition → extraction → validation → grounding pipeline is a strong architecture for auditability and for reducing monolithic-prompt failure modes.
2. **Permissioned skill framework**
   - Explicit permissions, declared dependencies, and audit logging create an excellent base for institutional controls.
3. **Persistent memory**
   - Episodic, entity, and precedent memories are the right primitives for institutional learning.
4. **Regime detection orientation**
   - The codebase already frames regime output as informative rather than prescriptive, which is a strong philosophical fit for decision support.
5. **Good modularity for vertical expansion**
   - The system is already structured in a way that can support portfolio, desk, or domain-specific downstream layers.

---

## What would elevate this professionally

The highest-leverage opportunity is to make NaturalSentinel more explicitly about **decision process quality**.

That means evolving the platform around six questions:

1. **What hypothesis is the system implicitly making?**
2. **What evidence supports or contradicts that hypothesis?**
3. **How strong is the evidence and from which sources?**
4. **What assumptions connect the filing to downstream business impact?**
5. **What scenarios would change the conclusion?**
6. **How should a user compare competing responses under uncertainty?**

---

## Priority iteration themes

### 1. Add an explicit decision object

**Status:** Complete as of 2026-03-18. NaturalSentinel now emits a first-class `DecisionFrame` alongside each `ImpactAssessment`.

Right now the system produces high-quality analytical artifacts, but the outputs are still mostly filing-centric. A more professional framing would introduce a first-class `DecisionFrame` or `DecisionContext` object that sits above analysis.

Suggested fields:

- `decision_id`
- `question`
- `scope`
- `time_horizon`
- `affected_entities`
- `candidate_actions`
- `constraints`
- `evidence_items`
- `assumptions`
- `counterarguments`
- `confidence`
- `expected_revisit_date`
- `owner`
- `audit_refs`

Why this matters:

- It separates **analysis artifacts** from **decision artifacts**.
- It gives a portfolio manager, risk lead, or model governance stakeholder something structured to review.
- It makes the system easier to integrate into downstream workflow, approvals, and challenge processes.

Professional upside:

- This is closer to how institutional investment, risk, and regulatory decisions are actually documented.

---

### 2. Introduce evidence weighting instead of flat retrieval

**Status:** Complete as of 2026-03-18. NaturalSentinel now builds a weighted `EvidenceLedger` from memory recall using source authority, recency, policy finality, jurisdiction relevance, business-line proximity, predictive usefulness, and contradiction risk.

Today, memory recall is useful, but recalled items are not yet obviously ranked by **decision relevance** in an institutional sense.

A next-level version should score evidence along dimensions such as:

- source authority
- recency
- policy finality (proposal vs final rule vs guidance vs enforcement)
- jurisdiction relevance
- business-line proximity
- historical predictive usefulness
- contradiction risk

This would support an `EvidenceLedger` pattern:

| Field | Purpose |
|---|---|
| `evidence_id` | stable identifier |
| `source_type` | filing, memory, feedback, analyst note |
| `supports` | which hypothesis/action it supports |
| `contradicts` | what it challenges |
| `strength_score` | weighted evidence score |
| `novelty_score` | whether it changes the prior view |
| `trace` | links to source spans, memory IDs, and timestamps |

Why this matters:

- Institutional users care less about raw retrieval and more about **why a conclusion should be believed**.
- This also sets up better challenge and review workflows.

---

### 3. Track priors, posteriors, and decision deltas

**Status:** Complete as of 2026-03-18. NaturalSentinel now maintains a belief-updating engine via the `BeliefTrackerSkill` (`track_belief`). Each filing observation updates a persisted `BeliefState` per (topic, domain) pair, recording `prior_confidence`, `posterior_confidence`, `delta_confidence`, `delta_drivers`, `stability_score`, and `reversal_risk`. The full observation history is stored in `belief_history` for audit and trend analysis. `BeliefState` is a first-class model and `MonitorResult` now carries a `belief_states` list.

A quant-facing system becomes much more compelling when it explicitly models **how beliefs change over time**.

Potential extension:

- Maintain a prior view on each regime / risk / obligation topic.
- Update that prior as new filings arrive.
- Store the delta between prior and posterior.
- Surface what specifically caused the change.

Useful output fields:

- `prior_confidence`
- `posterior_confidence`
- `delta_confidence`
- `delta_drivers`
- `stability_score`
- `reversal_risk`

Why this matters:

- It turns the system into a **belief-updating engine**, not just a filing summarizer.
- It aligns well with Bayesian, signal-processing, and regime-monitoring mindsets.
- It gives you a professional narrative around *decision evolution*, which is extremely valuable in risk committees and model review contexts.

---

### 4. Separate signal detection from action recommendation

One of the best strategic choices for this product is to remain disciplined about not prescribing business actions too early.

A stronger framework would formalize a layered stack:

1. **Observed signal layer** — what language was found?
2. **Interpretation layer** — what regime / obligation / impact is plausible?
3. **Decision layer** — what choices are now under consideration?
4. **Execution layer** — what operational workstreams would be triggered?

Why this matters:

- It reduces overreach.
- It makes the system more acceptable in tightly governed environments.
- It allows different stakeholders to engage at the correct layer.

This is especially valuable for State Street-like environments where separation between surveillance, interpretation, and policy/action may matter operationally.

---

### 5. Add scenario envelopes around each conclusion

The current design is good at producing a primary interpretation. A more decision-centric system should also state:

- what the base case is,
- what the upside / downside alternatives are,
- what evidence would invalidate the current view.

Suggested structure:

- `base_case`
- `alternative_cases`
- `invalidating_signals`
- `trigger_thresholds`
- `monitoring_metrics`

Why this matters:

- Professional users rarely want a single answer; they want a map of the uncertainty.
- It also turns the system into a monitoring platform for *decision triggers*, not just document changes.

---

### 6. Build a challenge-and-review loop

Institutional-grade systems improve materially when they can support formal challenge.

A high-value iteration would allow each conclusion to have:

- supporting rationale
- challenger rationale
- unresolved disagreements
- adjudication status
- reviewer sign-off metadata

Potential object:

- `ChallengeRecord`
  - `claim`
  - `supporting_evidence`
  - `challenge_evidence`
  - `adjudication_outcome`
  - `reviewer`
  - `reviewed_at`

Why this matters:

- This makes the system more credible for model risk, internal audit, and governance teams.
- It professionalizes the platform by embedding structured disagreement rather than assuming the first answer is the best answer.

---

## Concrete next-level iterations to explore

### A. Decision journal / investment committee mode

Create a mode where the output is not just an analysis report but a **decision memo** optimized for committee review.

Contents could include:

- executive framing of the issue
- evidence for and against a given interpretation
- confidence range
- comparable precedents from memory
- open questions
- next review trigger

This would be particularly strong for:

- risk committees
- model governance reviews
- regulatory interpretation committees
- cross-functional portfolio reviews

---

### B. Business impact propagation graph

You already have entity relations. The next step is a richer **propagation graph**:

`filing -> regulation -> policy interpretation -> process -> portfolio / desk -> KPI / risk metric`

Examples of downstream nodes:

- RWA
- leverage exposure
- liquidity buffers
- reporting burden
- collateral funding cost
- model validation queue
- data retention / lineage obligations

Why this matters:

- This bridges the gap between legal text and measurable operating or portfolio consequences.
- It also becomes the backbone for more disciplined what-if analysis.

---

### C. Decision quality scoring

Instead of only scoring filing severity, score the **quality of the decision frame** itself.

Candidate dimensions:

- evidence completeness
- contradiction coverage
- assumption transparency
- source grounding completeness
- precedent consistency
- reviewer agreement
- temporal freshness

This would produce a system where a user can ask not just **"How severe is this?"** but **"How decision-ready is this conclusion?"**

---

### D. Portfolio and benchmark awareness

To make this sharper for a quant / asset-servicing context, let the system reason over:

- affected issuer / sector / geography clusters
- benchmark exposures
- operational dependency maps
- data vendor dependencies
- model / process ownership maps

The key is not to jump to trade recommendations, but to improve **decision context** by connecting regulatory interpretation to actual exposure topology.

---

### E. Trigger-based monitoring instead of periodic summaries only

Move beyond static scan cycles toward **decision trigger monitoring**.

Examples:

- "Alert me when evidence for AI governance regime exceeds threshold and touches custody-servicing workflows."
- "Re-open this decision frame if a final rule replaces a proposal."
- "Escalate if contradictory guidance appears across agencies."

Why this matters:

- This turns the system into a standing decision infrastructure.
- It aligns with how professional monitoring teams manage issue escalation.

---

### F. Institutional feedback taxonomy

Current feedback recording is a great foundation, but professional environments benefit from feedback classes such as:

- extraction error
- severity disagreement
- scope disagreement
- unsupported assumption
- stale precedent
- missing counterfactual
- business-line mapping issue
- timing / deadline error

Why this matters:

- It gives better learning signals.
- It helps separate model weakness from ontology weakness from domain judgment disagreement.

---

## Suggested roadmap by phase

### Phase 1 — Strengthen decision framing

Explore:

- `DecisionFrame` schema
- evidence weighting / ledger
- explicit assumptions and counterarguments
- scenario envelopes

Outcome:

- Better institutional readability and reviewability.

### Phase 2 — Make decisions dynamic

Explore:

- priors / posteriors
- trigger monitoring
- confidence delta tracking
- revisit scheduling

Outcome:

- Better temporal intelligence and regime-awareness.

### Phase 3 — Make decisions governable

Explore:

- challenge workflows
- sign-off metadata
- decision quality score
- reviewer disagreement analytics

Outcome:

- More defensible outputs in professional settings.

### Phase 4 — Tie decisions to measurable business topology

Explore:

- propagation graph
- portfolio / entity exposure overlays
- process and KPI mapping
- benchmark-aware context

Outcome:

- More relevance for quant, risk, and operating-model stakeholders.

---

## What I would emphasize if your goal is professional differentiation

If the goal is to stand out professionally as a Quant / Data Scientist, the most differentiating path is not simply adding more agents or more skills.

It is building a system that can say:

1. **Here is the current institutional belief state.**
2. **Here is what changed it.**
3. **Here is the confidence and challenge record.**
4. **Here is what would invalidate the current view.**
5. **Here is how this propagates into exposure, workflow, and review cadence.**

That moves NaturalSentinel toward a genuinely sophisticated **decision intelligence system**.

---

## Practical framing principle

A useful north star for future iterations:

> Build the system so that every important conclusion can be reviewed as a sequence of:
>
> **signal -> evidence -> interpretation -> assumptions -> alternatives -> decision posture -> review trigger**

That framework is stronger, more defensible, and more professionally differentiated than a conventional recommendation engine.
