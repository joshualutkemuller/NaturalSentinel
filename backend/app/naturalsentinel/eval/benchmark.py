"""Benchmark suite — pairs filings with ground-truth extraction labels.

Cases are sourced from three places:

1. ``feedback_log`` corrections — every human override of a model prediction
   is a labeled example.  The model's original output is the prediction;
   the corrected value is the ground truth.

2. JSON fixture files — hand-labeled reference sets curated for regression
   testing or domain-specific evaluation.  Expected format::

       [
         {
           "case_id": "case-001",
           "filing": { <serialised RegulatoryFiling dict> },
           "predicted": { <model output dict> },
           "expected": { "severity": "critical", ... },
           "labeled_fields": ["severity", "change_type"],
           "source": "fixture",
           "tags": ["sec", "climate"]
         },
         ...
       ]

3. Programmatic construction — for unit tests or synthetic benchmarks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BenchmarkCase:
    """A single labeled evaluation example."""

    case_id: str
    filing: dict  # Serialised RegulatoryFiling
    predicted: dict  # What the model originally produced
    expected: dict  # Ground-truth labels (may be partial)
    source: str = "feedback"  # "feedback" | "fixture" | "synthetic"
    labeled_fields: list[str] = field(default_factory=list)  # Fields with GT
    created_at: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class BenchmarkSuite:
    """An ordered collection of labeled evaluation cases."""

    name: str
    cases: list[BenchmarkCase] = field(default_factory=list)
    description: str = ""

    def __len__(self) -> int:
        return len(self.cases)

    def filter_by_domain(self, domain: str) -> BenchmarkSuite:
        filtered = [c for c in self.cases if c.filing.get("domain") == domain]
        return BenchmarkSuite(
            name=f"{self.name}:{domain}",
            cases=filtered,
            description=f"{self.description} (domain={domain})",
        )

    def filter_by_field(self, field_name: str) -> BenchmarkSuite:
        filtered = [c for c in self.cases if field_name in c.labeled_fields]
        return BenchmarkSuite(
            name=f"{self.name}:{field_name}",
            cases=filtered,
            description=f"{self.description} (field={field_name})",
        )


def load_suite_from_feedback(
    memory_store,
    domains: list[str] | None = None,
    limit: int = 500,
) -> BenchmarkSuite:
    """Build a BenchmarkSuite from ``feedback_log`` corrections in memory.

    Each (filing_id, field) correction becomes a labeled field on a
    BenchmarkCase.  A single filing can contribute multiple labeled fields
    if the reviewer corrected more than one output field.

    Args:
        memory_store: A :class:`~naturalsentinel.memory.store.MemoryStore`.
        domains: Optional domain filter; ``None`` = all domains.
        limit: Maximum number of benchmark cases to return.

    Returns:
        A :class:`BenchmarkSuite` with ``source="feedback"`` cases.
    """
    rows = memory_store.conn.execute(
        "SELECT * FROM feedback_log ORDER BY created_at DESC LIMIT ?",
        (limit * 5,),  # Over-fetch to account for grouping
    ).fetchall()

    # Group corrections by filing_id
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        r = dict(row)
        fid = r["filing_id"]
        grouped.setdefault(fid, []).append(r)

    cases: list[BenchmarkCase] = []
    for filing_id, corrections in grouped.items():
        if len(cases) >= limit:
            break

        # Fetch the original episodic memory for this filing
        mem_record = memory_store.get(f"episodic:{filing_id}")
        if mem_record is None:
            continue

        filing_dict = mem_record.content.get("filing", {})
        impact_dict = mem_record.content.get("impact", {})

        if not filing_dict or not impact_dict:
            continue

        domain = filing_dict.get("domain", "")
        if domains and domain not in domains:
            continue

        # Build expected dict from corrections (newest correction wins)
        expected: dict = {}
        labeled_fields: list[str] = []
        for corr in reversed(corrections):  # oldest → newest so newest wins
            f = corr["field"]
            expected[f] = corr["new_value"]
            if f not in labeled_fields:
                labeled_fields.append(f)

        cases.append(
            BenchmarkCase(
                case_id=f"feedback:{filing_id}",
                filing=filing_dict,
                predicted=impact_dict,
                expected=expected,
                source="feedback",
                labeled_fields=labeled_fields,
                created_at=corrections[0].get("created_at", ""),
                tags=[domain],
            )
        )

    return BenchmarkSuite(
        name="feedback_log",
        cases=cases,
        description=(
            f"Benchmark derived from {len(cases)} human-corrected filings "
            f"in feedback_log" + (f" (domains={domains})" if domains else "")
        ),
    )


def load_suite_from_fixture(fixture_path: str) -> BenchmarkSuite:
    """Load a BenchmarkSuite from a JSON fixture file.

    The JSON file must be a list of case objects matching the schema
    described in the module docstring.

    Args:
        fixture_path: Path to the JSON file (absolute or relative to cwd).

    Returns:
        A :class:`BenchmarkSuite` with ``source="fixture"`` cases.
    """
    path = Path(fixture_path)
    with path.open() as fh:
        raw = json.load(fh)

    cases = []
    for item in raw:
        cases.append(
            BenchmarkCase(
                case_id=item.get("case_id", f"fixture-{len(cases)}"),
                filing=item.get("filing", {}),
                predicted=item.get("predicted", {}),
                expected=item.get("expected", {}),
                source=item.get("source", "fixture"),
                labeled_fields=item.get(
                    "labeled_fields", list(item.get("expected", {}).keys())
                ),
                created_at=item.get("created_at", ""),
                tags=item.get("tags", []),
            )
        )

    return BenchmarkSuite(
        name=path.stem,
        cases=cases,
        description=f"Fixture: {path.name} ({len(cases)} cases)",
    )
