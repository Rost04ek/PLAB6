"""Модульні тести валідації полів, граничних значень (boundary) та переходів статусів."""

import pytest

from application.exceptions import (
    InvalidStatusTransitionError,
    RecordValidationError,
    TaskValidationError,
)
from application.models import (
    BugTask,
    FeatureTask,
    Task,
    validate_priority,
    validate_status,
)


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

    assert isinstance(exc_info.value, RecordValidationError)
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

    with pytest.raises(TaskValidationError) as feat_max_exc:
        FeatureTask(task_id=2, title="Feature", story_points=22)
    assert feat_max_exc.value.field == "story_points"

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
        ("todo", "todo"),
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


def test_direct_validator_helpers() -> None:
    """Перевірка допоміжних функцій validate_priority та validate_status."""
    assert validate_priority("  HIGH ") == "high"
    assert validate_status(" Review ") == "review"
