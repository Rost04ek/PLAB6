"""Бізнес-логіка: синхронний та асинхронний сервіси керування завданнями."""

from task_manager.config import get_default_priority
from task_manager.exceptions import TaskNotFoundError
from task_manager.models import Task
from task_manager.protocols import AsyncTaskRepository, Notifier, TaskRepository


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
