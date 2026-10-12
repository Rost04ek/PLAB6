import os
import csv
import json
from dataclasses import dataclass
from typing import Protocol
from pathlib import Path

class InvalidTaskError(Exception): pass
class InvalidStatusTransition(Exception): pass
class MalformedTaskRecord(Exception): pass

def get_allowed_statuses() -> list[str]:
    return os.getenv("ALLOWED_STATUSES", "Open,In Progress,Resolved,Closed").split(",")

def get_allowed_priorities() -> list[str]:
    return os.getenv("ALLOWED_PRIORITIES", "Low,Medium,High,Critical").split(",")

@dataclass
class Task:
    task_id: int
    title: str
    priority: str
    estimated_hours: float
    status: str = "Open"

    def __post_init__(self):
        if self.priority not in get_allowed_priorities():
            raise InvalidTaskError(f"Invalid priority: {self.priority}")
        if self.estimated_hours < 0:
            raise InvalidTaskError("Estimated hours cannot be negative")

    def change_status(self, new_status: str):
        if new_status not in get_allowed_statuses():
            raise InvalidTaskError(f"Invalid status: {new_status}")
        if self.status == "Closed" and new_status != "Closed":
            raise InvalidStatusTransition("Cannot reopen a closed task.")
        self.status = new_status

@dataclass
class BugTask(Task):
    severity: str = "High"

@dataclass
class FeatureTask(Task):
    feature_branch: str = "main"

class TaskBoard:
    def __init__(self):
        self._tasks: list[Task] = []
        
    def add_task(self, task: Task):
        self._tasks.append(task)
        
    def filter_by_priority(self, priority: str) -> list[Task]:
        return [t for t in self._tasks if t.priority == priority]
        
    def filter_by_status(self, status: str) -> list[Task]:
        return [t for t in self._tasks if t.status == status]
        
    def find_task(self, task_id: int) -> Task | None:
        for t in self._tasks:
            if t.task_id == task_id:
                return t
        return None
        
    def count_completed(self) -> int:
        return sum(1 for t in self._tasks if t.status == "Closed")

    def count_incomplete(self) -> int:
        return sum(1 for t in self._tasks if t.status != "Closed")
        
    def average_estimation(self) -> float:
        if not self._tasks:
            return 0.0
        return sum(t.estimated_hours for t in self._tasks) / len(self._tasks)

class Notifier(Protocol):
    def send_alert(self, task_id: int, message: str) -> None: ...

class TaskRepository(Protocol):
    def save(self, task: Task) -> bool: ...

class AsyncTaskRepository:
    async def fetch_remote_task(self, task_id: int) -> dict:
        pass 

class TaskWorkflowService:
    def __init__(self, repo: TaskRepository, notifier: Notifier):
        self.repo = repo
        self.notifier = notifier
        
    def complete_task(self, task: Task) -> bool:
        task.change_status("Closed")
        saved = self.repo.save(task)
        if not saved:
            raise InvalidTaskError("Failed to save task to database")
        self.notifier.send_alert(task.task_id, f"Task {task.title} is completed")
        return True

    # Для покриття "integration task workflow" з асинхронністю
    async def import_remote_task(self, task_id: int, async_repo: AsyncTaskRepository, board: TaskBoard) -> Task:
        data = await async_repo.fetch_remote_task(task_id)
        if not data:
            raise InvalidTaskError("Remote task not found")
        task = Task(
            task_id=data["id"], 
            title=data["title"], 
            priority=data["priority"], 
            estimated_hours=float(data["estimated_hours"])
        )
        board.add_task(task)
        return task

def export_tasks_json(tasks: list[Task], path: Path) -> None:
    data = [{"id": t.task_id, "title": t.title, "status": t.status} for t in tasks]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def import_tasks_csv(path: Path) -> list[Task]:
    tasks = []
    try:
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row.get("title"):
                    raise MalformedTaskRecord("Missing task title")
                task = Task(
                    task_id=int(row["task_id"]),
                    title=row["title"],
                    priority=row["priority"],
                    estimated_hours=float(row["estimated_hours"])
                )
                tasks.append(task)
    except (KeyError, ValueError) as e:
        # Перевірка exception chaining
        raise MalformedTaskRecord(f"Invalid record format: {e}") from e
    return tasks
