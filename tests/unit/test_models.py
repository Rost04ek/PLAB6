"""Модульні (Unit) тести для моделей Task, BugTask, FeatureTask та TaskBoard."""

import pytest

from task_manager.config import AppConfig
from task_manager.exceptions import (
    InvalidStatusTransitionError,
    TaskNotFoundError,
    TaskValidationError,
)
from task_manager.models import BugTask, FeatureTask, Task, TaskBoard


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

    assert sample_feature.task_type == "feature"
    assert sample_feature.story_points == 8
    assert sample_feature.epic == "Security"
    assert sample_feature.is_completed is True
    assert sample_feature.to_dict()["story_points"] == 8


def test_task_creation_with_parameterized_fixture(valid_priority: str) -> None:
    """Використання параметризованої фікстури valid_priority."""
    task = Task(task_id=10, title="Перевірка пріоритету", priority=valid_priority)
    assert task.priority == valid_priority


@pytest.mark.parametrize(
    "estimate",
    [
        pytest.param(0.0, id="min_boundary_zero"),
        pytest.param(0.01, id="just_above_min"),
        pytest.param(100.0, id="normal_middle"),
        pytest.param(199.99, id="just_below_max"),
        pytest.param(200.0, id="max_boundary_200"),
    ],
)
def test_estimate_hours_valid_boundaries(estimate: float) -> None:
    """Граничне тестування (Boundary testing) допустимих значень estimate_hours (0..200)."""
    task = Task(task_id=1, title="Boundary test", estimate_hours=estimate)
    assert task.estimate_hours == pytest.approx(estimate)


@pytest.mark.parametrize(
    "invalid_estimate",
    [
        pytest.param(-0.01, id="below_min_boundary"),
        pytest.param(-50.0, id="negative_value"),
        pytest.param(200.01, id="above_max_boundary"),
        pytest.param(500.0, id="large_invalid_value"),
    ],
)
def test_estimate_hours_invalid_boundaries_raise_error(
    invalid_estimate: float,
) -> None:
    """Граничне тестування недопустимих значень estimate_hours через pytest.raises."""
    with pytest.raises(TaskValidationError, match="between 0.0 and 200.0") as exc_info:
        Task(task_id=1, title="Invalid estimate", estimate_hours=invalid_estimate)

    assert exc_info.value.field == "estimate_hours"


@pytest.mark.parametrize(
    ("task_id", "title", "priority", "status", "expected_field"),
    [
        (0, "Valid title", "low", "todo", "task_id"),
        (-5, "Valid title", "low", "todo", "task_id"),
        (1, "   ", "low", "todo", "title"),
        (1, "Valid title", "urgent_invalid", "todo", "priority"),
        (1, "Valid title", "low", "unknown_status", "status"),
    ],
)
def test_task_validation_errors_on_invalid_fields(
    task_id: int,
    title: str,
    priority: str,
    status: str,
    expected_field: str,
) -> None:
    """Параметризована перевірка кастомного винятку TaskValidationError та його поля field."""
    with pytest.raises(TaskValidationError) as exc_info:
        Task(
            task_id=task_id,
            title=title,
            priority=priority,
            status=status,
        )
    assert exc_info.value.field == expected_field


def test_bug_and_feature_invalid_specific_fields() -> None:
    """Перевірка валідації специфічних полів BugTask (severity) та FeatureTask (story_points, epic)."""
    with pytest.raises(TaskValidationError) as bug_exc:
        BugTask(task_id=1, title="Bug", severity="catastrophic")
    assert bug_exc.value.field == "severity"

    with pytest.raises(TaskValidationError) as feat_exc:
        FeatureTask(task_id=2, title="Feature", story_points=0)
    assert feat_exc.value.field == "story_points"

    with pytest.raises(TaskValidationError) as epic_exc:
        FeatureTask(task_id=3, title="Feature", story_points=5, epic="  ")
    assert epic_exc.value.field == "epic"


@pytest.mark.parametrize(
    ("initial_status", "next_status"),
    [
        ("todo", "in_progress"),
        ("todo", "cancelled"),
        ("in_progress", "review"),
        ("in_progress", "done"),
        ("review", "done"),
        ("cancelled", "todo"),
        ("todo", "todo"),  # ідемпотентний перехід у той самий статус
    ],
)
def test_valid_status_transitions(initial_status: str, next_status: str) -> None:
    """Перевірка допустимих переходів між статусами завдання."""
    task = Task(task_id=1, title="Transition test", status=initial_status)
    task.change_status(next_status)
    assert task.status == next_status


@pytest.mark.parametrize(
    ("initial_status", "invalid_target"),
    [
        ("todo", "done"),
        ("todo", "review"),
        ("done", "in_progress"),
        ("done", "todo"),
        ("cancelled", "done"),
    ],
)
def test_invalid_status_transition_raises_custom_exception(
    initial_status: str,
    invalid_target: str,
) -> None:
    """Перевірка генерації InvalidStatusTransitionError при забороненому переході."""
    task = Task(task_id=1, title="Invalid transition", status=initial_status)
    with pytest.raises(InvalidStatusTransitionError) as exc_info:
        task.change_status(invalid_target)

    assert exc_info.value.current_status == initial_status
    assert exc_info.value.target_status == invalid_target


def test_change_status_to_unknown_value_raises_validation_error(
    sample_task: Task,
) -> None:
    """Спроба змінити статус на неіснуючий піднімає TaskValidationError."""
    with pytest.raises(TaskValidationError, match="Unsupported status"):
        sample_task.change_status("archived")


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

    with pytest.raises(TaskValidationError, match="Invalid priority filter"):
        board.filter_by_priority("critical")

    with pytest.raises(TaskValidationError, match="Invalid status filter"):
        board.filter_by_status("review")
