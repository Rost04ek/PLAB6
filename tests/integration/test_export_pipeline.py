import pytest
import json
from src.tasks.exporters import export_tasks_json

@pytest.mark.integration
def test_export_pipeline_success(tmp_path, populated_board):
    file_path = tmp_path / "out.json"
    export_tasks_json(populated_board._tasks, file_path)
    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert data[0]["title"] == "Setup CI"
