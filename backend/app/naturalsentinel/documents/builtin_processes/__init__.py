"""Deprecated shim — built-in processes moved to ``app.naturalsentinel.data.processes``.

Phase R extras C relocated the process markdown files (and the loader)
out of ``documents/`` and into ``data/`` alongside the other data
artifacts (mappings, samples). Import from the new path directly::

    from app.naturalsentinel.data.processes import load_builtin_processes

This shim will be removed once downstream imports migrate.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "app.naturalsentinel.documents.builtin_processes is deprecated; "
    "import from app.naturalsentinel.data.processes instead",
    DeprecationWarning,
    stacklevel=2,
)

from app.naturalsentinel.data.processes import (  # noqa: E402
    BUILTIN_PROCESS_NAMES,
    get_builtin_definition,
    load_builtin_processes,
)

__all__ = [
    "BUILTIN_PROCESS_NAMES",
    "get_builtin_definition",
    "load_builtin_processes",
]
