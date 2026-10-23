from reliable_importer.exceptions import RecordValidationError
from reliable_importer.models import Task, ProcessingConfig

def parse_task(row: dict[str, str], *, line_number: int, config: ProcessingConfig) -> Task:
    try:
        task_id = int(row["task_id"])
    except (KeyError, TypeError, ValueError) as error:
        raise RecordValidationError("Invalid task ID", line_number=line_number, field="task_id") from error

    title = row.get("title", "").strip()
    if not title:
        raise RecordValidationError("Task title is empty", line_number=line_number, field="title")

    description = row.get("description", "").strip()

    priority = row.get("priority", "").strip()
    if priority not in config.allowed_priorities:
        raise RecordValidationError(f"Invalid priority: {priority}", line_number=line_number, field="priority")

    status = row.get("status", "").strip()
    if status not in config.allowed_statuses:
        raise RecordValidationError(f"Invalid status: {status}", line_number=line_number, field="status")

    return Task(
        task_id=task_id,
        title=title,
        description=description,
        priority=priority,
        status=status,
    )
