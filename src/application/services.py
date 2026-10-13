from application.models import Task
from application.exceptions import InvalidTaskError
from application.repositories import TaskRepository, Notifier, AsyncTaskRepository

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
