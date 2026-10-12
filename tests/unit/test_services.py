import pytest
from unittest.mock import Mock, AsyncMock, create_autospec
from src.tasks.services import TaskBoard, TaskWorkflowService, Notifier, TaskRepository, AsyncTaskRepository
from src.tasks.exceptions import InvalidTaskError

def test_board_empty_and_counts():
    board = TaskBoard()
    assert board.count_completed() == 0
    assert board.count_incomplete() == 0
    assert board.average_estimation() == 0.0

def test_board_filters_and_find(populated_board, basic_task):
    assert populated_board.find_task(1) == basic_task
    assert populated_board.find_task(999) is None
    
    high_tasks = populated_board.filter_by_priority("High")
    assert len(high_tasks) == 1

def test_average_estimation_approx(populated_board):
    assert populated_board.average_estimation() == pytest.approx(3.6666666666666665)

def test_workflow_complete_task_success(basic_task, fake_repo):
    # Advanced: autospec
    mock_notifier = create_autospec(Notifier, instance=True)
    service = TaskWorkflowService(fake_repo, mock_notifier)
    assert service.complete_task(basic_task) is True
    mock_notifier.send_alert.assert_called_once()

def test_workflow_complete_task_repo_failure(basic_task):
    mock_repo = create_autospec(TaskRepository, instance=True)
    mock_repo.save.return_value = False
    service = TaskWorkflowService(mock_repo, Mock())
    with pytest.raises(InvalidTaskError):
        service.complete_task(basic_task)

def test_workflow_notifier_side_effect(basic_task):
    mock_repo, mock_notifier = Mock(), Mock()
    mock_repo.save.return_value = True
    mock_notifier.send_alert.side_effect = ConnectionError("Network down")
    service = TaskWorkflowService(mock_repo, mock_notifier)
    with pytest.raises(ConnectionError):
        service.complete_task(basic_task)

@pytest.mark.asyncio
async def test_async_fetch_remote_task_unit():
    async_repo = AsyncMock(spec=AsyncTaskRepository)
    async_repo.fetch_remote_task.return_value = {"id": 99, "status": "Remote"}
    result = await async_repo.fetch_remote_task(99)
    async_repo.fetch_remote_task.assert_awaited_once_with(99)
