import pytest
import json
from unittest.mock import Mock, AsyncMock
from application.exporters import export_tasks_json, import_tasks_csv
from application.exceptions import MalformedTaskRecord
from application.services import TaskBoard, TaskWorkflowService
from application.repositories import AsyncTaskRepository
from application.config import get_allowed_statuses, load_json_config

@pytest.mark.integration
def test_import_pipeline_success(tmp_path):
    csv_file = tmp_path / "import.csv"
    csv_file.write_text("task_id,title,priority,estimated_hours\n10,New,Low,2.5\n", encoding="utf-8")
    tasks = import_tasks_csv(csv_file)
    assert len(tasks) == 1
    assert tasks[0].task_id == 10
    assert tasks[0].title == "New"

@pytest.mark.integration
def test_export_pipeline_success(tmp_path, populated_board):
    file_path = tmp_path / "out.json"
    export_tasks_json(populated_board.tasks, file_path)
    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert len(data) == 3
    assert data[0]["title"] == "Setup CI"
    assert data[0]["id"] == 1

@pytest.mark.integration
def test_atomic_file_output_exception(tmp_path, populated_board, monkeypatch):
    file_path = tmp_path / "atomic.json"
    def mock_replace(*args, **kwargs):
        raise OSError("Disk full")
    monkeypatch.setattr("pathlib.Path.replace", mock_replace)
    with pytest.raises(OSError):
        export_tasks_json(populated_board.tasks, file_path)
    assert not file_path.with_suffix('.tmp').exists()

@pytest.mark.integration
def test_malformed_csv_missing_title(tmp_path):
    csv_file = tmp_path / "bad1.csv"
    csv_file.write_text("task_id,priority,estimated_hours\n10,Low,2.5\n", encoding="utf-8")
    with pytest.raises(MalformedTaskRecord, match="Missing task title"):
        import_tasks_csv(csv_file)

@pytest.mark.integration
def test_malformed_csv_exception_chaining(tmp_path):
    csv_file = tmp_path / "bad2.csv"
    csv_file.write_text("task_id,title,priority,estimated_hours\n10,T,Low,INVALID\n", encoding="utf-8")
    with pytest.raises(MalformedTaskRecord) as exc_info:
        import_tasks_csv(csv_file)
    assert isinstance(exc_info.value.__cause__, ValueError)

@pytest.mark.integration
def test_full_application_flow(tmp_path, fake_repo):
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("task_id,title,priority,estimated_hours\n1,Flow Test,High,3.0\n", encoding="utf-8")
    tasks = import_tasks_csv(csv_file)
    
    board = TaskBoard()
    board.add_task(tasks[0])
    
    service = TaskWorkflowService(fake_repo, Mock())
    service.complete_task(board.find_task(1))
    
    json_out = tmp_path / "out.json"
    export_tasks_json(board.tasks, json_out)
    
    result_data = json.loads(json_out.read_text(encoding="utf-8"))
    assert result_data[0]["status"] == "Closed"

@pytest.mark.asyncio
@pytest.mark.integration
async def test_async_integration_task_workflow():
    board = TaskBoard()
    async_repo = AsyncMock(spec=AsyncTaskRepository)
    async_repo.fetch_remote_task.return_value = {
        "id": 100, "title": "Sync", "priority": "Critical", "estimated_hours": 10.0
    }
    service = TaskWorkflowService(Mock(), Mock())
    task = await service.import_remote_task(100, async_repo, board)
    assert task.title == "Sync"
    assert board.find_task(100) == task

@pytest.mark.integration
def test_load_json_config(tmp_path):
    cfg_file = tmp_path / "cfg.json"
    assert load_json_config(tmp_path / "nonexistent.json") == {}
    cfg_file.write_text('{"ALLOWED": ["O"]}')
    assert load_json_config(cfg_file)["ALLOWED"] == ["O"]
