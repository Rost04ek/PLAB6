"""Модульні тести конфігурації з використанням monkeypatch та tmp_path."""

from pathlib import Path
import pytest

from task_manager.config import (
    AppConfig,
    DEFAULT_PRIORITIES,
    DEFAULT_STATUSES,
    get_default_priority,
    load_config_from_env,
    load_config_from_json,
)
from task_manager.exceptions import TaskValidationError


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


def test_load_config_from_json_file(tmp_path: Path) -> None:
    """Перевірка завантаження конфігурації з JSON-файлу у тимчасовому каталозі tmp_path."""
    config_file = tmp_path / "config.json"
    config_file.write_text(
        '{"allowed_statuses": ["todo", "done"], "allowed_priorities": ["medium", "critical"], "max_estimate_hours": 120, "environment": "ci"}',
        encoding="utf-8",
    )

    cfg = load_config_from_json(config_file)
    assert cfg.allowed_statuses == ("todo", "done")
    assert cfg.allowed_priorities == ("medium", "critical")
    assert cfg.max_estimate_hours == pytest.approx(120.0)
    assert cfg.environment == "ci"
