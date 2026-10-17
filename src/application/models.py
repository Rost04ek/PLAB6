"""Доменні моделі: Task, BugTask, FeatureTask та TaskBoard."""

from dataclasses import dataclass, field
from typing import Any

from application.config import AppConfig, DEFAULT_PRIORITIES, DEFAULT_STATUSES
from application.exceptions import (
    InvalidStatusTransitionError,
    TaskNotFoundError,
    TaskValidationError,
)

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "todo": {"in_progress", "cancelled"},
    "in_progress": {"review", "todo", "done", "cancelled"},
    "review": {"in_progress", "done", "cancelled"},
    "done": set(),
    "cancelled": {"todo"},
}

PRIORITY_WEIGHTS: dict[str, float] = {
    "low": 1.0,
    "medium": 1.5,
    "high": 2.0,
    "critical": 3.0,
}


def validate_priority(priority: str, allowed: tuple[str, ...] = DEFAULT_PRIORITIES) -> str:
    """Валідує та нормалізує пріоритет завдання."""
    norm = priority.strip().lower()
    if norm not in allowed:
        raise TaskValidationError("priority", f"Unsupported priority '{priority}'")
    return norm


def validate_status(status: str, allowed: tuple[str, ...] = DEFAULT_STATUSES) -> str:
    """Валідує та нормалізує статус завдання."""
    norm = status.strip().lower()
    if norm not in allowed:
        raise TaskValidationError("status", f"Unsupported status '{status}'")
    return norm


@dataclass
class Task:
    """Базова модель завдання."""

    task_id: int
    title: str
    priority: str = "medium"
    status: str = "todo"
    estimate_hours: float = 1.0

    def __post_init__(self) -> None:
        if self.task_id <= 0:
            raise TaskValidationError("task_id", "Task ID must be a positive integer")
        cleaned_title = self.title.strip()
        if not cleaned_title:
            raise TaskValidationError("title", "Title cannot be empty")
        self.title = cleaned_title
        self.priority = validate_priority(self.priority)
        self.status = validate_status(self.status)

        if not (0.0 <= self.estimate_hours <= 200.0):
            raise TaskValidationError(
                "estimate_hours",
                "Estimate hours must be between 0.0 and 200.0",
            )

    @property
    def task_type(self) -> str:
        """Тип завдання для серіалізації."""
        return "task"

    @property
    def is_completed(self) -> bool:
        """Повертає True, якщо завдання виконано (status == 'done')."""
        return self.status == "done"

    @property
    def weighted_effort(self) -> float:
        """Обчислює зважену трудомісткість з урахуванням коефіцієнта пріоритету."""
        return self.estimate_hours * PRIORITY_WEIGHTS[self.priority]

    def change_status(self, new_status: str) -> None:
        """Змінює статус завдання з перевіркою допустимих переходів."""
        target = validate_status(new_status)
        if target == self.status:
            return
        allowed = ALLOWED_TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise InvalidStatusTransitionError(self.status, target)
        self.status = target

    def to_dict(self) -> dict[str, Any]:
        """Перетворює завдання на словник для експорту."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "title": self.title,
            "priority": self.priority,
            "status": self.status,
            "estimate_hours": self.estimate_hours,
        }


@dataclass
class BugTask(Task):
    """Спеціалізоване завдання для виправлення дефекту (Bug)."""

    severity: str = "major"
    environment: str = "prod"

    def __post_init__(self) -> None:
        super().__post_init__()
        norm_severity = self.severity.strip().lower()
        if norm_severity not in ("minor", "major", "blocker"):
            raise TaskValidationError(
                "severity", f"Unsupported bug severity '{self.severity}'"
            )
        self.severity = norm_severity

    @property
    def task_type(self) -> str:
        return "bug"

    @property
    def weighted_effort(self) -> float:
        base = super().weighted_effort
        multiplier = (
            1.5 if self.severity == "blocker" else (1.2 if self.severity == "major" else 1.0)
        )
        return base * multiplier

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["severity"] = self.severity
        data["environment"] = self.environment
        return data


@dataclass
class FeatureTask(Task):
    """Спеціалізоване завдання для розробки нової функціональності (Feature)."""

    story_points: int = 3
    epic: str = "Core"

    def __post_init__(self) -> None:
        super().__post_init__()
        if not (1 <= self.story_points <= 21):
            raise TaskValidationError(
                "story_points", "Story points must be between 1 and 21"
            )
        if not self.epic.strip():
            raise TaskValidationError("epic", "Epic name cannot be empty")
        self.epic = self.epic.strip()

    @property
    def task_type(self) -> str:
        return "feature"

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["story_points"] = self.story_points
        data["epic"] = self.epic
        return data


@dataclass
class TaskBoard:
    """Дошка завдань для зберігання, пошуку, фільтрації та аналітики."""

    config: AppConfig = field(default_factory=AppConfig)
    _tasks: dict[int, Task] = field(default_factory=dict)

    def add_task(self, task: Task) -> None:
        """Додає нове завдання на дошку з перевіркою конфігурації та дублікатів."""
        if task.task_id in self._tasks:
            raise TaskValidationError(
                "task_id", f"Task with id={task.task_id} already exists"
            )
        if task.status not in self.config.allowed_statuses:
            raise TaskValidationError(
                "status", f"Status '{task.status}' is not allowed by board config"
            )
        if task.priority not in self.config.allowed_priorities:
            raise TaskValidationError(
                "priority", f"Priority '{task.priority}' is not allowed by board config"
            )
        if task.estimate_hours > self.config.max_estimate_hours:
            raise TaskValidationError(
                "estimate_hours",
                f"Estimate {task.estimate_hours} exceeds max {self.config.max_estimate_hours}",
            )
        self._tasks[task.task_id] = task

    def get_task(self, task_id: int) -> Task:
        """Повертає завдання за ID або піднімає TaskNotFoundError."""
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id)
        return self._tasks[task_id]

    def search_by_title(self, query: str) -> list[Task]:
        """Пошук завдань за підрядком у назві (регістронезалежний)."""
        cleaned = query.strip().lower()
        if not cleaned:
            return []
        return [t for t in self._tasks.values() if cleaned in t.title.lower()]

    def filter_by_priority(self, priority: str) -> list[Task]:
        """Фільтрація завдань за пріоритетом."""
        norm = validate_priority(priority, self.config.allowed_priorities)
        return [t for t in self._tasks.values() if t.priority == norm]

    def filter_by_status(self, status: str) -> list[Task]:
        """Фільтрація завдань за статусом."""
        norm = validate_status(status, self.config.allowed_statuses)
        return [t for t in self._tasks.values() if t.status == norm]

    @property
    def all_tasks(self) -> list[Task]:
        """Список усіх завдань у порядку додавання."""
        return list(self._tasks.values())

    def __len__(self) -> int:
        return len(self._tasks)

    def __contains__(self, task_id: int) -> bool:
        return task_id in self._tasks

    def count_completed(self) -> int:
        """Кількість завершених завдань (status == 'done')."""
        return sum(1 for t in self._tasks.values() if t.is_completed)

    def count_incomplete(self) -> int:
        """Кількість незавершених завдань (status != 'done')."""
        return sum(1 for t in self._tasks.values() if not t.is_completed)

    def completion_rate(self) -> float:
        """Відсоток виконання завдань (від 0.0 до 100.0)."""
        if not self._tasks:
            return 0.0
        return (self.count_completed() / len(self._tasks)) * 100.0

    def average_estimate_hours(self) -> float:
        """Середня оцінка часу за всіма завданнями на дошці."""
        if not self._tasks:
            return 0.0
        return sum(t.estimate_hours for t in self._tasks.values()) / len(self._tasks)
