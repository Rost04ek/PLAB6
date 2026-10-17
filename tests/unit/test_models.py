"""Модульні (Unit) тести для моделей Task, BugTask, FeatureTask та TaskBoard."""

import pytest

from application.config import AppConfig
from application.exceptions import (
    InvalidStatusTransitionError,
    TaskNotFoundError,
    TaskValidationError,
)
from application.models import BugTask, FeatureTask, Task, TaskBoard


def test_task_creation_normal(sample_task: Task) -> None:
    """Перевірка коректного створення Task та властивостей за замовчуванням."""
    # Arrange & Act виконуються у фікстурі sample_task
    # Assert
    assert sample_task.task_id == 1
    assert sample_task.title == "Написати документацію API"
    assert sample_task.priority == "medium"
    assert sample_task.status == "todo"
    assert sample_task.task_type == "task"
    assert not sample_task.is_completed
    assert sample_task.weighted_effort == pytest.approx(6.75)


def test_bug_and_feature_task_creation(
    sample_bug: BugTask,
    sample_feature: FeatureTask,
) -> None:
    """Перевірка створення спеціалізованих класів BugTask та FeatureTask."""
    assert sample_bug.task_type == "bug"
    assert sample_bug.severity == "blocker"
    # 6.0 * 3.0 (critical) * 1.5 (blocker) = 27.0
    assert sample_bug.weighted_effort == pytest.approx(27.0)
    assert sample_bug.to_dict()["severity"] == "blocker"

    minor_bug = BugTask(task_id=9, title="Косметичний баг", priority="low", estimate_hours=2.0, severity="minor")
    assert minor_bug.weighted_effort == pytest.approx(2.0)

    major_bug = BugTask(task_id=10, title="Помилка форми", priority="low", estimate_hours=2.0, severity="major")
    assert major_bug.weighted_effort == pytest.approx(2.4)

    assert sample_feature.task_type == "feature"
    assert sample_feature.story_points == 8
    assert sample_feature.epic == "Security"
    assert sample_feature.is_completed is True
    assert sample_feature.to_dict()["story_points"] == 8


def test_task_creation_with_parameterized_fixture(valid_priority: str) -> None:
    """Використання параметризованої фікстури valid_priority."""
    task = Task(task_id=10, title="Перевірка пріоритету", priority=valid_priority)
    assert task.priority == valid_priority


def test_empty_task_board_behavior() -> None:
    """Перевірка поведінки порожнього TaskBoard (граничний випадок порожньої колекції)."""
    board = TaskBoard()
    assert len(board) == 0
    assert board.count_completed() == 0
    assert board.count_incomplete() == 0
    assert board.completion_rate() == pytest.approx(0.0)
    assert board.average_estimate_hours() == pytest.approx(0.0)
    assert board.search_by_title("API") == []
    assert board.search_by_title("   ") == []


def test_task_board_filtering_searching_and_metrics(
    populated_board: TaskBoard,
) -> None:
    """Перевірка фільтрації за priority/status, пошуку та підрахунку completed/incomplete."""
    assert len(populated_board) == 3
    assert 1 in populated_board
    assert 999 not in populated_board

    assert populated_board.count_completed() == 1
    assert populated_board.count_incomplete() == 2
    assert populated_board.completion_rate() == pytest.approx(33.333333, rel=1e-4)
    # (4.5 + 6.0 + 12.0) / 3 = 7.5
    assert populated_board.average_estimate_hours() == pytest.approx(7.5)

    high_tasks = populated_board.filter_by_priority("HIGH")
    assert len(high_tasks) == 1
    assert high_tasks[0].task_id == 3

    todo_tasks = populated_board.filter_by_status("todo")
    assert len(todo_tasks) == 1
    assert todo_tasks[0].task_id == 1

    found = populated_board.search_by_title("oauth2")
    assert len(found) == 1
    assert found[0].task_id == 3


def test_task_board_duplicate_and_not_found_errors(
    populated_board: TaskBoard,
    sample_task: Task,
) -> None:
    """Перевірка заборони додавання дубліката ID та пошуку неіснуючого завдання."""
    with pytest.raises(TaskValidationError, match="already exists"):
        populated_board.add_task(sample_task)

    with pytest.raises(TaskNotFoundError) as exc_info:
        populated_board.get_task(404)
    assert exc_info.value.task_id == 404


def test_task_board_config_constraints(task_factory) -> None:
    """Перевірка обмежень конфігурації TaskBoard при додаванні та фільтрації."""
    restricted_config = AppConfig(
        allowed_statuses=("todo", "done"),
        allowed_priorities=("low", "medium"),
        max_estimate_hours=10.0,
    )
    board = TaskBoard(config=restricted_config)

    with pytest.raises(TaskValidationError, match="not allowed by board config"):
        board.add_task(task_factory(status="in_progress"))

    with pytest.raises(TaskValidationError, match="not allowed by board config"):
        board.add_task(task_factory(priority="critical"))

    with pytest.raises(TaskValidationError, match="exceeds max"):
        board.add_task(task_factory(estimate_hours=15.0))

    with pytest.raises(TaskValidationError, match="Unsupported priority"):
        board.filter_by_priority("critical")

    with pytest.raises(TaskValidationError, match="Unsupported status"):
        board.filter_by_status("review")
