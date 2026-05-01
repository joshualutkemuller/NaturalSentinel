"""DEPRECATED — use ``app.naturalsentinel.domain`` instead.

Document intelligence value objects (``DocumentNode`` and
``DocumentTree``) now live in ``app.naturalsentinel.domain.document``
alongside ``DocumentChunk`` from the old ``app.naturalsentinel.models``
file. Consolidating all pure-Pydantic / pure-dataclass value objects in
``app.naturalsentinel.domain`` is the Phase R convention.

This shim re-exports the two names the old module defined and emits a
DeprecationWarning at import time. New code should import from
``app.naturalsentinel.domain`` directly. This shim will be removed in a
future release.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "app.naturalsentinel.documents.models is deprecated; "
    "import from app.naturalsentinel.domain instead. "
    "This shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from app.naturalsentinel.domain.document import (  # noqa: E402,F401
    DocumentNode,
    DocumentTree,
)

__all__ = ["DocumentNode", "DocumentTree"]
