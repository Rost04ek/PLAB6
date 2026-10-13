import csv
import json
from pathlib import Path
from typing import List
from application.models import Task
from application.exceptions import MalformedTaskRecord

def export_tasks_json(tasks: List[Task], path: Path) -> None:
    data = [{"id": t.task_id, "title": t.title, "status": t.status} for t in tasks]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def import_tasks_csv(path: Path) -> List[Task]:
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
        raise MalformedTaskRecord(f"Invalid record format: {e}") from e
    return tasks
