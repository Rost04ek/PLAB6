import pytest
from src.tasks.core import Task, BugTask, FeatureTask, InvalidTaskError, InvalidStatusTransition, get_allowed_statuses, get_allowed_priorities

def test_task_creation(basic_task):
    assert basic_task.title == "Setup CI"
    assert basic_task.priority == "High"

def test_bug_task_creation(bug_task):
    assert bug_task.severity == "Critical"

def test_feature_task_creation(feature_task):
    assert feature_task.feature_branch == "feat/ui"

@pytest.mark.parametrize("priority", ["Unknown", "SuperHigh", ""])
def test_invalid_priority_raises(priority):
    with pytest.raises(InvalidTaskError, match="Invalid priority"):
        Task(task_id=1, title="Bad", priority=priority, estimated_hours=1.0)

def test_negative_hours_raises():
    with pytest.raises(InvalidTaskError, match="negative"):
        Task(task_id=1, title="Bad", priority="Low", estimated_hours=-2.0)

@pytest.mark.parametrize("status", ["In Progress", "Resolved", "Closed"])
def test_valid_status_change(basic_task, status):
    basic_task.change_status(status)
    assert basic_task.status == status

def test_invalid_status_change(basic_task):
    with pytest.raises(InvalidTaskError, match="Invalid status"):
        basic_task.change_status("Deploying")

def test_invalid_status_transition(basic_task):
    basic_task.change_status("Closed")
    with pytest.raises(InvalidStatusTransition, match="Cannot reopen"):
        basic_task.change_status("In Progress")

# Monkeypatch tests
def test_config_allowed_statuses(monkeypatch):
    monkeypatch.setenv("ALLOWED_STATUSES", "Draft,Published")
    assert get_allowed_statuses() == ["Draft", "Published"]

def test_config_allowed_priorities(monkeypatch):
    monkeypatch.setenv("ALLOWED_PRIORITIES", "P1,P2,P3")
    assert get_allowed_priorities() == ["P1", "P2", "P3"]