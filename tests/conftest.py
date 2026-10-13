import pytest
from application.models import Task, BugTask, FeatureTask
from application.services import TaskBoard

@pytest.fixture
def basic_task():
    return Task(task_id=1, title="Setup CI", priority="High", estimated_hours=4.5)

@pytest.fixture
def bug_task():
    return BugTask(task_id=2, title="Fix login", priority="Critical", estimated_hours=1.5, severity="High")

@pytest.fixture
def feature_task():
    return FeatureTask(task_id=3, title="Dark Mode", priority="Medium", estimated_hours=5.0, feature_branch="feat/ui")

@pytest.fixture
def populated_board(basic_task, bug_task, feature_task):
    board = TaskBoard()
    board.add_task(basic_task)
    board.add_task(bug_task)
    board.add_task(feature_task)
    yield board
    board._tasks.clear()

class FakeTaskRepository:
    def __init__(self):
        self.items = {}
    def save(self, task: Task) -> bool:
        self.items[task.task_id] = task
        return True

@pytest.fixture
def fake_repo():
    return FakeTaskRepository()

@pytest.fixture
def task_factory():
    def _create(task_id=99, title="Fac", priority="Low", estimated_hours=1.0):
        return Task(task_id, title, priority, estimated_hours)
    return _create
