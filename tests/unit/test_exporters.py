"""Модульні тести файлового імпорту CSV та експорту JSON через tmp_path."""

import json
from pathlib import Path
import pytest

from task_manager.exceptions import TaskImportError, TaskValidationError
from task_manager.exporters import (
    TempExportSession,
    export_tasks_to_json,
    import_tasks_from_csv,
)
from task_manager.models import BugTask, FeatureTask, TaskBoard


def test_import_tasks_from_csv_valid(tmp_path: Path) -> None:
    """Тестування успішного імпорту завдань різних типів із CSV через tmp_path."""
    csv_file = tmp_path / "tasks.csv"
    csv_file.write_text(
        "id,type,title,priority,status,estimate_hours,extra\n"
        "1,task,Налаштувати CI,high,todo,3.5,\n"
        "2,bug,Виправити 500 помилку,critical,in_progress,5.0,blocker\n"
        "3,feature,Темна тема інтерфейсу,low,done,8.0,5\n",
        encoding="utf-8",
    )

    board = TaskBoard()
    tasks = import_tasks_from_csv(csv_file, board=board)

    assert len(tasks) == 3
    assert len(board) == 3
    assert isinstance(tasks[1], BugTask)
    assert tasks[1].severity == "blocker"
    assert isinstance(tasks[2], FeatureTask)
    assert tasks[2].story_points == 5


def test_import_csv_malformed_numeric_record_chains_exception(tmp_path: Path) -> None:
    """Перевірка обробки malformed CSV record та збереження оригінального ValueError у __cause__."""
    csv_file = tmp_path / "broken_numeric.csv"
    csv_file.write_text(
        "id,type,title,priority,status,estimate_hours,extra\n"
        "abc,task,Некоректний ID,medium,todo,2.0,\n",
        encoding="utf-8",
    )

    with pytest.raises(TaskImportError) as exc_info:
        import_tasks_from_csv(csv_file)

    assert exc_info.value.line_number == 2
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_import_csv_invalid_domain_data_and_missing_headers(tmp_path: Path) -> None:
    """Перевірка помилок при відсутніх стовпцях CSV, невідомому типі або невалідному статусі."""
    missing_file = tmp_path / "nonexistent.csv"
    with pytest.raises(FileNotFoundError):
        import_tasks_from_csv(missing_file)

    bad_header_csv = tmp_path / "bad_header.csv"
    bad_header_csv.write_text("id,title\n1,Test\n", encoding="utf-8")
    with pytest.raises(TaskImportError, match="Missing required CSV header"):
        import_tasks_from_csv(bad_header_csv)

    bad_type_csv = tmp_path / "bad_type.csv"
    bad_type_csv.write_text(
        "id,type,title,priority,status,estimate_hours,extra\n"
        "1,unknown_kind,Title,medium,todo,2.0,\n",
        encoding="utf-8",
    )
    with pytest.raises(TaskImportError) as exc_info:
        import_tasks_from_csv(bad_type_csv)
    assert isinstance(exc_info.value.__cause__, TaskValidationError)


def test_export_tasks_to_json_creates_valid_file(
    tmp_path: Path,
    populated_board: TaskBoard,
) -> None:
    """Перевірка експорту дошки завдань у JSON-файл через tmp_path."""
    output_file = tmp_path / "report.json"

    export_tasks_to_json(populated_board, output_file)

    assert output_file.exists()
    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert data["total_tasks"] == 3
    assert data["completed_tasks"] == 1
    assert data["incomplete_tasks"] == 2
    assert data["completion_rate"] == pytest.approx(33.33)
    assert len(data["tasks"]) == 3


def test_atomic_export_preserves_old_file_on_failure(
    tmp_path: Path,
    populated_board: TaskBoard,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Перевірка атомарності експорту: при збої старий файл не пошкоджується, а .tmp видаляється."""
    output_file = tmp_path / "atomic_report.json"
    output_file.write_text('{"status": "old_valid_data"}', encoding="utf-8")
    temp_file = output_file.with_suffix(".json.tmp")

    def broken_dumps(*args, **kwargs):
        raise OSError("Simulated disk serialization failure")

    monkeypatch.setattr(json, "dumps", broken_dumps)

    with pytest.raises(OSError, match="Simulated disk"):
        export_tasks_to_json(populated_board, output_file)

    assert output_file.read_text(encoding="utf-8") == '{"status": "old_valid_data"}'
    assert not temp_file.exists()


def test_temp_export_session_context_manager_cleanup(tmp_path: Path) -> None:
    """Перевірка коректного очищення ресурсу контекстним менеджером навіть при винятку всередині with."""
    buf_path = tmp_path / "buffer.tmp"
    session = TempExportSession(buf_path)

    with pytest.raises(RuntimeError, match="Abort export"):
        with session:
            assert session.is_open is True
            assert buf_path.exists()
            raise RuntimeError("Abort export")

    assert session.is_open is False
    assert not buf_path.exists()
