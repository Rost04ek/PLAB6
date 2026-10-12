import pytest
from src.tasks.core import Task, BugTask, FeatureTask, TaskBoard

def test_task_creation(basic_task):
    assert basic_task.title == "Setup CI"
    assert basic_task.priority == "High"

def test_bug_task_creation(bug_task):
    assert bug_task.severity == "Critical"

def test_feature_task_creation(feature_task):
    assert feature_task.feature_branch == "feat/ui"

def test_task_minimum_boundary():
    # Boundary case = 0.0
    t = Task(task_id=1, title="Fast", priority="Low", estimated_hours=0.0)
    assert t.estimated_hours == 0.0

def test_task_factory_usage(task_factory):
    t = task_factory(priority="High")
    assert t.priority == "High"
    assert t.task_id == 10

def test_board_filters_and_counts(populated_board):
    assert populated_board.count_completed() == 0
    assert populated_board.count_incomplete() == 3
    
    high_tasks = populated_board.filter_by_priority("High")
    assert len(high_tasks) == 1
    
    found = populated_board.find_task(1)
    assert found is not None
    assert populated_board.find_task(999) is None

def test_average_estimation_approx(populated_board):
    assert populated_board.average_estimation() == pytest.approx(3.6666666666666665)

def test_empty_board():
    board = TaskBoard()
    assert board.count_completed() == 0
    assert board.count_incomplete() == 0
    assert board.average_estimation() == 0.0
