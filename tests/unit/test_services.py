"""Модульні тести сервісів із використанням Mock, create_autospec, side_effect та AsyncMock."""

from unittest.mock import AsyncMock, Mock, create_autospec
import pytest

from task_manager.exceptions import (
    InvalidStatusTransitionError,
    NotificationError,
    TaskNotFoundError,
)
from task_manager.models import Task
from task_manager.protocols import AsyncTaskRepository, Notifier, TaskRepository
from task_manager.repositories import InMemoryTaskRepository
from task_manager.services import AsyncTaskService, TaskService


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
    repo_mock.save.assert_called_once_with(created)
    notifier_mock.notify.assert_called_once_with(
        "dev@example.com",
        "Task #10 Created",
        "Assigned task 'Оновити залежності' with priority 'high'",
    )


def test_create_task_uses_monkeypatched_default_priority(
    monkeypatch: pytest.MonkeyPatch,
    fake_repository: InMemoryTaskRepository,
) -> None:
    """Перевірка підміни функції у сервісі через monkeypatch.setattr та використання FakeRepository."""
    monkeypatch.setattr(
        "task_manager.services.get_default_priority",
        lambda: "critical",
    )
    notifier_mock = create_autospec(Notifier, instance=True)
    service = TaskService(repository=fake_repository, notifier=notifier_mock)

    task = service.create_task(task_id=55, title="Терміновий хотфікс")

    assert task.priority == "critical"
    assert fake_repository.get_by_id(55) == task
    notifier_mock.notify.assert_not_called()


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
            new_status="done",  # з 'todo' одразу в 'done' заборонено
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

    # Налаштовуємо послідовні повернення для fetch_all_by_status("done") та ("todo")
    async_repo.fetch_all_by_status.side_effect = [
        [task_factory(status="done"), task_factory(status="done")],
        [task_factory(status="todo")],
    ]
    ratio = await async_service.calculate_remote_completion_ratio()
    assert ratio == pytest.approx(2 / 3)

    # Перевірка для порожнього хмарного репозиторію
    async_repo.fetch_all_by_status.side_effect = [[], []]
    empty_ratio = await async_service.calculate_remote_completion_ratio()
    assert empty_ratio == pytest.approx(0.0)
