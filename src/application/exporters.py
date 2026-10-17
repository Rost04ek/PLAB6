"""Імпорт завдань із CSV та атомарний експорт у JSON."""

import csv
import json
from pathlib import Path
from typing import Any

from application.exceptions import TaskImportError, TaskValidationError
from application.models import BugTask, FeatureTask, Task, TaskBoard


def import_tasks_from_csv(csv_path: Path, board: TaskBoard | None = None) -> list[Task]:
    """Читає завдання з CSV-файлу, валідує записи та опціонально додає їх у TaskBoard."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    imported: list[Task] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required_cols = {"id", "type", "title", "priority", "status", "estimate_hours"}
        if reader.fieldnames is None or not required_cols.issubset(set(reader.fieldnames)):
            raise TaskImportError(1, "Missing required CSV header columns")

        for line_num, row in enumerate(reader, start=2):
            try:
                raw_id = row.get("id", "")
                raw_est = row.get("estimate_hours", "")
                task_id = int(raw_id)
                estimate = float(raw_est)
            except (ValueError, TypeError) as err:
                raise TaskImportError(
                    line_num, f"Invalid numeric field in row: {row}"
                ) from err

            task_type = (row.get("type") or "task").strip().lower()
            title = row.get("title") or ""
            priority = row.get("priority") or "medium"
            status = row.get("status") or "todo"

            try:
                if task_type == "bug":
                    severity = row.get("extra") or "major"
                    task: Task = BugTask(
                        task_id=task_id,
                        title=title,
                        priority=priority,
                        status=status,
                        estimate_hours=estimate,
                        severity=severity,
                    )
                elif task_type == "feature":
                    pts_str = row.get("extra") or "3"
                    task = FeatureTask(
                        task_id=task_id,
                        title=title,
                        priority=priority,
                        status=status,
                        estimate_hours=estimate,
                        story_points=int(pts_str),
                    )
                elif task_type == "task":
                    task = Task(
                        task_id=task_id,
                        title=title,
                        priority=priority,
                        status=status,
                        estimate_hours=estimate,
                    )
                else:
                    raise TaskValidationError("type", f"Unknown task type '{task_type}'")

                if board is not None:
                    board.add_task(task)
                imported.append(task)
            except (TaskValidationError, ValueError) as err:
                raise TaskImportError(line_num, str(err)) from err

    return imported


def _replace_atomic(temp_path: Path, output_path: Path) -> None:
    """Допоміжна функція атомарної заміни файлу."""
    temp_path.replace(output_path)


def export_tasks_to_json(board: TaskBoard, output_path: Path) -> None:
    """Виконує атомарний експорт стану TaskBoard у JSON-файл через тимчасовий файл."""
    payload: dict[str, Any] = {
        "environment": board.config.environment,
        "total_tasks": len(board),
        "completed_tasks": board.count_completed(),
        "incomplete_tasks": board.count_incomplete(),
        "completion_rate": round(board.completion_rate(), 2),
        "average_estimate_hours": round(board.average_estimate_hours(), 2),
        "tasks": [t.to_dict() for t in board.all_tasks],
    }

    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        temp_path.write_text(serialized, encoding="utf-8")
        _replace_atomic(temp_path, output_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


class TempExportSession:
    """Контекстний менеджер для тимчасового буфера експорту з гарантованим очищенням."""

    def __init__(self, temp_file: Path) -> None:
        self.temp_file = temp_file
        self.is_open = False

    def __enter__(self) -> "TempExportSession":
        self.temp_file.write_text("", encoding="utf-8")
        self.is_open = True
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        self.is_open = False
        if self.temp_file.exists():
            self.temp_file.unlink()
        return False
