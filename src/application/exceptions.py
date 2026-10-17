"""Кастомні винятки для системи керування завданнями (Варіант 14)."""


class TaskError(Exception):
    """Базовий виняток системи керування завданнями."""


class RecordValidationError(TaskError):
    """Виняток валідації запису або поля моделі."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"Validation error in '{field}': {message}")
        self.field = field
        self.details = message


class TaskValidationError(RecordValidationError):
    """Виняток при некоректних значеннях полів завдання (priority, status, estimate_hours)."""


class InvalidStatusTransitionError(TaskError):
    """Виняток при спробі виконати недопустимий перехід між статусами завдання."""

    def __init__(self, current_status: str, target_status: str) -> None:
        super().__init__(
            f"Cannot transition task status from '{current_status}' to '{target_status}'"
        )
        self.current_status = current_status
        self.target_status = target_status


class TaskNotFoundError(TaskError):
    """Виняток, коли завдання з вказаним ID не знайдено."""

    def __init__(self, task_id: int) -> None:
        super().__init__(f"Task with id={task_id} was not found")
        self.task_id = task_id


class DataImportError(TaskError):
    """Виняток під час імпорту даних із зовнішнього файлу."""

    def __init__(self, line_number: int, reason: str) -> None:
        super().__init__(f"CSV import error at line {line_number}: {reason}")
        self.line_number = line_number
        self.reason = reason


class TaskImportError(DataImportError):
    """Виняток під час імпорту завдань із CSV."""


class NotificationError(TaskError):
    """Виняток при збої зовнішнього сервісу сповіщень."""
