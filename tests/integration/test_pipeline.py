import pytest
import json
from unittest.mock import Mock, AsyncMock
from src.tasks.core import TaskBoard, TaskWorkflowService, export_tasks_json, import_tasks_csv, MalformedTaskRecord, AsyncTaskRepository

@pytest.mark.integration
def test_export_json_tmp_path(tmp_path, populated_board):
    file_path = tmp_path / "tasks_export.json"
    export_tasks_json(populated_board._tasks, file_path)
    
    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert len(data) == 3

@pytest.mark.integration
def test_import_csv_tmp_path(tmp_path):
    csv_file = tmp_path / "import.csv"
    csv_file.write_text("task_id,title,priority,estimated_hours\n10,New Task,Low,2.5\n", encoding="utf-8")
    tasks = import_tasks_csv(csv_file)
    assert len(tasks) == 1

@pytest.mark.integration
def test_import_malformed_csv_exception_chaining(tmp_path):
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("task_id,priority,estimated_hours\n10,Low,INVALID_HOURS\n", encoding="utf-8")
    
    with pytest.raises(MalformedTaskRecord) as exc_info:
        import_tasks_csv(csv_file)
    
    # Перевірка exception chaining
    assert isinstance(exc_info.value.__cause__, ValueError)

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
        "id": 100, 
        "title": "Remote Sync", 
        "priority": "Critical", 
        "estimated_hours": 10.0
    }
    
    service = TaskWorkflowService(Mock(), Mock())
    task = await service.import_remote_task(100, async_repo, board)
    
    assert task.title == "Remote Sync"
    assert board.find_task(100) is not None
    assert board.count_incomplete() == 1
    async_repo.fetch_remote_task.assert_awaited_once_with(100)
