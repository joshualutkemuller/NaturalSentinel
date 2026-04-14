"""Pure domain value objects for NaturalSentinel.

This package holds Pydantic models that represent domain concepts —
``RegulatoryFiling``, ``ImpactAssessment``, ``DocumentNode``,
``DocumentTree``, and the enums for ``RegulatoryDomain`` /
``IndustrySector`` / ``StateCode`` / ``Jurisdiction`` / ``Tier`` /
``ChangeType`` / ``Severity``.

No database, no I/O, no framework dependencies — just value objects the
rest of the system passes around. SQLModel tables for persistence live
in ``app.naturalsentinel.memory.pg_models`` instead.

Before Phase R, these were split across ``app.naturalsentinel.models``
(filing + enums) and ``app.naturalsentinel.documents.models`` (document
tree). Both legacy paths remain as deprecation shims.

Import from here::

    from app.naturalsentinel.domain import (
        RegulatoryFiling,
        ImpactAssessment,
        RegulatoryDomain,
        IndustrySector,
        StateCode,
        Jurisdiction,
        Tier,
        DocumentNode,
        DocumentTree,
    )
"""
