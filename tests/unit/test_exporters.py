import pytest
import json
from src.tasks.exporters import export_tasks_json, import_tasks_csv
from src.tasks.exceptions import MalformedTaskRecord

def test_export_json_tmp_path(tmp_path, populated_board):
    file_path = tmp_path / "tasks.json"
    export_tasks_json(populated_board._tasks, file_path)
    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert len(data) == 3

# ВИПРАВЛЕНО: ТЕСТ 1 (Немає поля title - падає одразу)
def test_import_malformed_csv_missing_title(tmp_path):
    csv_file = tmp_path / "bad1.csv"
    csv_file.write_text("task_id,priority,estimated_hours\n10,Low,2.5\n", encoding="utf-8")
    with pytest.raises(MalformedTaskRecord, match="Missing task title"):
        import_tasks_csv(csv_file)

# ВИПРАВЛЕНО: ТЕСТ 2 (Exception Chaining - title є, але невалідний час)
def test_import_malformed_csv_exception_chaining(tmp_path):
    csv_file = tmp_path / "bad2.csv"
    csv_file.write_text("task_id,title,priority,estimated_hours\n10,Test,Low,INVALID\n", encoding="utf-8")
    with pytest.raises(MalformedTaskRecord) as exc_info:
        import_tasks_csv(csv_file)
    assert isinstance(exc_info.value.__cause__, ValueError)
