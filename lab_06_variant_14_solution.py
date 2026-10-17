"""
Лабораторна робота №6. Автоматизоване тестування Python-програм
Студент: Козачок Ростислав Михайлович (Група ФЕП-23с)
Варіант: 14 — Система керування завданнями (Task, BugTask, FeatureTask, TaskBoard)
Повний модуль Production Code + Test Suite (pytest, Mock, MagicMock, AsyncMock, tmp_path, monkeypatch)
"""

from collections.abc import Callable, Generator
import csv
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any, Protocol, runtime_checkable
from unittest.mock import AsyncMock, MagicMock, Mock, create_autospec, patch
import uuid

import pytest

# Реєструємо поточний модуль у sys.modules під іменами пакетів для роботи @patch та monkeypatch.setattr
_current_module = sys.modules[__name__]
for _alias in (
    "application",
    "application.exceptions",
    "application.config",
    "application.models",
    "application.protocols",
    "application.repositories",
    "application.services",
    "application.exporters",
    "task_manager",
    "task_manager.exceptions",
    "task_manager.config",
    "task_manager.models",
    "task_manager.protocols",
    "task_manager.repositories",
    "task_manager.services",
    "task_manager.exporters",
):
    sys.modules.setdefault(_alias, _current_module)

exporters_mod = _current_module
services_mod = _current_module


# ==================== src/application/exceptions.py ====================
"""Кастомні винятки для системи керування завданнями (Варіант 14)."""


class TaskError(Exception):
    """Базовий виняток системи керування завданнями."""


class RecordValidationError(TaskError):
    """Виняток валідації запису або поля моделі."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"Validation error in '{field}': {message}")
        self.field = field
        self.details = message


class TaskValidationError(RecordValidationError):
    """Виняток при некоректних значеннях полів завдання (priority, status, estimate_hours)."""


class InvalidStatusTransitionError(TaskError):
    """Виняток при спробі виконати недопустимий перехід між статусами завдання."""

    def __init__(self, current_status: str, target_status: str) -> None:
        super().__init__(
            f"Cannot transition task status from '{current_status}' to '{target_status}'"
        )
        self.current_status = current_status
        self.target_status = target_status


class TaskNotFoundError(TaskError):
    """Виняток, коли завдання з вказаним ID не знайдено."""

    def __init__(self, task_id: int) -> None:
        super().__init__(f"Task with id={task_id} was not found")
        self.task_id = task_id


class DataImportError(TaskError):
    """Виняток під час імпорту даних із зовнішнього файлу."""

    def __init__(self, line_number: int, reason: str) -> None:
        super().__init__(f"CSV import error at line {line_number}: {reason}")
        self.line_number = line_number
        self.reason = reason


class TaskImportError(DataImportError):
    """Виняток під час імпорту завдань із CSV."""


class NotificationError(TaskError):
    """Виняток при збої зовнішнього сервісу сповіщень."""


# ==================== src/application/config.py ====================
"""Модуль конфігурації дозволених статусів, пріоритетів та параметрів середовища."""

from dataclasses import dataclass
import json
import os
from pathlib import Path


DEFAULT_STATUSES: tuple[str, ...] = ("todo", "in_progress", "review", "done", "cancelled")
DEFAULT_PRIORITIES: tuple[str, ...] = ("low", "medium", "high", "critical")


def get_environment() -> str:
    """Повертає назву середовища зі змінної APP_ENV або 'development'."""
    return os.getenv("APP_ENV", "development").strip()


def get_default_priority() -> str:
    """Повертає пріоритет за замовчуванням зі змінної TASK_DEFAULT_PRIORITY або 'medium'."""
    return os.getenv("TASK_DEFAULT_PRIORITY", "medium").strip().lower()


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Конфігурація системи керування завданнями."""

    allowed_statuses: tuple[str, ...] = DEFAULT_STATUSES
    allowed_priorities: tuple[str, ...] = DEFAULT_PRIORITIES
    max_estimate_hours: float = 200.0
    environment: str = "development"

    def __post_init__(self) -> None:
        if not self.allowed_statuses:
            raise TaskValidationError("allowed_statuses", "Allowed statuses cannot be empty")
        if not self.allowed_priorities:
            raise TaskValidationError("allowed_priorities", "Allowed priorities cannot be empty")
        if self.max_estimate_hours <= 0:
            raise TaskValidationError("max_estimate_hours", "Max estimate hours must be positive")


def load_config_from_env() -> AppConfig:
    """Завантажує конфігурацію зі змінних середовища ОС."""
    raw_statuses = os.getenv("TASK_ALLOWED_STATUSES", "")
    raw_priorities = os.getenv("TASK_ALLOWED_PRIORITIES", "")
    raw_max_hours = os.getenv("TASK_MAX_ESTIMATE_HOURS", "200.0")
    env_name = get_environment()

    statuses = (
        tuple(s.strip().lower() for s in raw_statuses.split(",") if s.strip())
        if raw_statuses.strip()
        else DEFAULT_STATUSES
    )
    priorities = (
        tuple(p.strip().lower() for p in raw_priorities.split(",") if p.strip())
        if raw_priorities.strip()
        else DEFAULT_PRIORITIES
    )

    try:
        max_hours = float(raw_max_hours)
    except ValueError as err:
        raise TaskValidationError("TASK_MAX_ESTIMATE_HOURS", "Must be a valid float") from err

    return AppConfig(
        allowed_statuses=statuses,
        allowed_priorities=priorities,
        max_estimate_hours=max_hours,
        environment=env_name,
    )


def load_config_from_json(path: Path) -> AppConfig:
    """Завантажує конфігурацію з JSON-файлу."""
    data = json.loads(path.read_text(encoding="utf-8"))
    statuses = tuple(data.get("allowed_statuses", DEFAULT_STATUSES))
    priorities = tuple(data.get("allowed_priorities", DEFAULT_PRIORITIES))
    max_hours = float(data.get("max_estimate_hours", 200.0))
    environment = str(data.get("environment", "production"))
    return AppConfig(
        allowed_statuses=statuses,
        allowed_priorities=priorities,
        max_estimate_hours=max_hours,
        environment=environment,
    )


def load_config_from_yaml(path: Path) -> AppConfig:
    """Завантажує конфігурацію з простого YAML-файлу (key: value або списки)."""
    parsed: dict[str, object] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, val = [part.strip() for part in line.split(":", 1)]
        if val.startswith("[") and val.endswith("]"):
            items = [x.strip().strip() for x in val[1:-1].split(",") if x.strip()]
            parsed[key] = items
        else:
            parsed[key] = val.strip()

    statuses = tuple(parsed.get("allowed_statuses", DEFAULT_STATUSES))  # type: ignore[arg-type]
    priorities = tuple(parsed.get("allowed_priorities", DEFAULT_PRIORITIES))  # type: ignore[arg-type]
    max_hours = float(str(parsed.get("max_estimate_hours", "200.0")))
    environment = str(parsed.get("environment", "production"))
    return AppConfig(
        allowed_statuses=statuses,
        allowed_priorities=priorities,
        max_estimate_hours=max_hours,
        environment=environment,
    )


# ==================== src/application/models.py ====================
"""Доменні моделі: Task, BugTask, FeatureTask та TaskBoard."""

from dataclasses import dataclass, field
from typing import Any

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


# ==================== src/application/protocols.py ====================
"""Протоколи (інтерфейси) для репозиторіїв та зовнішніх сервісів."""

from typing import Protocol, runtime_checkable



@runtime_checkable
class TaskRepository(Protocol):
    """Синхронний інтерфейс репозиторію завдань."""

    def save(self, task: Task) -> None:
        ...

    def get_by_id(self, task_id: int) -> Task | None:
        ...

    def list_all(self) -> list[Task]:
        ...


@runtime_checkable
class Notifier(Protocol):
    """Інтерфейс сервісу сповіщень."""

    def notify(self, recipient: str, subject: str, message: str) -> bool:
        ...


@runtime_checkable
class AsyncTaskRepository(Protocol):
    """Асинхронний інтерфейс репозиторію завдань."""

    async def fetch_by_id(self, task_id: int) -> Task | None:
        ...

    async def save_async(self, task: Task) -> str:
        ...

    async def fetch_all_by_status(self, status: str) -> list[Task]:
        ...


# ==================== src/application/repositories.py ====================
"""Реалізації репозиторіїв для збереження завдань (InMemory та SQLite)."""

from pathlib import Path
import sqlite3



class InMemoryTaskRepository:
    """In-memory реалізація репозиторію завдань (FakeRepository)."""

    def __init__(self) -> None:
        self._storage: dict[int, Task] = {}

    def save(self, task: Task) -> None:
        self._storage[task.task_id] = task

    def get_by_id(self, task_id: int) -> Task | None:
        return self._storage.get(task_id)

    def list_all(self) -> list[Task]:
        return list(self._storage.values())


class SQLiteTaskRepository:
    """Реалізація репозиторію завдань на базі вбудованої СУБД SQLite."""

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._create_table()

    def _create_table(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id INTEGER PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    estimate_hours REAL NOT NULL,
                    extra_field TEXT NOT NULL
                )
                """
            )

    def save(self, task: Task) -> None:
        extra = ""
        if isinstance(task, BugTask):
            extra = f"{task.severity}:{task.environment}"
        elif isinstance(task, FeatureTask):
            extra = f"{task.story_points}:{task.epic}"

        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO tasks
                (task_id, task_type, title, priority, status, estimate_hours, extra_field)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.task_type,
                    task.title,
                    task.priority,
                    task.status,
                    task.estimate_hours,
                    extra,
                ),
            )

    def get_by_id(self, task_id: int) -> Task | None:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT task_id, task_type, title, priority, status, estimate_hours, extra_field FROM tasks WHERE task_id = ?",
            (task_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_task(row)

    def list_all(self) -> list[Task]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT task_id, task_type, title, priority, status, estimate_hours, extra_field FROM tasks ORDER BY task_id"
        )
        return [self._row_to_task(r) for r in cur.fetchall()]

    @staticmethod
    def _row_to_task(row: tuple) -> Task:
        t_id, t_type, title, priority, status, estimate, extra = row
        if t_type == "bug":
            sev, env = extra.split(":", 1)
            return BugTask(
                task_id=t_id,
                title=title,
                priority=priority,
                status=status,
                estimate_hours=estimate,
                severity=sev,
                environment=env,
            )
        if t_type == "feature":
            pts, epic = extra.split(":", 1)
            return FeatureTask(
                task_id=t_id,
                title=title,
                priority=priority,
                status=status,
                estimate_hours=estimate,
                story_points=int(pts),
                epic=epic,
            )
        return Task(
            task_id=t_id,
            title=title,
            priority=priority,
            status=status,
            estimate_hours=estimate,
        )

    def close(self) -> None:
        self._conn.close()


# ==================== src/application/services.py ====================
"""Бізнес-логіка: синхронний та асинхронний сервіси керування завданнями."""

from datetime import datetime
from typing import Any
import uuid



def generate_audit_id() -> str:
    """Генерує унікальний ID запису аудиту через uuid4."""
    return str(uuid.uuid4())


def get_current_timestamp() -> str:
    """Повертає поточну позначку часу ISO 8601."""
    return datetime.now().isoformat()


def send_audit_log(event_name: str, task_id: int) -> dict[str, Any]:
    """Зовнішня функція відправки аудит-логу (для демонстрації unittest.mock.patch)."""
    return {
        "audit_id": generate_audit_id(),
        "timestamp": get_current_timestamp(),
        "event": event_name,
        "task_id": task_id,
    }


class TaskService:
    """Сервіс керування завданнями із зовнішніми залежностями (Repository та Notifier)."""

    def __init__(self, repository: TaskRepository, notifier: Notifier) -> None:
        self._repository = repository
        self._notifier = notifier

    def create_task(
        self,
        task_id: int,
        title: str,
        priority: str | None = None,
        estimate_hours: float = 1.0,
        assignee_email: str | None = None,
    ) -> Task:
        """Створює нове завдання, зберігає у репозиторій та надсилає сповіщення."""
        resolved_priority = priority if priority is not None else get_default_priority()
        task = Task(
            task_id=task_id,
            title=title,
            priority=resolved_priority,
            status="todo",
            estimate_hours=estimate_hours,
        )
        self._repository.save(task)
        send_audit_log("task_created", task.task_id)

        if assignee_email:
            self._notifier.notify(
                assignee_email,
                f"Task #{task.task_id} Created",
                f"Assigned task '{task.title}' with priority '{task.priority}'",
            )
        return task

    def transition_task_status(
        self,
        task_id: int,
        new_status: str,
        notify_email: str | None = None,
    ) -> Task:
        """Змінює статус існуючого завдання, зберігає зміни та сповіщає виконавця."""
        task = self._repository.get_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)

        old_status = task.status
        task.change_status(new_status)
        self._repository.save(task)
        send_audit_log("status_changed", task.task_id)

        if notify_email and old_status != task.status:
            self._notifier.notify(
                notify_email,
                f"Task #{task.task_id} Status Updated",
                f"Status changed from '{old_status}' to '{task.status}'",
            )
        return task


class AsyncTaskService:
    """Асинхронний сервіс для роботи з віддаленим асинхронним сховищем завдань."""

    def __init__(self, async_repo: AsyncTaskRepository) -> None:
        self._async_repo = async_repo

    async def sync_task_to_cloud(self, task: Task) -> str:
        """Асинхронно зберігає завдання у хмарному репозиторії та повертає sync token."""
        token = await self._async_repo.save_async(task)
        return token

    async def complete_remote_task(self, task_id: int) -> Task:
        """Завантажує завдання асинхронно, переводить у статус 'done' та зберігає."""
        task = await self._async_repo.fetch_by_id(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)

        if task.status == "todo":
            task.change_status("in_progress")
        if task.status != "done":
            task.change_status("done")

        await self._async_repo.save_async(task)
        return task

    async def calculate_remote_completion_ratio(self) -> float:
        """Обчислює частку виконаних завдань серед активних та завершених у хмарі."""
        done_tasks = await self._async_repo.fetch_all_by_status("done")
        todo_tasks = await self._async_repo.fetch_all_by_status("todo")
        total = len(done_tasks) + len(todo_tasks)
        if total == 0:
            return 0.0
        return len(done_tasks) / total


# ==================== src/application/exporters.py ====================
"""Імпорт завдань із CSV та атомарний експорт у JSON."""

import csv
import json
from pathlib import Path
from typing import Any



def import_tasks_from_csv(csv_path: Path, board: TaskBoard | None = None) -> list[Task]:
    """Читає завдання з CSV-файлу, валідує записи та опціонально додає їх у TaskBoard."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    imported: list[Task] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required_cols = {"id", "type", "title", "priority", "status", "estimate_hours"}
        if reader.fieldnames is None or not required_cols.issubset(set(reader.fieldnames)):
            raise TaskImportError(1, "Missing required CSV header columns")

        for line_num, row in enumerate(reader, start=2):
            try:
                raw_id = row.get("id", "")
                raw_est = row.get("estimate_hours", "")
                task_id = int(raw_id)
                estimate = float(raw_est)
            except (ValueError, TypeError) as err:
                raise TaskImportError(
                    line_num, f"Invalid numeric field in row: {row}"
                ) from err

            task_type = (row.get("type") or "task").strip().lower()
            title = row.get("title") or ""
            priority = row.get("priority") or "medium"
            status = row.get("status") or "todo"

            try:
                if task_type == "bug":
                    severity = row.get("extra") or "major"
                    task: Task = BugTask(
                        task_id=task_id,
                        title=title,
                        priority=priority,
                        status=status,
                        estimate_hours=estimate,
                        severity=severity,
                    )
                elif task_type == "feature":
                    pts_str = row.get("extra") or "3"
                    task = FeatureTask(
                        task_id=task_id,
                        title=title,
                        priority=priority,
                        status=status,
                        estimate_hours=estimate,
                        story_points=int(pts_str),
                    )
                elif task_type == "task":
                    task = Task(
                        task_id=task_id,
                        title=title,
                        priority=priority,
                        status=status,
                        estimate_hours=estimate,
                    )
                else:
                    raise TaskValidationError("type", f"Unknown task type '{task_type}'")

                if board is not None:
                    board.add_task(task)
                imported.append(task)
            except (TaskValidationError, ValueError) as err:
                raise TaskImportError(line_num, str(err)) from err

    return imported


def _replace_atomic(temp_path: Path, output_path: Path) -> None:
    """Допоміжна функція атомарної заміни файлу."""
    temp_path.replace(output_path)


def export_tasks_to_json(board: TaskBoard, output_path: Path) -> None:
    """Виконує атомарний експорт стану TaskBoard у JSON-файл через тимчасовий файл."""
    payload: dict[str, Any] = {
        "environment": board.config.environment,
        "total_tasks": len(board),
        "completed_tasks": board.count_completed(),
        "incomplete_tasks": board.count_incomplete(),
        "completion_rate": round(board.completion_rate(), 2),
        "average_estimate_hours": round(board.average_estimate_hours(), 2),
        "tasks": [t.to_dict() for t in board.all_tasks],
    }

    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        temp_path.write_text(serialized, encoding="utf-8")
        _replace_atomic(temp_path, output_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


class TempExportSession:
    """Контекстний менеджер для тимчасового буфера експорту з гарантованим очищенням."""

    def __init__(self, temp_file: Path) -> None:
        self.temp_file = temp_file
        self.is_open = False

    def __enter__(self) -> "TempExportSession":
        self.temp_file.write_text("", encoding="utf-8")
        self.is_open = True
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        self.is_open = False
        if self.temp_file.exists():
            self.temp_file.unlink()
        return False


# ==================== tests/conftest.py ====================
"""Спільні fixtures для всього test suite (tests/conftest.py)."""

from collections.abc import Callable, Generator
from pathlib import Path
import pytest



@pytest.fixture(autouse=True)
def reset_env_between_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Autouse fixture: гарантує ізоляцію змінних середовища між усіма тестами."""
    monkeypatch.delenv("TASK_DEFAULT_PRIORITY", raising=False)


@pytest.fixture(scope="module")
def default_board_config() -> AppConfig:
    """Fixture зі scope='module' для незмінної стандартної конфігурації дошки."""
    return AppConfig()


@pytest.fixture
def sample_task() -> Task:
    """Базова фікстура звичайного завдання."""
    return Task(
        task_id=1,
        title="Написати документацію API",
        priority="medium",
        status="todo",
        estimate_hours=4.5,
    )


@pytest.fixture
def sample_bug() -> BugTask:
    """Фікстура завдання-багу (BugTask)."""
    return BugTask(
        task_id=2,
        title="Виправити витік пам'яті у воркері",
        priority="critical",
        status="in_progress",
        estimate_hours=6.0,
        severity="blocker",
        environment="prod",
    )


@pytest.fixture
def sample_feature() -> FeatureTask:
    """Фікстура завдання-фічі (FeatureTask)."""
    return FeatureTask(
        task_id=3,
        title="Додати підтримку OAuth2 авторизації",
        priority="high",
        status="done",
        estimate_hours=12.0,
        story_points=8,
        epic="Security",
    )


@pytest.fixture
def populated_board(
    default_board_config: AppConfig,
    sample_task: Task,
    sample_bug: BugTask,
    sample_feature: FeatureTask,
) -> TaskBoard:
    """Фікстура заповненої дошки завдань (TaskBoard) із трьома різними завданнями."""
    board = TaskBoard(config=default_board_config)
    board.add_task(sample_task)
    board.add_task(sample_bug)
    board.add_task(sample_feature)
    return board


@pytest.fixture
def task_factory() -> Callable[..., Task]:
    """Fixture factory для гнучкого створення екземплярів Task із кастомними параметрами."""
    counter = 100

    def _create_task(
        *,
        task_id: int | None = None,
        title: str = "Тестове завдання",
        priority: str = "medium",
        status: str = "todo",
        estimate_hours: float = 2.0,
    ) -> Task:
        nonlocal counter
        if task_id is None:
            counter += 1
            task_id = counter
        return Task(
            task_id=task_id,
            title=title,
            priority=priority,
            status=status,
            estimate_hours=estimate_hours,
        )

    return _create_task


@pytest.fixture
def fake_repository() -> InMemoryTaskRepository:
    """Фікстура, що повертає ізольований Fake-репозиторій у пам'яті."""
    return InMemoryTaskRepository()


@pytest.fixture
def sqlite_repo(tmp_path: Path) -> Generator[SQLiteTaskRepository, None, None]:
    """Фікстура з teardown через yield для SQLiteTaskRepository."""
    db_file = tmp_path / "tasks_test.db"
    repo = SQLiteTaskRepository(db_file)
    yield repo
    repo.close()


@pytest.fixture(params=["low", "medium", "high", "critical"])
def valid_priority(request: pytest.FixtureRequest) -> str:
    """Параметризована фікстура для перевірки всіх стандартних пріоритетів."""
    return str(request.param)


# ==================== tests/unit/test_models.py ====================
"""Модульні (Unit) тести для моделей Task, BugTask, FeatureTask та TaskBoard."""

import pytest



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


# ==================== tests/unit/test_validators.py ====================
"""Модульні тести валідації полів, граничних значень (boundary) та переходів статусів."""

import pytest

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


# ==================== tests/unit/test_configuration.py ====================
"""Модульні тести конфігурації з використанням monkeypatch та tmp_path."""

from pathlib import Path
import pytest



def test_load_config_from_env_custom_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Перевірка читання конфігурації зі змінних середовища через monkeypatch.setenv."""
    monkeypatch.setenv("TASK_ALLOWED_STATUSES", "todo, in_progress, done")
    monkeypatch.setenv("TASK_ALLOWED_PRIORITIES", "low, high")
    monkeypatch.setenv("TASK_MAX_ESTIMATE_HOURS", "80.5")
    monkeypatch.setenv("APP_ENV", "staging")

    cfg = load_config_from_env()

    assert cfg.allowed_statuses == ("todo", "in_progress", "done")
    assert cfg.allowed_priorities == ("low", "high")
    assert cfg.max_estimate_hours == pytest.approx(80.5)
    assert cfg.environment == "staging"
    assert get_environment() == "staging"


def test_load_config_defaults_when_env_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Перевірка значень за замовчуванням після видалення змінних через monkeypatch.delenv."""
    monkeypatch.delenv("TASK_ALLOWED_STATUSES", raising=False)
    monkeypatch.delenv("TASK_ALLOWED_PRIORITIES", raising=False)
    monkeypatch.delenv("TASK_MAX_ESTIMATE_HOURS", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("TASK_DEFAULT_PRIORITY", raising=False)

    cfg = load_config_from_env()

    assert cfg.allowed_statuses == DEFAULT_STATUSES
    assert cfg.allowed_priorities == DEFAULT_PRIORITIES
    assert cfg.max_estimate_hours == pytest.approx(200.0)
    assert cfg.environment == "development"
    assert get_default_priority() == "medium"


def test_load_config_invalid_float_in_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Перевірка генерації TaskValidationError із ланцюжком винятків при некоректному числі в env."""
    monkeypatch.setenv("TASK_MAX_ESTIMATE_HOURS", "not_a_number")

    with pytest.raises(TaskValidationError, match="Must be a valid float") as exc_info:
        load_config_from_env()

    assert isinstance(exc_info.value.__cause__, ValueError)


def test_app_config_validation_errors() -> None:
    """Перевірка валідації порожніх списків статусів/пріоритетів або від'ємного ліміту годин."""
    with pytest.raises(TaskValidationError, match="cannot be empty"):
        AppConfig(allowed_statuses=())

    with pytest.raises(TaskValidationError, match="cannot be empty"):
        AppConfig(allowed_priorities=())

    with pytest.raises(TaskValidationError, match="must be positive"):
        AppConfig(max_estimate_hours=0.0)


def test_load_config_from_json_and_yaml_files(tmp_path: Path) -> None:
    """Перевірка завантаження конфігурації з JSON та YAML файлів у tmp_path."""
    config_json = tmp_path / "config.json"
    config_json.write_text(
        '{"allowed_statuses": ["todo", "done"], "allowed_priorities": ["medium", "critical"], "max_estimate_hours": 120, "environment": "ci"}',
        encoding="utf-8",
    )
    cfg_j = load_config_from_json(config_json)
    assert cfg_j.allowed_statuses == ("todo", "done")
    assert cfg_j.allowed_priorities == ("medium", "critical")
    assert cfg_j.max_estimate_hours == pytest.approx(120.0)
    assert cfg_j.environment == "ci"

    config_yaml = tmp_path / "config.yaml"
    config_yaml.write_text(
        "# Task Manager YAML Configuration\n"
        "allowed_statuses: [todo, in_progress, done]\n"
        "allowed_priorities: [low, medium, high]\n"
        "max_estimate_hours: 150.0\n"
        "environment: production\n",
        encoding="utf-8",
    )
    cfg_y = load_config_from_yaml(config_yaml)
    assert cfg_y.allowed_statuses == ("todo", "in_progress", "done")
    assert cfg_y.allowed_priorities == ("low", "medium", "high")
    assert cfg_y.max_estimate_hours == pytest.approx(150.0)
    assert cfg_y.environment == "production"


# ==================== tests/unit/test_exporters.py ====================
"""Модульні тести файлового імпорту CSV та експорту JSON через tmp_path і MagicMock."""

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest



def test_import_tasks_from_csv_valid(tmp_path: Path) -> None:
    """Тестування успішного імпорту завдань різних типів із CSV через tmp_path."""
    csv_file = tmp_path / "tasks.csv"
    csv_file.write_text(
        "id,type,title,priority,status,estimate_hours,extra\n"
        "1,task,Налаштувати CI,high,todo,3.5,\n"
        "2,bug,Виправити 500 помилку,critical,in_progress,5.0,blocker\n"
        "3,feature,Темна тема інтерфейсу,low,done,8.0,5\n",
        encoding="utf-8",
    )

    board = TaskBoard()
    tasks = import_tasks_from_csv(csv_file, board=board)

    assert len(tasks) == 3
    assert len(board) == 3
    assert isinstance(tasks[1], BugTask)
    assert tasks[1].severity == "blocker"
    assert isinstance(tasks[2], FeatureTask)
    assert tasks[2].story_points == 5


def test_import_csv_malformed_numeric_record_chains_exception(tmp_path: Path) -> None:
    """Перевірка обробки malformed CSV record та збереження оригінального ValueError у __cause__."""
    csv_file = tmp_path / "broken_numeric.csv"
    csv_file.write_text(
        "id,type,title,priority,status,estimate_hours,extra\n"
        "abc,task,Некоректний ID,medium,todo,2.0,\n",
        encoding="utf-8",
    )

    with pytest.raises(TaskImportError) as exc_info:
        import_tasks_from_csv(csv_file)

    assert isinstance(exc_info.value, DataImportError)
    assert exc_info.value.line_number == 2
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_import_csv_invalid_domain_data_and_missing_headers(tmp_path: Path) -> None:
    """Перевірка помилок при відсутніх стовпцях CSV, невідомому типі або невалідному статусі."""
    missing_file = tmp_path / "nonexistent.csv"
    with pytest.raises(FileNotFoundError):
        import_tasks_from_csv(missing_file)

    bad_header_csv = tmp_path / "bad_header.csv"
    bad_header_csv.write_text("id,title\n1,Test\n", encoding="utf-8")
    with pytest.raises(TaskImportError, match="Missing required CSV header"):
        import_tasks_from_csv(bad_header_csv)

    bad_type_csv = tmp_path / "bad_type.csv"
    bad_type_csv.write_text(
        "id,type,title,priority,status,estimate_hours,extra\n"
        "1,unknown_kind,Title,medium,todo,2.0,\n",
        encoding="utf-8",
    )
    with pytest.raises(TaskImportError) as exc_info:
        import_tasks_from_csv(bad_type_csv)
    assert isinstance(exc_info.value.__cause__, TaskValidationError)


def test_export_tasks_to_json_creates_valid_file(
    tmp_path: Path,
    populated_board: TaskBoard,
) -> None:
    """Перевірка експорту дошки завдань у JSON-файл через tmp_path."""
    output_file = tmp_path / "report.json"

    export_tasks_to_json(populated_board, output_file)

    assert output_file.exists()
    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert data["total_tasks"] == 3
    assert data["completed_tasks"] == 1
    assert data["incomplete_tasks"] == 2
    assert data["completion_rate"] == pytest.approx(33.33)
    assert len(data["tasks"]) == 3


def test_atomic_export_preserves_old_file_and_cleans_tmp_on_replace_failure(
    tmp_path: Path,
    populated_board: TaskBoard,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Перевірка атомарності експорту: якщо збій стається під час заміни файлу, .tmp видаляється, а старі дані цілі."""
    output_file = tmp_path / "atomic_report.json"
    output_file.write_text('{"status": "old_valid_data"}', encoding="utf-8")
    temp_file = output_file.with_suffix(".json.tmp")

    def broken_replace(src: Path, dst: Path) -> None:
        raise OSError("Simulated atomic replace failure")

    monkeypatch.setattr(exporters_mod, "_replace_atomic", broken_replace)

    with pytest.raises(OSError, match="Simulated atomic replace failure"):
        export_tasks_to_json(populated_board, output_file)

    assert output_file.read_text(encoding="utf-8") == '{"status": "old_valid_data"}'
    assert not temp_file.exists()


def test_atomic_export_when_serialization_fails_before_tmp_created(
    tmp_path: Path,
    populated_board: TaskBoard,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Перевірка гілки except, коли temp_path ще не створено (помилка у json.dumps)."""
    output_file = tmp_path / "early_fail.json"
    monkeypatch.setattr(json, "dumps", lambda *a, **kw: (_ for _ in ()).throw(ValueError("Bad JSON")))

    with pytest.raises(ValueError, match="Bad JSON"):
        export_tasks_to_json(populated_board, output_file)

    assert not output_file.exists()


def test_temp_export_session_context_manager_and_magic_mock(tmp_path: Path) -> None:
    """Перевірка контекстного менеджера TempExportSession (нормальний вихід, виняток та MagicMock)."""
    buf_path = tmp_path / "buffer.tmp"
    session = TempExportSession(buf_path)

    with session as active:
        assert active.is_open is True
        assert buf_path.exists()
    assert session.is_open is False
    assert not buf_path.exists()

    with pytest.raises(RuntimeError, match="Abort export"):
        with session:
            assert session.is_open is True
            raise RuntimeError("Abort export")
    assert not buf_path.exists()

    # Використання MagicMock для імітації магічних методів контекстного менеджера (__enter__ / __exit__)
    magic_stream = MagicMock()
    magic_stream.__enter__.return_value = magic_stream
    with magic_stream as s:
        s.write('{"ok": true}')
    magic_stream.__enter__.assert_called_once()
    magic_stream.write.assert_called_once_with('{"ok": true}')
    magic_stream.__exit__.assert_called_once()


# ==================== tests/unit/test_services.py ====================
"""Модульні тести сервісів із використанням Mock, MagicMock, patch, create_autospec, side_effect та AsyncMock."""

from unittest.mock import AsyncMock, MagicMock, Mock, create_autospec, patch
import pytest

def test_create_task_saves_and_notifies_with_mock() -> None:
    """Перевірка створення завдання та interaction assertion через Mock(spec=...)."""
    repo_mock = Mock(spec=TaskRepository)
    notifier_mock = Mock(spec=Notifier)
    notifier_mock.notify.return_value = True

    service = TaskService(repository=repo_mock, notifier=notifier_mock)

    created = service.create_task(
        task_id=10,
        title="Оновити залежності",
        priority="high",
        estimate_hours=2.5,
        assignee_email="dev@example.com",
    )

    assert created.task_id == 10
    assert created.priority == "high"
    repo_mock.save.assert_called_once()
    repo_mock.save.assert_called_once_with(created)
    notifier_mock.notify.assert_called_once_with(
        "dev@example.com",
        "Task #10 Created",
        "Assigned task 'Оновити залежності' with priority 'high'",
    )


@patch("application.services.send_audit_log")
def test_create_task_uses_patch_and_monkeypatch(
    mock_audit: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    fake_repository: InMemoryTaskRepository,
) -> None:
    """Перевірка unittest.mock.patch, monkeypatch.setattr та FakeRepository."""
    monkeypatch.setattr(
        services_mod,
        "get_default_priority",
        lambda: "critical",
    )
    notifier_mock = create_autospec(Notifier, instance=True)
    service = TaskService(repository=fake_repository, notifier=notifier_mock)

    task = service.create_task(task_id=55, title="Терміновий хотфікс")

    assert task.priority == "critical"
    assert fake_repository.get_by_id(55) == task
    mock_audit.assert_called_once_with("task_created", 55)
    notifier_mock.notify.assert_not_called()


def test_deterministic_time_and_uuid_via_monkeypatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Детерміноване тестування часу та генерації UUID через monkeypatch.setattr."""
    monkeypatch.setattr(services_mod, "generate_audit_id", lambda: "00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(services_mod, "get_current_timestamp", lambda: "2026-10-17T12:00:00")

    entry = send_audit_log("task_created", 1)
    assert entry == {
        "audit_id": "00000000-0000-0000-0000-000000000001",
        "timestamp": "2026-10-17T12:00:00",
        "event": "task_created",
        "task_id": 1,
    }
    assert isinstance(generate_audit_id(), str)
    assert "T" in get_current_timestamp()


def test_transition_status_success_with_return_value(sample_task: Task) -> None:
    """Перевірка зміни статусу через Mock із налаштованим return_value."""
    repo_mock = create_autospec(TaskRepository, instance=True)
    repo_mock.get_by_id.return_value = sample_task
    notifier_mock = create_autospec(Notifier, instance=True)
    notifier_mock.notify.return_value = True

    service = TaskService(repository=repo_mock, notifier=notifier_mock)

    updated = service.transition_task_status(
        task_id=1,
        new_status="in_progress",
        notify_email="qa@example.com",
    )

    assert updated.status == "in_progress"
    repo_mock.get_by_id.assert_called_once_with(1)
    repo_mock.save.assert_called_once_with(sample_task)
    notifier_mock.notify.assert_called_once_with(
        "qa@example.com",
        "Task #1 Status Updated",
        "Status changed from 'todo' to 'in_progress'",
    )


def test_transition_status_invalid_does_not_save_or_notify(sample_task: Task) -> None:
    """Negative path: при недопустимому переході статусу save та notify НЕ викликаються."""
    repo_mock = Mock(spec=TaskRepository)
    repo_mock.get_by_id.return_value = sample_task
    notifier_mock = Mock(spec=Notifier)

    service = TaskService(repository=repo_mock, notifier=notifier_mock)

    with pytest.raises(InvalidStatusTransitionError):
        service.transition_task_status(
            task_id=1,
            new_status="done",
            notify_email="qa@example.com",
        )

    repo_mock.save.assert_not_called()
    notifier_mock.notify.assert_not_called()


def test_transition_status_notifier_failure_via_side_effect(sample_task: Task) -> None:
    """Перевірка failure path зовнішнього сервісу сповіщень через side_effect."""
    repo_mock = Mock(spec=TaskRepository)
    repo_mock.get_by_id.return_value = sample_task
    notifier_mock = Mock(spec=Notifier)
    notifier_mock.notify.side_effect = NotificationError("SMTP gateway timeout")

    service = TaskService(repository=repo_mock, notifier=notifier_mock)

    with pytest.raises(NotificationError, match="SMTP gateway timeout"):
        service.transition_task_status(
            task_id=1,
            new_status="in_progress",
            notify_email="user@example.com",
        )

    repo_mock.save.assert_called_once_with(sample_task)


def test_transition_status_missing_task_raises_not_found() -> None:
    """Якщо репозиторій повертає None, сервіс піднімає TaskNotFoundError і не викликає notifier."""
    repo_mock = Mock(spec=TaskRepository)
    repo_mock.get_by_id.return_value = None
    notifier_mock = Mock(spec=Notifier)

    service = TaskService(repository=repo_mock, notifier=notifier_mock)

    with pytest.raises(TaskNotFoundError):
        service.transition_task_status(999, "in_progress", notify_email="a@b.com")

    notifier_mock.notify.assert_not_called()


@pytest.mark.asyncio
async def test_async_service_sync_and_complete_with_async_mock(
    sample_task: Task,
) -> None:
    """Тестування асинхронного репозиторію через AsyncMock та assert_awaited_once_with."""
    async_repo = AsyncMock(spec=AsyncTaskRepository)
    async_repo.fetch_by_id.return_value = sample_task
    async_repo.save_async.return_value = "SYNC-TOKEN-777"

    async_service = AsyncTaskService(async_repo)

    token = await async_service.sync_task_to_cloud(sample_task)
    assert token == "SYNC-TOKEN-777"
    async_repo.save_async.assert_awaited_once_with(sample_task)

    completed_task = await async_service.complete_remote_task(1)
    assert completed_task.status == "done"
    async_repo.fetch_by_id.assert_awaited_once_with(1)
    assert async_repo.save_async.await_count == 2


@pytest.mark.asyncio
async def test_async_service_error_and_ratio_calculation(
    task_factory,
) -> None:
    """Перевірка side_effect зі списком значень та винятком у AsyncMock."""
    async_repo = AsyncMock(spec=AsyncTaskRepository)
    async_repo.fetch_by_id.return_value = None

    async_service = AsyncTaskService(async_repo)

    with pytest.raises(TaskNotFoundError):
        await async_service.complete_remote_task(404)

    async_repo.fetch_all_by_status.side_effect = [
        [task_factory(status="done"), task_factory(status="done")],
        [task_factory(status="todo")],
    ]
    ratio = await async_service.calculate_remote_completion_ratio()
    assert ratio == pytest.approx(2 / 3)

    async_repo.fetch_all_by_status.side_effect = [[], []]
    empty_ratio = await async_service.calculate_remote_completion_ratio()
    assert empty_ratio == pytest.approx(0.0)


# ==================== tests/integration/test_import_export.py ====================
"""Інтеграційні тести імпорту CSV та експорту JSON."""

import json
from pathlib import Path
import pytest



@pytest.mark.integration
def test_full_csv_import_status_transition_and_json_export_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Інтеграційний тест: Env Config → CSV Import → TaskBoard → Status Transitions → JSON Export."""
    monkeypatch.setenv("APP_ENV", "integration_test")
    config = load_config_from_env()
    board = TaskBoard(config=config)

    csv_path = tmp_path / "incoming_tasks.csv"
    csv_path.write_text(
        "id,type,title,priority,status,estimate_hours,extra\n"
        "101,task,Підготувати реліз,high,todo,4.0,\n"
        "102,bug,Виправити верстку форми,medium,in_progress,2.5,minor\n"
        "103,feature,Експорт у PDF,critical,review,10.0,8\n",
        encoding="utf-8",
    )

    imported = import_tasks_from_csv(csv_path, board=board)
    assert len(imported) == 3

    board.get_task(102).change_status("done")
    board.get_task(103).change_status("done")

    json_path = tmp_path / "summary_report.json"
    export_tasks_to_json(board, json_path)

    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["environment"] == "integration_test"
    assert report["total_tasks"] == 3
    assert report["completed_tasks"] == 2
    assert report["incomplete_tasks"] == 1
    assert report["completion_rate"] == pytest.approx(66.67)
    assert report["average_estimate_hours"] == pytest.approx(5.5)


# ==================== tests/integration/test_configuration.py ====================
"""Інтеграційні тести конфігурації (JSON/YAML/ENV) разом із TaskBoard та TaskService."""

import json
from pathlib import Path
from unittest.mock import Mock
import pytest



@pytest.mark.integration
def test_json_config_driven_board_and_repository_sync(tmp_path: Path) -> None:
    """Інтеграційний тест: Завантаження JSON-конфігурації → TaskService → агрегація на TaskBoard."""
    cfg_file = tmp_path / "board_settings.json"
    cfg_file.write_text(
        json.dumps(
            {
                "allowed_statuses": ["todo", "in_progress", "done"],
                "allowed_priorities": ["low", "medium", "high"],
                "max_estimate_hours": 50.0,
                "environment": "staging",
            }
        ),
        encoding="utf-8",
    )

    cfg = load_config_from_json(cfg_file)
    repo = InMemoryTaskRepository()
    notifier = Mock(spec=Notifier)
    service = TaskService(repository=repo, notifier=notifier)

    service.create_task(1, "Модуль авторизації", priority="high", estimate_hours=8.0)
    service.create_task(2, "Модуль профілю", priority="medium", estimate_hours=4.0)
    service.transition_task_status(1, "in_progress")
    service.transition_task_status(1, "done")

    board = TaskBoard(config=cfg)
    for t in repo.list_all():
        board.add_task(t)

    assert board.count_completed() == 1
    assert board.count_incomplete() == 1
    assert len(board.filter_by_priority("high")) == 1


# ==================== tests/integration/test_application_flow.py ====================
"""Інтеграційні тести: SQLiteTaskRepository та асинхронний workflow."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock
import pytest



@pytest.mark.integration
def test_sqlite_repository_and_task_service_integration(
    sqlite_repo: SQLiteTaskRepository,
) -> None:
    """Інтеграційний тест: TaskService + реальний SQLiteTaskRepository (з yield teardown) + Notifier."""
    notifier = Mock(spec=Notifier)
    service = TaskService(repository=sqlite_repo, notifier=notifier)

    service.create_task(
        task_id=1,
        title="Налаштувати індекси БД",
        priority="high",
        estimate_hours=3.0,
        assignee_email="dba@example.com",
    )
    sqlite_repo.save(
        BugTask(
            task_id=2,
            title="Помилка серіалізації дати",
            priority="critical",
            status="todo",
            estimate_hours=1.5,
            severity="major",
        )
    )
    sqlite_repo.save(
        FeatureTask(
            task_id=3,
            title="Інтеграція з календарем",
            priority="medium",
            status="in_progress",
            estimate_hours=6.0,
            story_points=5,
        )
    )

    service.transition_task_status(1, "in_progress", notify_email="dba@example.com")
    service.transition_task_status(1, "done", notify_email="dba@example.com")

    persisted_tasks = sqlite_repo.list_all()
    assert len(persisted_tasks) == 3
    assert persisted_tasks[0].is_completed is True
    assert isinstance(persisted_tasks[1], BugTask)
    assert isinstance(persisted_tasks[2], FeatureTask)
    assert sqlite_repo.get_by_id(999) is None
    assert notifier.notify.call_count == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_workflow_import_sync_and_export(tmp_path: Path) -> None:
    """Інтеграційний тест: CSV Import → AsyncTaskService хмарна синхронізація → JSON Export."""
    csv_path = tmp_path / "async_tasks.csv"
    csv_path.write_text(
        "id,type,title,priority,status,estimate_hours,extra\n"
        "10,task,Асинхронний воркер,high,todo,5.0,\n"
        "20,bug,Таймаут вебсокета,critical,in_progress,3.0,blocker\n",
        encoding="utf-8",
    )

    board = TaskBoard()
    tasks = import_tasks_from_csv(csv_path, board=board)

    cloud_storage: dict[int, object] = {t.task_id: t for t in tasks}
    async_repo = AsyncMock(spec=AsyncTaskRepository)
    async_repo.fetch_by_id.side_effect = lambda tid: cloud_storage.get(tid)
    async_repo.save_async.side_effect = lambda t: f"SYNC-{t.task_id}"

    async_service = AsyncTaskService(async_repo)
    await async_service.complete_remote_task(10)
    await async_service.complete_remote_task(20)

    output_json = tmp_path / "async_result.json"
    export_tasks_to_json(board, output_json)

    data = json.loads(output_json.read_text(encoding="utf-8"))
    assert data["completed_tasks"] == 2
    assert data["completion_rate"] == pytest.approx(100.0)
