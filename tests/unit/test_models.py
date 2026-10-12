import pytest
from src.tasks.models import Task, BugTask, FeatureTask

def test_task_creation(basic_task):
    assert basic_task.title == "Setup CI"
    assert basic_task.priority == "High"

def test_bug_task_creation(bug_task):
    assert bug_task.severity == "Critical"

def test_feature_task_creation(feature_task):
    assert feature_task.feature_branch == "feat/ui"

def test_task_minimum_boundary():
    t = Task(task_id=1, title="Fast", priority="Low", estimated_hours=0.0)
    assert t.estimated_hours == 0.0
