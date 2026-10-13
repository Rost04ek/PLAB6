from typing import Protocol
from application.models import Task

class Notifier(Protocol):
    def send_alert(self, task_id: int, message: str) -> None: ...

class TaskRepository(Protocol):
    def save(self, task: Task) -> bool: ...

class AsyncTaskRepository:
    async def fetch_remote_task(self, task_id: int) -> dict:
        pass
