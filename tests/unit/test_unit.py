import pytest
from application.models import Task, BugTask, FeatureTask
from application.exceptions import InvalidTaskError, InvalidStatusTransition
from application.services import TaskBoard, TaskBoardSession, TaskWorkflowService
from application.repositories import Notifier, TaskRepository, AsyncTaskRepository
from unittest.mock import Mock, AsyncMock, create_autospec

def test_deterministic_uuid_and_time(monkeypatch):
    monkeypatch.setattr("application.models.uuid.uuid4", lambda: "1234-abcd")
    monkeypatch.setattr("application.models.time.time", lambda: 1600000000.0)
    t = Task(1, "Test", "Low", 1.0)
    assert t.uid == "1234-abcd"
    assert t.created_at == 1600000000.0

def test_context_manager_cleanup():
    board = TaskBoard()
    board.add_task(Task(1, "A", "Low", 1.0))
    session = TaskBoardSession(board)
    with session:
        assert session.is_open is True
        assert len(board.tasks) == 1
    assert session.is_open is False
    assert len(board.tasks) == 0

def test_task_minimum_boundary():
    t = Task(task_id=1, title="Fast", priority="Low", estimated_hours=0.0)
    assert t.estimated_hours == 0.0

def test_models_creation(basic_task, bug_task, feature_task):
    assert basic_task.title == "Setup CI"
    assert bug_task.severity == "High"
    assert feature_task.feature_branch == "feat/ui"

def test_fixture_factory_and_params(task_factory, param_task):
    t = task_factory(priority="Critical")
    assert t.priority == "Critical"
    assert param_task.priority in ["Medium", "High"]

@pytest.mark.parametrize("priority", ["Unknown", "SuperHigh"])
def test_invalid_priority_raises(priority):
    with pytest.raises(InvalidTaskError):
        Task(1, "B", priority, 1.0)

def test_negative_hours_raises():
    with pytest.raises(InvalidTaskError):
        Task(1, "B", "Low", -2.0)

def test_status_transitions(basic_task):
    basic_task.change_status("In Progress")
    assert basic_task.status == "In Progress"
    with pytest.raises(InvalidTaskError):
        basic_task.change_status("Deploying")
    
    basic_task.change_status("Closed")
    with pytest.raises(InvalidStatusTransition):
        basic_task.change_status("In Progress")

def test_board_filters_and_find(populated_board, basic_task):
    assert populated_board.find_task(1) == basic_task
    assert populated_board.find_task(999) is None
    assert len(populated_board.filter_by_priority("High")) == 1
    basic_task.change_status("In Progress")
    assert len(populated_board.filter_by_status("In Progress")) == 1

def test_board_empty_and_counts(populated_board):
    assert populated_board.count_completed() == 0
    assert populated_board.count_incomplete() == 3
    assert populated_board.average_estimation() == pytest.approx(3.6666666666666665)
    
    empty_board = TaskBoard()
    assert empty_board.average_estimation() == 0.0

def test_workflow_complete_task_success(basic_task, fake_repo):
    mock_notifier = create_autospec(Notifier, instance=True)
    service = TaskWorkflowService(fake_repo, mock_notifier)
    assert service.complete_task(basic_task) is True
    mock_notifier.send_alert.assert_called_once_with(basic_task.task_id, f"Task {basic_task.title} is completed")

def test_workflow_complete_task_repo_failure(basic_task):
    mock_repo = create_autospec(TaskRepository, instance=True)
    mock_repo.save.return_value = False
    service = TaskWorkflowService(mock_repo, Mock())
    with pytest.raises(InvalidTaskError):
        service.complete_task(basic_task)

def test_workflow_notifier_side_effect(basic_task):
    mock_repo, mock_notifier = Mock(), Mock()
    mock_repo.save.return_value = True
    mock_notifier.send_alert.side_effect = ConnectionError("Net down")
    service = TaskWorkflowService(mock_repo, mock_notifier)
    with pytest.raises(ConnectionError):
        service.complete_task(basic_task)

@pytest.mark.asyncio
async def test_async_fetch_remote_task_unit():
    async_repo = AsyncMock(spec=AsyncTaskRepository)
    async_repo.fetch_remote_task.return_value = {"id": 99, "status": "Remote"}
    result = await async_repo.fetch_remote_task(99)
    async_repo.fetch_remote_task.assert_awaited_once_with(99)
    assert result["status"] == "Remote"

@pytest.mark.asyncio
async def test_async_import_remote_task_not_found():
    board = TaskBoard()
    async_repo = AsyncMock(spec=AsyncTaskRepository)
    async_repo.fetch_remote_task.return_value = None
    service = TaskWorkflowService(Mock(), Mock())
    with pytest.raises(InvalidTaskError, match="Remote task not found"):
        await service.import_remote_task(99, async_repo, board)
