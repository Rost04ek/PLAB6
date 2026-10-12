from dataclasses import dataclass
from .exceptions import InvalidTaskError, InvalidStatusTransition
from .config import get_allowed_statuses, get_allowed_priorities

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
