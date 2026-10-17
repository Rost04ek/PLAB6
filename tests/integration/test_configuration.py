"""Інтеграційні тести конфігурації (JSON/YAML/ENV) разом із TaskBoard та TaskService."""

import json
from pathlib import Path
from unittest.mock import Mock
import pytest

from application.config import load_config_from_json
from application.models import TaskBoard
from application.protocols import Notifier
from application.repositories import InMemoryTaskRepository
from application.services import TaskService


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
