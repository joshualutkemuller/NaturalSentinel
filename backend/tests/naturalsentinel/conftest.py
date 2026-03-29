"""Shared test fixtures — works with both pytest and unittest."""

import os
import tempfile

# Try pytest fixtures, fall back to simple factory functions
try:
    import pytest

    @pytest.fixture
    def mock_provider():
        from app.naturalsentinel import MockProvider

        return MockProvider()

    @pytest.fixture
    def memory():
        from app.naturalsentinel import MemoryStore

        store = MemoryStore(":memory:")
        yield store
        store.close()

    @pytest.fixture
    def agent(mock_provider, memory, tmp_path):
        from app.naturalsentinel import RegulatoryMonitorAgent

        return RegulatoryMonitorAgent(
            provider=mock_provider,
            memory=memory,
            state_path=str(tmp_path / "state.json"),
        )

except ImportError:
    pass


# Factory functions usable from unittest.TestCase
def make_mock_provider():
    from app.naturalsentinel import MockProvider

    return MockProvider()


def make_memory():
    from app.naturalsentinel import MemoryStore

    return MemoryStore(":memory:")


def make_agent(provider=None, memory=None, state_dir=None):
    from app.naturalsentinel import MemoryStore, MockProvider, RegulatoryMonitorAgent

    provider = provider or MockProvider()
    memory = memory or MemoryStore(":memory:")
    state_dir = state_dir or tempfile.mkdtemp()
    return RegulatoryMonitorAgent(
        provider=provider,
        memory=memory,
        state_path=os.path.join(state_dir, "state.json"),
    )
