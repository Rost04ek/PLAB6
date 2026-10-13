import pytest
from application.config import get_allowed_statuses, get_allowed_priorities

def test_config_allowed_statuses(monkeypatch):
    monkeypatch.setenv("ALLOWED_STATUSES", "Draft,Published")
    assert get_allowed_statuses() == ["Draft", "Published"]

def test_config_allowed_priorities(monkeypatch):
    monkeypatch.setenv("ALLOWED_PRIORITIES", "P1,P2,P3")
    assert get_allowed_priorities() == ["P1", "P2", "P3"]
