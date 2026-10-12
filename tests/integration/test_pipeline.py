import pytest
import json
from unittest.mock import Mock
from src.tasks.core import TaskBoard, TaskWorkflowService, export_tasks_json, import_tasks_csv, MalformedTaskRecord

@pytest.mark.integration
def test_export_json_tmp_path(tmp_path, populated_board):
    file_path = tmp_path / "tasks_export.json"
    export_tasks_json(populated_board._tasks, file_path)
    
    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert len(data) == 3
    assert data[0]["title"] == "Setup CI"

@pytest.mark.integration
def test_import_csv_tmp_path(tmp_path):
    csv_file = tmp_path / "import.csv"
    csv_file.write_text("task_id,title,priority,estimated_hours\n10,New Task,Low,2.5\n", encoding="utf-8")
    
    tasks = import_tasks_csv(csv_file)
    assert len(tasks) == 1
    assert tasks[0].task_id == 10

@pytest.mark.integration
def test_import_malformed_csv(tmp_path):
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("task_id,priority,estimated_hours\n10,Low,2.5\n", encoding="utf-8")
    with pytest.raises(MalformedTaskRecord):
        import_tasks_csv(csv_file)

@pytest.mark.integration
def test_full_application_flow(tmp_path):
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("task_id,title,priority,estimated_hours\n1,Write tests,High,3.0\n", encoding="utf-8")
    tasks = import_tasks_csv(csv_file)
    
    board = TaskBoard()
    board.add_task(tasks[0])
    
    mock_repo = Mock()
    mock_repo.save.return_value = True
    service = TaskWorkflowService(mock_repo, Mock())
    service.complete_task(board.find_task(1))
    
    json_out = tmp_path / "out.json"
    export_tasks_json(board._tasks, json_out)
    
    result_data = json.loads(json_out.read_text(encoding="utf-8"))
    assert result_data[0]["status"] == "Closed"