"""Реалізації репозиторіїв для збереження завдань (InMemory та SQLite)."""

from pathlib import Path
import sqlite3

from application.models import BugTask, FeatureTask, Task


class InMemoryTaskRepository:
    """In-memory реалізація репозиторію завдань (FakeRepository)."""

    def __init__(self) -> None:
        self._storage: dict[int, Task] = {}

    def save(self, task: Task) -> None:
        self._storage[task.task_id] = task

    def get_by_id(self, task_id: int) -> Task | None:
        return self._storage.get(task_id)

    def list_all(self) -> list[Task]:
        return list(self._storage.values())


class SQLiteTaskRepository:
    """Реалізація репозиторію завдань на базі вбудованої СУБД SQLite."""

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._create_table()

    def _create_table(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id INTEGER PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    estimate_hours REAL NOT NULL,
                    extra_field TEXT NOT NULL
                )
                """
            )

    def save(self, task: Task) -> None:
        extra = ""
        if isinstance(task, BugTask):
            extra = f"{task.severity}:{task.environment}"
        elif isinstance(task, FeatureTask):
            extra = f"{task.story_points}:{task.epic}"

        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO tasks
                (task_id, task_type, title, priority, status, estimate_hours, extra_field)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.task_type,
                    task.title,
                    task.priority,
                    task.status,
                    task.estimate_hours,
                    extra,
                ),
            )

    def get_by_id(self, task_id: int) -> Task | None:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT task_id, task_type, title, priority, status, estimate_hours, extra_field FROM tasks WHERE task_id = ?",
            (task_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_task(row)

    def list_all(self) -> list[Task]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT task_id, task_type, title, priority, status, estimate_hours, extra_field FROM tasks ORDER BY task_id"
        )
        return [self._row_to_task(r) for r in cur.fetchall()]

    @staticmethod
    def _row_to_task(row: tuple) -> Task:
        t_id, t_type, title, priority, status, estimate, extra = row
        if t_type == "bug":
            sev, env = extra.split(":", 1)
            return BugTask(
                task_id=t_id,
                title=title,
                priority=priority,
                status=status,
                estimate_hours=estimate,
                severity=sev,
                environment=env,
            )
        if t_type == "feature":
            pts, epic = extra.split(":", 1)
            return FeatureTask(
                task_id=t_id,
                title=title,
                priority=priority,
                status=status,
                estimate_hours=estimate,
                story_points=int(pts),
                epic=epic,
            )
        return Task(
            task_id=t_id,
            title=title,
            priority=priority,
            status=status,
            estimate_hours=estimate,
        )

    def close(self) -> None:
        self._conn.close()
