"""Модуль конфігурації дозволених статусів, пріоритетів та параметрів середовища."""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path

from task_manager.exceptions import TaskValidationError

DEFAULT_STATUSES: tuple[str, ...] = ("todo", "in_progress", "review", "done", "cancelled")
DEFAULT_PRIORITIES: tuple[str, ...] = ("low", "medium", "high", "critical")


def get_default_priority() -> str:
    """Повертає пріоритет за замовчуванням зі змінної середовища або 'medium'."""
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
    env_name = os.getenv("APP_ENV", "development").strip()

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
