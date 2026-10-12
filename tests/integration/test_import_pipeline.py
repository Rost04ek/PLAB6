import pytest
from src.tasks.exporters import import_tasks_csv

@pytest.mark.integration
def test_import_pipeline_success(tmp_path):
    csv_file = tmp_path / "import.csv"
    csv_file.write_text("task_id,title,priority,estimated_hours\n10,New Task,Low,2.5\n", encoding="utf-8")
    tasks = import_tasks_csv(csv_file)
    assert len(tasks) == 1
    assert tasks[0].task_id == 10
