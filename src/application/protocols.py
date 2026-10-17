"""Протоколи (інтерфейси) для репозиторіїв та зовнішніх сервісів."""

from typing import Protocol, runtime_checkable

from application.models import Task


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
