"""Модульні тести конфігурації з використанням monkeypatch та tmp_path."""

from pathlib import Path
import pytest

from application.config import (
    AppConfig,
    DEFAULT_PRIORITIES,
    DEFAULT_STATUSES,
    get_default_priority,
    get_environment,
    load_config_from_env,
    load_config_from_json,
    load_config_from_yaml,
)
from application.exceptions import TaskValidationError


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
