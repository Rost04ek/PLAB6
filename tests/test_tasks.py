import pytest
import json
from unittest.mock import Mock, AsyncMock
from src.tasks.core import (
    Task, BugTask, FeatureTask, TaskBoard, TaskWorkflowService,
    InvalidTaskError, InvalidStatusTransition, MalformedTaskRecord,
    get_allowed_statuses, export_tasks_json, import_tasks_csv, AsyncTaskRepository
)

# --- 1. UNIT TESTS: Models & Validation ---
def test_create_feature_task():
    t = FeatureTask(task_id=3, title="Add dark mode", priority="Medium", estimated_hours=5.0, feature_branch="feat/dark-mode")
    assert t.feature_branch == "feat/dark-mode"

@pytest.mark.parametrize("priority", ["Unknown", "SuperHigh", ""])
def test_invalid_priority_raises(priority):
    with pytest.raises(InvalidTaskError, match="Invalid priority"):
        Task(task_id=1, title="Bad", priority=priority, estimated_hours=1.0)

def test_negative_hours_raises():
    with pytest.raises(InvalidTaskError, match="negative"):
        Task(task_id=1, title="Bad", priority="Low", estimated_hours=-2.0)

@pytest.mark.parametrize("status", ["In Progress", "Resolved", "Closed"])
def test_valid_status_change(basic_task, status):
    basic_task.change_status(status)
    assert basic_task.status == status

def test_invalid_status_change(basic_task):
    with pytest.raises(InvalidTaskError, match="Invalid status"):
        basic_task.change_status("Deploying")

def test_invalid_status_transition(basic_task):
    basic_task.change_status("Closed")
    with pytest.raises(InvalidStatusTransition, match="Cannot reopen"):
        basic_task.change_status("In Progress")

# --- 2. UNIT TESTS: TaskBoard ---
def test_empty_board():
    board = TaskBoard()
    assert board.count_completed() == 0
    assert board.average_estimation() == 0.0

def test_board_add_and_find(populated_board, basic_task):
    found = populated_board.find_task(1)
    assert found == basic_task
    assert populated_board.find_task(999) is None

def test_board_filter_by_priority(populated_board):
    high_tasks = populated_board.filter_by_priority("High")
    assert len(high_tasks) == 1
    assert high_tasks[0].task_id == 1

def test_board_filter_by_status(populated_board, basic_task):
    basic_task.change_status("In Progress")
    in_progress = populated_board.filter_by_status("In Progress")
    assert len(in_progress) == 1
    assert in_progress[0].task_id == 1

def test_board_count_completed(populated_board, basic_task):
    assert populated_board.count_completed() == 0
    basic_task.change_status("Closed")
    assert populated_board.count_completed() == 1

def test_average_estimation_approx(populated_board):
    # Setup: 4.5 + 1.5 = 6.0 / 2 = 3.0
    assert populated_board.average_estimation() == pytest.approx(3.0)

# --- 3. MOCKS & SIDE EFFECTS ---
def test_workflow_complete_task_success(basic_task):
    mock_repo = Mock()
    mock_repo.save.return_value = True  # return_value test
    mock_notifier = Mock()
    
    service = TaskWorkflowService(mock_repo, mock_notifier)
    result = service.complete_task(basic_task)
    
    assert result is True
    assert basic_task.status == "Closed"
    mock_repo.save.assert_called_once_with(basic_task)  # interaction assertion
    mock_notifier.send_alert.assert_called_once()

def test_workflow_complete_task_repo_failure(basic_task):
    mock_repo = Mock()
    mock_repo.save.return_value = False
    mock_notifier = Mock()
    
    service = TaskWorkflowService(mock_repo, mock_notifier)
    
    with pytest.raises(InvalidTaskError, match="Failed to save"):
        service.complete_task(basic_task)
        
    mock_notifier.send_alert.assert_not_called()

def test_workflow_notifier_side_effect(basic_task):
    mock_repo = Mock()
    mock_repo.save.return_value = True
    
    mock_notifier = Mock()
    # Testing side_effect
    mock_notifier.send_alert.side_effect = ConnectionError("Network down")
    
    service = TaskWorkflowService(mock_repo, mock_notifier)
    with pytest.raises(ConnectionError, match="Network down"):
        service.complete_task(basic_task)

@pytest.mark.asyncio
async def test_async_fetch_remote_task():
    # Testing AsyncMock
    async_repo = AsyncMock(spec=AsyncTaskRepository)
    async_repo.fetch_remote_task.return_value = {"id": 99, "status": "Remote"}
    
    result = await async_repo.fetch_remote_task(99)
    assert result["status"] == "Remote"
    async_repo.fetch_remote_task.assert_awaited_once_with(99)

# --- 4. MONKEYPATCH ---
def test_config_allowed_statuses(monkeypatch):
    monkeypatch.setenv("ALLOWED_STATUSES", "Draft,Published")
    statuses = get_allowed_statuses()
    assert statuses == ["Draft", "Published"]

# --- 5. INTEGRATION TESTS & TMP_PATH ---
@pytest.mark.integration
def test_export_json_tmp_path(tmp_path, populated_board):
    file_path = tmp_path / "tasks_export.json"
    export_tasks_json(populated_board._tasks, file_path)
    
    assert file_path.exists()
    data = json.loads(file_path.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["title"] == "Setup CI"

@pytest.mark.integration
def test_import_csv_tmp_path(tmp_path):
    csv_file = tmp_path / "import.csv"
    csv_file.write_text(
        "task_id,title,priority,estimated_hours\n"
        "10,New Task,Low,2.5\n",
        encoding="utf-8"
    )
    
    tasks = import_tasks_csv(csv_file)
    assert len(tasks) == 1
    assert tasks[0].task_id == 10

def test_import_malformed_csv(tmp_path):
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text(
        "task_id,priority,estimated_hours\n"
        "10,Low,2.5\n",
        encoding="utf-8"
    )
    with pytest.raises(MalformedTaskRecord):
        import_tasks_csv(csv_file)

@pytest.mark.integration
def test_full_application_flow(tmp_path):
    # Pipeline: Import -> Board -> Complete -> Export
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("task_id,title,priority,estimated_hours\n1,Write tests,High,3.0\n", encoding="utf-8")
    tasks = import_tasks_csv(csv_file)
    
    board = TaskBoard()
    for t in tasks:
        board.add_task(t)
        
    task = board.find_task(1)
    mock_repo = Mock()
    mock_repo.save.return_value = True
    service = TaskWorkflowService(mock_repo, Mock())
    
    service.complete_task(task)
    
    json_out = tmp_path / "out.json"
    export_tasks_json(board._tasks, json_out)
    
    assert board.count_completed() == 1
    result_data = json.loads(json_out.read_text(encoding="utf-8"))
    assert result_data[0]["status"] == "Closed"