"""Skill: Track prior/posterior belief evolution for regulatory topics.

Priority 3 of the Decision Framework Iterations.

Maintains a belief-updating engine that records how confidence in a specific
regulatory topic (regime, risk category, or obligation) changes as new filings
arrive.  Each invocation:

1. Reads the current belief state (prior) from memory.
2. Applies a smoothed Bayesian-style update to compute the posterior.
3. Derives delta_drivers, stability_score, and reversal_risk from the delta
   and the full observation history.
4. Persists the updated state and appends to the history log.
5. Returns a dict that maps cleanly onto the BeliefState dataclass.

Output fields
-------------
topic                 The subject being tracked (e.g. "prudential_capital_tightening")
domain                Regulatory domain namespace (e.g. "fed", "sec")
prior_confidence      Confidence before this filing (0.0–1.0)
posterior_confidence  Confidence after updating (0.0–1.0)
delta_confidence      posterior − prior  (can be negative)
delta_drivers         List[str] explaining what caused the change
stability_score       1.0 = perfectly stable; 0.0 = highly volatile
reversal_risk         0.0–1.0 probability the belief will flip in the next cycle
observation_count     Total number of observations recorded for this topic
last_filing_id        The filing that triggered this update
updated_at            ISO timestamp of the update
"""

import math
from datetime import datetime

from naturalsentinel.agent_framework import (
    LatencyClass,
    Permission,
    Skill,
    SkillContext,
    SkillMetadata,
    SkillParameter,
    SkillResult,
)

# ---------------------------------------------------------------------------
# Heuristic helpers
# ---------------------------------------------------------------------------


def _compute_delta_drivers(
    prior: float,
    posterior: float,
    delta: float,
    filing_id: str,
    evidence_summary: str,
    change_type: str,
) -> list[str]:
    """Produce human-readable explanations for a confidence delta."""
    drivers: list[str] = []

    abs_delta = abs(delta)
    if abs_delta < 0.02:
        drivers.append("Minimal shift — new evidence is consistent with the prior view")
    elif delta > 0:
        if delta >= 0.20:
            drivers.append(
                f"Strong positive update (+{delta:.2f}) — significant new supporting evidence"
            )
        else:
            drivers.append(
                f"Moderate positive update (+{delta:.2f}) — incremental corroborating signal"
            )
    else:
        if delta <= -0.20:
            drivers.append(
                f"Strong negative update ({delta:.2f}) — contradictory or de-escalatory evidence"
            )
        else:
            drivers.append(f"Moderate negative update ({delta:.2f}) — mixed or weakening signals")

    # Document-type finality signal
    if change_type in ("final_rule", "enforcement"):
        drivers.append(f"High-finality document type ({change_type}) narrows uncertainty")
    elif change_type == "proposed_rule":
        drivers.append("Proposed rule stage — uncertainty persists until finalisation")
    elif change_type in ("guidance", "notice"):
        drivers.append(f"Interpretive document ({change_type}) — moderate certainty, may evolve")

    # Prior position context
    if prior < 0.3 and delta > 0:
        drivers.append(
            f"Belief was previously weak (prior={prior:.2f}); "
            "this filing upgrades a low-confidence hypothesis"
        )
    elif prior > 0.7 and delta < -0.1:
        drivers.append(
            f"Strong prior view (prior={prior:.2f}) challenged — "
            "warrants close review of the new evidence"
        )

    if evidence_summary:
        drivers.append(f"Evidence summary: {evidence_summary[:200]}")

    if filing_id:
        drivers.append(f"Triggering filing: {filing_id}")

    return drivers


def _compute_stability_score(history: list[dict]) -> float:
    """Compute stability as the inverse of delta volatility.

    Uses the population standard deviation of the last ≤10 delta values.
    std_dev = 0   →  stability = 1.0  (perfectly stable)
    std_dev ≥ 0.5 →  stability = 0.0  (highly volatile)
    """
    if len(history) < 2:
        return 1.0  # Insufficient history — assume stable

    deltas = [h["delta_confidence"] for h in history[:10]]
    n = len(deltas)
    mean = sum(deltas) / n
    variance = sum((d - mean) ** 2 for d in deltas) / n
    std_dev = math.sqrt(variance)

    # Linear mapping: std_dev ∈ [0, 0.5] → stability ∈ [1.0, 0.0]
    return max(0.0, 1.0 - 2.0 * std_dev)


def _compute_reversal_risk(
    delta: float,
    posterior: float,
    history: list[dict],
) -> float:
    """Estimate probability that the belief will reverse in the next cycle.

    Factors:
    - Magnitude of the current delta (large swings tend to mean-revert)
    - How uncertain the current posterior is (low confidence = fragile)
    - Oscillation in the recent history (alternating +/− deltas)
    - Large positive delta from a weak prior (regression-to-mean risk)
    """
    risk = 0.10  # Baseline

    # Large deltas tend to partially revert
    risk += 0.25 * min(abs(delta), 0.8)

    # Low posterior confidence = more likely to flip
    risk += 0.15 * (1.0 - min(posterior, 1.0))

    # Oscillation in last 3 observations
    recent_deltas = [h["delta_confidence"] for h in history[:3]]
    if len(recent_deltas) >= 3:
        sign_changes = sum(
            1
            for i in range(1, len(recent_deltas))
            if (recent_deltas[i] >= 0) != (recent_deltas[i - 1] >= 0)
        )
        oscillation_factor = sign_changes / (len(recent_deltas) - 1)
        risk += 0.30 * oscillation_factor

    # Large upswing from a weak base — regression-to-mean risk
    if delta > 0.25 and posterior < 0.55:
        risk += 0.10

    return min(1.0, max(0.0, risk))


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------


class BeliefTrackerSkill(Skill):
    """Track prior/posterior confidence evolution for a regulatory topic.

    Implements Priority 3 of the Decision Framework Iterations: maintaining a
    Bayesian-style belief-updating engine across filing cycles.  Each call
    reads the stored prior, computes the posterior from the new observation,
    and writes back the updated state plus a history entry.
    """

    metadata = SkillMetadata(
        name="track_belief",
        description=(
            "Update the prior/posterior belief state for a regulatory topic "
            "based on a new filing observation.  Computes delta_confidence, "
            "delta_drivers, stability_score, and reversal_risk, then persists "
            "the updated state to memory.  Implements Priority 3 (priors / "
            "posteriors / decision deltas) of the Decision Framework."
        ),
        version="1.0.0",
        permissions=Permission.MEMORY_READ | Permission.MEMORY_WRITE,
        latency=LatencyClass.FAST,
        parameters=[
            SkillParameter(
                "topic",
                "str",
                "The subject to track — e.g. a regime ID like "
                "'prudential_capital_tightening', or a composite key like "
                "'sec:climate_disclosure'.  Must be a stable identifier.",
            ),
            SkillParameter(
                "domain",
                "str",
                "Regulatory domain code (sec, cfpb, fed, etc.).  Used as the "
                "namespace for storage and scoped retrieval.",
            ),
            SkillParameter(
                "new_confidence",
                "float",
                "Confidence score (0.0–1.0) derived from the current observation "
                "— e.g. signal_strength from regime_detection or the confidence "
                "field from an ImpactAssessment.",
            ),
            SkillParameter(
                "filing_id",
                "str",
                "ID of the filing that triggered this belief update.",
                required=False,
                default="",
            ),
            SkillParameter(
                "evidence_summary",
                "str",
                "Short description of the evidence driving the new_confidence "
                "score.  Included verbatim in delta_drivers.",
                required=False,
                default="",
            ),
            SkillParameter(
                "change_type",
                "str",
                "Document type of the triggering filing — e.g. 'final_rule', "
                "'proposed_rule', 'guidance', 'enforcement'.  Used to qualify "
                "the delta_drivers narrative.",
                required=False,
                default="",
            ),
            SkillParameter(
                "learning_rate",
                "float",
                "Weight given to the new observation when blending with the "
                "prior (0.0–1.0).  Default 0.40 gives meaningful updating "
                "while avoiding over-fitting to any single filing.",
                required=False,
                default=0.40,
            ),
        ],
        returns=(
            "dict — BeliefState fields: topic, domain, prior_confidence, "
            "posterior_confidence, delta_confidence, delta_drivers, "
            "stability_score, reversal_risk, observation_count, "
            "last_filing_id, updated_at"
        ),
        dependencies=[],
        max_token_budget=0,  # No LLM calls
        cacheable=False,
        tags=["belief", "priors", "posteriors", "delta", "decision-framework", "priority-3"],
    )

    def execute(self, context: SkillContext) -> SkillResult:
        if context.memory is None:
            return SkillResult(
                skill_name=self.metadata.name,
                success=False,
                data=None,
                error="Memory access denied — track_belief requires MEMORY_READ | MEMORY_WRITE",
            )

        topic: str = context.params["topic"]
        domain: str = context.params["domain"]
        new_confidence: float = float(context.params["new_confidence"])
        filing_id: str = context.params.get("filing_id", "")
        evidence_summary: str = context.params.get("evidence_summary", "")
        change_type: str = context.params.get("change_type", "")
        learning_rate: float = float(context.params.get("learning_rate", 0.40))

        # Clamp inputs
        new_confidence = max(0.0, min(1.0, new_confidence))
        learning_rate = max(0.05, min(0.95, learning_rate))

        # ------------------------------------------------------------------
        # 1. Read current (prior) belief state
        # ------------------------------------------------------------------
        existing = context.memory.get_belief_state(topic, domain)
        if existing is None:
            # First observation — seed with a neutral prior
            prior_confidence = 0.50
            observation_count = 0
        else:
            prior_confidence = float(existing["posterior_confidence"])
            observation_count = int(existing.get("observation_count", 0))

        # ------------------------------------------------------------------
        # 2. Compute posterior via exponential moving average
        #
        #   posterior = α * new_confidence + (1 − α) * prior_confidence
        #
        #   α (learning_rate) is attenuated slightly as more observations
        #   accumulate, so early filings don't over-anchor the prior.
        # ------------------------------------------------------------------
        effective_lr = learning_rate / (1.0 + 0.05 * min(observation_count, 10))
        posterior_confidence = (
            effective_lr * new_confidence + (1.0 - effective_lr) * prior_confidence
        )
        posterior_confidence = round(max(0.0, min(1.0, posterior_confidence)), 4)

        delta_confidence = round(posterior_confidence - prior_confidence, 4)

        # ------------------------------------------------------------------
        # 3. Fetch history to compute stability and reversal risk
        # ------------------------------------------------------------------
        history = context.memory.get_belief_history(topic, domain, limit=10)

        # Prepend a synthetic "current" entry so statistics include this delta
        history_with_current = [{"delta_confidence": delta_confidence}] + history

        stability_score = round(_compute_stability_score(history_with_current), 4)
        reversal_risk = round(
            _compute_reversal_risk(delta_confidence, posterior_confidence, history_with_current),
            4,
        )

        # ------------------------------------------------------------------
        # 4. Derive delta drivers
        # ------------------------------------------------------------------
        delta_drivers = _compute_delta_drivers(
            prior=prior_confidence,
            posterior=posterior_confidence,
            delta=delta_confidence,
            filing_id=filing_id,
            evidence_summary=evidence_summary,
            change_type=change_type,
        )

        # ------------------------------------------------------------------
        # 5. Build the updated belief dict and persist
        # ------------------------------------------------------------------
        updated_at = datetime.utcnow().isoformat()
        belief = {
            "topic": topic,
            "domain": domain,
            "prior_confidence": prior_confidence,
            "posterior_confidence": posterior_confidence,
            "delta_confidence": delta_confidence,
            "delta_drivers": delta_drivers,
            "stability_score": stability_score,
            "reversal_risk": reversal_risk,
            "observation_count": observation_count + 1,
            "last_filing_id": filing_id,
            "updated_at": updated_at,
        }

        context.memory.store_belief_state(topic, domain, belief)

        return SkillResult(
            skill_name=self.metadata.name,
            success=True,
            data=belief,
            token_usage=0,
            metadata={
                "topic": topic,
                "domain": domain,
                "delta_confidence": delta_confidence,
                "stability_score": stability_score,
                "reversal_risk": reversal_risk,
                "observation_count": belief["observation_count"],
            },
        )
