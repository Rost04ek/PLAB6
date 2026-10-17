"""Інтеграційні тести: SQLiteTaskRepository та асинхронний workflow."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock
import pytest

from application.exporters import export_tasks_to_json, import_tasks_from_csv
from application.models import BugTask, FeatureTask, TaskBoard
from application.protocols import AsyncTaskRepository, Notifier
from application.repositories import SQLiteTaskRepository
from application.services import AsyncTaskService, TaskService


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
