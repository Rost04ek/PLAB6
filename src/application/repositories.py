from typing import Protocol
from application.models import Task

class Notifier(Protocol):
    def send_alert(self, task_id: int, message: str) -> None:
        ... # pragma: no cover

class TaskRepository(Protocol):
    def save(self, task: Task) -> bool:
        ... # pragma: no cover

class AsyncTaskRepository:
    async def fetch_remote_task(self, task_id: int) -> dict:
        pass # pragma: no cover
