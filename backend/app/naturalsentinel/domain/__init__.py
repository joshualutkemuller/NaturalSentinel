"""Pure domain value objects for NaturalSentinel.

This package holds Pydantic models that represent domain concepts —
``RegulatoryFiling``, ``ImpactAssessment``, ``DocumentNode``,
``DocumentTree``, and the enums for ``RegulatoryDomain`` /
``IndustrySector`` / ``StateCode`` / ``Jurisdiction`` / ``ChangeType`` /
``Severity``.

No database, no I/O, no framework dependencies — just value objects the
rest of the system passes around. SQLModel tables for persistence live
in ``app.naturalsentinel.memory.pg_models`` instead.

Before Phase R, these were split across ``app.naturalsentinel.models``
(filing + enums + DocumentChunk) and
``app.naturalsentinel.documents.models`` (DocumentNode + DocumentTree).
Both legacy paths remain as deprecation shims.

Import from here::

    from app.naturalsentinel.domain import (
        RegulatoryFiling,
        ImpactAssessment,
        DecisionFrame,
        BeliefState,
        MonitorResult,
        RegulatoryDomain,
        IndustrySector,
        StateCode,
        Jurisdiction,
        Severity,
        ChangeType,
        DocumentNode,
        DocumentTree,
        DocumentChunk,
    )
"""

from app.naturalsentinel.domain.document import (
    DocumentChunk,
    DocumentNode,
    DocumentTree,
)
from app.naturalsentinel.domain.enums import (
    ChangeType,
    IndustrySector,
    Jurisdiction,
    RegulatoryDomain,
    Severity,
    StateCode,
    UnitFloat,
)
from app.naturalsentinel.domain.filing import (
    BeliefState,
    DecisionFrame,
    ImpactAssessment,
    MonitorResult,
    RegulatoryFiling,
)

__all__ = [
    "BeliefState",
    "ChangeType",
    "DecisionFrame",
    "DocumentChunk",
    "DocumentNode",
    "DocumentTree",
    "ImpactAssessment",
    "IndustrySector",
    "Jurisdiction",
    "MonitorResult",
    "RegulatoryDomain",
    "RegulatoryFiling",
    "Severity",
    "StateCode",
    "UnitFloat",
]
