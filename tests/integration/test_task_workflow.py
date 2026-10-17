"""Інтеграційні тести: перевірка взаємодії компонентів системи керування завданнями."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock
import pytest

from task_manager.config import load_config_from_env, load_config_from_json
from task_manager.exporters import export_tasks_to_json, import_tasks_from_csv
from task_manager.models import BugTask, FeatureTask, TaskBoard
from task_manager.protocols import AsyncTaskRepository, Notifier
from task_manager.repositories import InMemoryTaskRepository, SQLiteTaskRepository
from task_manager.services import AsyncTaskService, TaskService


@pytest.mark.integration
def test_full_csv_import_status_transition_and_json_export_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Інтеграційний тест 1:
    Env Config → CSV Import → TaskBoard → Service Status Transitions → JSON Export.
    """
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

    # Переводимо завдання 102 та 103 у статус 'done'
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


@pytest.mark.integration
def test_sqlite_repository_and_task_service_integration(
    sqlite_repo: SQLiteTaskRepository,
) -> None:
    """
    Інтеграційний тест 2:
    TaskService + реальний SQLiteTaskRepository (з фікстурою yield teardown) + Notifier.
    """
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
def test_json_config_driven_board_and_repository_sync(tmp_path: Path) -> None:
    """
    Інтеграційний тест 3:
    Завантаження JSON-конфігурації → створення завдань через TaskService → агрегація на TaskBoard.
    """
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_async_workflow_import_sync_and_export(tmp_path: Path) -> None:
    """
    Інтеграційний тест 4:
    CSV Import → AsyncTaskService хмарна синхронізація та завершення → JSON Export.
    """
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
