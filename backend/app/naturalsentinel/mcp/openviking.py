"""OpenViking context database integration for NaturalSentinel MCP.

OpenViking (volcengine/OpenViking) is an agent-native context database that
stores memory, resources, and skills under a filesystem paradigm using
``viking://`` URIs with tiered abstraction (L0 abstract → L1 overview → L2
full content).

This module bridges NaturalSentinel's MCP server and FastAPI web layer with
a running OpenViking server so both web-based clients and MCP tool-calling
clients share the same context store.

Configure via the ``OPENVIKING_URL`` environment variable (default:
``http://localhost:1933``).
"""

import logging
import os
from typing import Any

logger = logging.getLogger("SentinelMCP.OpenViking")

_OPENVIKING_URL = os.getenv("OPENVIKING_URL", "http://localhost:1933")

# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

_ov_client = None


def _get_ov_client():
    """Return a synchronous OpenViking HTTP client (lazy-initialized)."""
    global _ov_client
    if _ov_client is None:
        try:
            from openviking import SyncHTTPClient

            _ov_client = SyncHTTPClient(url=_OPENVIKING_URL)
        except ImportError as exc:
            raise ImportError(
                "openviking SDK not installed. Run: pip install openviking"
            ) from exc
    return _ov_client


def reset_client() -> None:
    """Clear the cached client (useful for tests and reconfiguration)."""
    global _ov_client
    _ov_client = None


def is_available() -> bool:
    """Return True if the OpenViking server is reachable."""
    try:
        return _get_ov_client().is_healthy()
    except Exception:
        return False


def server_url() -> str:
    return _OPENVIKING_URL


# ---------------------------------------------------------------------------
# Tool implementations — called from StandaloneServer and MCP tool handlers
# ---------------------------------------------------------------------------


def ov_search(query: str, target_uri: str = "", limit: int = 10) -> Any:
    """Semantic search across the OpenViking context store."""
    return _get_ov_client().find(query=query, target_uri=target_uri, limit=limit)


def ov_read(uri: str) -> str:
    """Read the full content of a resource at the given viking:// URI."""
    return _get_ov_client().read(uri)


def ov_list(uri: str = "viking://") -> list:
    """List resources under a viking:// URI (directory listing)."""
    return _get_ov_client().ls(uri)


def ov_add_resource(path: str, wait: bool = True) -> dict:
    """Ingest a URL or local file path into the OpenViking context store."""
    return _get_ov_client().add_resource(path, wait=wait)


def ov_grep(uri: str, pattern: str, case_insensitive: bool = False) -> dict:
    """Regex search within resources under a viking:// URI."""
    return _get_ov_client().grep(
        uri=uri, pattern=pattern, case_insensitive=case_insensitive
    )


def ov_glob(pattern: str, uri: str = "viking://") -> dict:
    """Path-pattern match (glob) within the OpenViking filesystem."""
    return _get_ov_client().glob(pattern=pattern, uri=uri)


def ov_commit_session(session_id: str) -> dict:
    """Commit a session to long-term memory in OpenViking."""
    return _get_ov_client().commit_session(session_id)
