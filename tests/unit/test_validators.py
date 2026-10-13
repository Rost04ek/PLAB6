import pytest
from application.models import Task, InvalidTaskError, InvalidStatusTransition

@pytest.mark.parametrize("priority", ["Unknown", "SuperHigh"])
def test_invalid_priority_raises(priority):
    with pytest.raises(InvalidTaskError, match="Invalid priority"):
        Task(task_id=1, title="Bad", priority=priority, estimated_hours=1.0)

def test_negative_hours_raises():
    with pytest.raises(InvalidTaskError, match="negative"):
        Task(task_id=1, title="Bad", priority="Low", estimated_hours=-2.0)

@pytest.mark.parametrize("status", ["In Progress", "Closed"])
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
