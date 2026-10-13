import csv
import json
from pathlib import Path
from application.models import Task
from application.exceptions import MalformedTaskRecord

def export_tasks_json(tasks: list[Task], path: Path) -> None:
    data = [{"id": t.task_id, "title": t.title, "status": t.status} for t in tasks]
    # Завдання 95: Atomic file output
    temp_path = path.with_suffix('.tmp')
    try:
        temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp_path.replace(path)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise e

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
        # Завдання 98: Exception chaining
        raise MalformedTaskRecord(f"Invalid record format: {e}") from e
    return tasks
