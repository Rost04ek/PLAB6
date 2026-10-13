import pytest
import json
from unittest.mock import Mock, AsyncMock
from src.tasks.services import TaskBoard, TaskWorkflowService, AsyncTaskRepository
from src.tasks.exporters import export_tasks_json, import_tasks_csv

@pytest.mark.integration
def test_import_pipeline_success(tmp_path):
    csv_file = tmp_path / "import.csv"
    csv_file.write_text("task_id,title,priority,estimated_hours\n10,New Task,Low,2.5\n", encoding="utf-8")
    tasks = import_tasks_csv(csv_file)
    assert len(tasks) == 1
    assert tasks[0].task_id == 10

@pytest.mark.integration
def test_export_pipeline_success(tmp_path, populated_board):
    file_path = tmp_path / "out.json"
    export_tasks_json(populated_board._tasks, file_path)
    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert data[0]["title"] == "Setup CI"

@pytest.mark.integration
def test_full_application_flow(tmp_path, fake_repo):
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("task_id,title,priority,estimated_hours\n1,Write tests,High,3.0\n", encoding="utf-8")
    tasks = import_tasks_csv(csv_file)
    
    board = TaskBoard()
    board.add_task(tasks[0])
    
    service = TaskWorkflowService(fake_repo, Mock())
    service.complete_task(board.find_task(1))
    
    json_out = tmp_path / "out.json"
    export_tasks_json(board._tasks, json_out)
    
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
    assert board.count_incomplete() == 1
