import pytest
import json
from src.tasks.exporters import export_tasks_json, import_tasks_csv
from src.tasks.exceptions import MalformedTaskRecord

def test_export_json_tmp_path(tmp_path, populated_board):
    file_path = tmp_path / "tasks.json"
    export_tasks_json(populated_board._tasks, file_path)
    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert len(data) == 3

def test_import_malformed_csv_exception_chaining(tmp_path):
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("task_id,priority,estimated_hours\n10,Low,INVALID\n", encoding="utf-8")
    with pytest.raises(MalformedTaskRecord) as exc_info:
        import_tasks_csv(csv_file)
    assert isinstance(exc_info.value.__cause__, ValueError)
