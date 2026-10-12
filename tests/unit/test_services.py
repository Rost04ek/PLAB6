import pytest
from unittest.mock import Mock, AsyncMock, create_autospec
from src.tasks.core import TaskWorkflowService, InvalidTaskError, Notifier, TaskRepository, AsyncTaskRepository

def test_workflow_complete_task_fake_repo(basic_task, fake_repo):
    mock_notifier = create_autospec(Notifier, instance=True)
    service = TaskWorkflowService(fake_repo, mock_notifier)
    
    assert service.complete_task(basic_task) is True
    assert fake_repo.items[basic_task.task_id] == basic_task
    mock_notifier.send_alert.assert_called_once()

def test_workflow_complete_task_repo_failure(basic_task):
    mock_repo = create_autospec(TaskRepository, instance=True)
    mock_repo.save.return_value = False
    mock_notifier = create_autospec(Notifier, instance=True)
    
    service = TaskWorkflowService(mock_repo, mock_notifier)
    with pytest.raises(InvalidTaskError, match="Failed to save"):
        service.complete_task(basic_task)
    mock_notifier.send_alert.assert_not_called()

def test_workflow_notifier_side_effect(basic_task):
    mock_repo = Mock()
    mock_repo.save.return_value = True
    mock_notifier = Mock()
    mock_notifier.send_alert.side_effect = ConnectionError("Network down")
    
    service = TaskWorkflowService(mock_repo, mock_notifier)
    with pytest.raises(ConnectionError, match="Network down"):
        service.complete_task(basic_task)

@pytest.mark.asyncio
async def test_async_fetch_remote_task_unit():
    async_repo = AsyncMock(spec=AsyncTaskRepository)
    async_repo.fetch_remote_task.return_value = {"id": 99, "status": "Remote"}
    
    result = await async_repo.fetch_remote_task(99)
    assert result["status"] == "Remote"
    async_repo.fetch_remote_task.assert_awaited_once_with(99)
