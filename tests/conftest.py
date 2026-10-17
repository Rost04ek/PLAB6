"""Спільні fixtures для всього test suite (conftest.py)."""

from collections.abc import Callable, Generator
from pathlib import Path
import pytest

from task_manager.config import AppConfig
from task_manager.models import BugTask, FeatureTask, Task, TaskBoard
from task_manager.repositories import InMemoryTaskRepository, SQLiteTaskRepository


@pytest.fixture
def sample_task() -> Task:
    """Базова фікстура звичайного завдання."""
    return Task(
        task_id=1,
        title="Написати документацію API",
        priority="medium",
        status="todo",
        estimate_hours=4.5,
    )


@pytest.fixture
def sample_bug() -> BugTask:
    """Фікстура завдання-багу (BugTask)."""
    return BugTask(
        task_id=2,
        title="Виправити витік пам'яті у воркері",
        priority="critical",
        status="in_progress",
        estimate_hours=6.0,
        severity="blocker",
        environment="prod",
    )


@pytest.fixture
def sample_feature() -> FeatureTask:
    """Фікстура завдання-фічі (FeatureTask)."""
    return FeatureTask(
        task_id=3,
        title="Додати підтримку OAuth2 авторизації",
        priority="high",
        status="done",
        estimate_hours=12.0,
        story_points=8,
        epic="Security",
    )


@pytest.fixture
def populated_board(
    sample_task: Task,
    sample_bug: BugTask,
    sample_feature: FeatureTask,
) -> TaskBoard:
    """Фікстура заповненої дошки завдань (TaskBoard) із трьома різними завданнями."""
    board = TaskBoard()
    board.add_task(sample_task)
    board.add_task(sample_bug)
    board.add_task(sample_feature)
    return board


@pytest.fixture
def task_factory() -> Callable[..., Task]:
    """Fixture factory для гнучкого створення екземплярів Task із кастомними параметрами."""
    counter = 100

    def _create_task(
        *,
        task_id: int | None = None,
        title: str = "Тестове завдання",
        priority: str = "medium",
        status: str = "todo",
        estimate_hours: float = 2.0,
    ) -> Task:
        nonlocal counter
        if task_id is None:
            counter += 1
            task_id = counter
        return Task(
            task_id=task_id,
            title=title,
            priority=priority,
            status=status,
            estimate_hours=estimate_hours,
        )

    return _create_task


@pytest.fixture
def fake_repository() -> InMemoryTaskRepository:
    """Фікстура, що повертає ізольований Fake-репозиторій у пам'яті."""
    return InMemoryTaskRepository()


@pytest.fixture
def sqlite_repo(tmp_path: Path) -> Generator[SQLiteTaskRepository, None, None]:
    """Фікстура з teardown через yield для SQLiteTaskRepository."""
    db_file = tmp_path / "tasks_test.db"
    repo = SQLiteTaskRepository(db_file)
    yield repo
    repo.close()


@pytest.fixture(params=["low", "medium", "high", "critical"])
def valid_priority(request: pytest.FixtureRequest) -> str:
    """Параметризована фікстура для перевірки всіх стандартних пріоритетів."""
    return str(request.param)
