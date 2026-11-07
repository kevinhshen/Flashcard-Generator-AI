import pytest


@pytest.fixture(autouse=True)
def research_database_in_tmp(monkeypatch, tmp_path):
    """Tests must never write run records into the real data/ folder."""
    monkeypatch.setenv("RECALL_DATA_DIR", str(tmp_path / "research-data"))
