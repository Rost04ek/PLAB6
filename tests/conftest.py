import pytest
from src.tasks.core import Task, BugTask, FeatureTask, TaskBoard

@pytest.fixture
def basic_task():
    return Task(task_id=1, title="Setup CI", priority="High", estimated_hours=4.5)

@pytest.fixture
def bug_task():
    return BugTask(task_id=2, title="Fix login", priority="Critical", estimated_hours=1.5, severity="Critical")

@pytest.fixture
def populated_board(basic_task, bug_task):
    board = TaskBoard()
    board.add_task(basic_task)
    board.add_task(bug_task)
    return board