"""Regression test for ``qdrant_service._build_filter``.

The original bug: ``_build_filter`` imported ``Must`` from
``qdrant_client.http.models``, but ``Must`` was removed in
qdrant-client ≥ 1.8. The ``except ImportError: return None`` silently
returned ``None`` for every call, which meant every Qdrant search in
production ran **unfiltered** — losing doc isolation.

These tests verify that ``_build_filter``:
1. Returns a real ``Filter`` instance (not ``None``) when given a
   non-empty ``doc_ids`` list.
2. Bubbles an ``ImportError`` up the stack if a required class goes
   missing, rather than silently returning ``None``.
"""

from __future__ import annotations

import pytest


class TestBuildFilter:
    def test_returns_filter_for_doc_ids(self):
        """Happy path: a non-empty doc_ids list yields a real filter."""
        pytest.importorskip("qdrant_client")
        from qdrant_client.http.models import Filter

        from app.naturalsentinel.documents.qdrant_service import _build_filter

        result = _build_filter(doc_ids=["doc-1", "doc-2"], max_level=1)
        assert result is not None, (
            "_build_filter must return a Filter object for non-empty doc_ids — "
            "returning None means Qdrant runs unfiltered and doc isolation is "
            "broken."
        )
        assert isinstance(result, Filter)

    def test_returns_filter_for_max_level(self):
        pytest.importorskip("qdrant_client")
        from qdrant_client.http.models import Filter

        from app.naturalsentinel.documents.qdrant_service import _build_filter

        result = _build_filter(doc_ids=None, max_level=0)
        assert result is not None
        assert isinstance(result, Filter)

    def test_returns_none_when_no_constraints(self):
        """No constraints → None is the intended 'match anything' signal."""
        pytest.importorskip("qdrant_client")
        from app.naturalsentinel.documents.qdrant_service import _build_filter

        result = _build_filter(doc_ids=None, max_level=2)
        assert result is None

    def test_build_filter_has_no_import_error_handler(self):
        """Source-level guard: ``_build_filter`` must not have an
        ``except ImportError`` handler. That pattern is what caused the
        original ``Must`` bug — the silent fallback to ``return None``
        shipped unfiltered Qdrant searches to production. Checking the
        AST (rather than a brittle monkeypatch) catches any
        reintroduction.
        """
        import ast
        import inspect
        import textwrap

        from app.naturalsentinel.documents import qdrant_service

        source = textwrap.dedent(inspect.getsource(qdrant_service._build_filter))
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is not None:
                handler_src = ast.unparse(node.type)
                assert "ImportError" not in handler_src, (
                    "_build_filter must not swallow ImportError. A missing "
                    "qdrant class is a structural failure and must bubble "
                    "up so we fail boot loudly instead of returning None "
                    "and silently running Qdrant searches unfiltered."
                )
