"""DEPRECATED — use ``app.naturalsentinel.domain`` instead.

This module used to mix enum definitions (RegulatoryDomain, ChangeType,
Severity, IndustrySector, StateCode, Jurisdiction), Pydantic filing
models (RegulatoryFiling, ImpactAssessment, DecisionFrame, BeliefState,
MonitorResult), and the document chunk dataclass (DocumentChunk) in a
single 250-line file.

Phase R split them into focused modules under
``app.naturalsentinel.domain``:

    domain/enums.py    — RegulatoryDomain, Jurisdiction, StateCode,
                         IndustrySector, Severity, ChangeType, UnitFloat
    domain/filing.py   — RegulatoryFiling, ImpactAssessment, DecisionFrame,
                         BeliefState, MonitorResult
    domain/document.py — DocumentNode, DocumentTree, DocumentChunk

This shim re-exports every public name so legacy imports keep working.
It emits a DeprecationWarning at import time. New code should import
from ``app.naturalsentinel.domain`` directly. This shim will be removed
in a future release.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "app.naturalsentinel.models is deprecated; "
    "import from app.naturalsentinel.domain instead. "
    "This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from app.naturalsentinel.domain.document import (  # noqa: E402,F401
    DocumentChunk,
    DocumentNode,
    DocumentTree,
)
from app.naturalsentinel.domain.enums import (  # noqa: E402,F401
    ChangeType,
    IndustrySector,
    Jurisdiction,
    RegulatoryDomain,
    Severity,
    StateCode,
    UnitFloat,
)
from app.naturalsentinel.domain.filing import (  # noqa: E402,F401
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
