"""Кастомні винятки для системи керування завданнями."""


class TaskError(Exception):
    """Базовий виняток для всіх помилок у системі керування завданнями."""


class TaskValidationError(TaskError):
    """Виняток при некоректних значеннях полів завдання (пріоритет, статус, оцінка часу тощо)."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"Validation error in '{field}': {message}")
        self.field = field
        self.details = message


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


class TaskImportError(TaskError):
    """Виняток під час імпорту завдань із зовнішнього файлу (наприклад, CSV)."""

    def __init__(self, line_number: int, reason: str) -> None:
        super().__init__(f"CSV import error at line {line_number}: {reason}")
        self.line_number = line_number
        self.reason = reason


class NotificationError(TaskError):
    """Виняток при збої зовнішнього сервісу сповіщень."""
