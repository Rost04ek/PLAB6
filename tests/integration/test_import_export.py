"""Інтеграційні тести імпорту CSV та експорту JSON."""

import json
from pathlib import Path
import pytest

from application.config import load_config_from_env
from application.exporters import export_tasks_to_json, import_tasks_from_csv
from application.models import TaskBoard


@pytest.mark.integration
def test_full_csv_import_status_transition_and_json_export_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Інтеграційний тест: Env Config → CSV Import → TaskBoard → Status Transitions → JSON Export."""
    monkeypatch.setenv("APP_ENV", "integration_test")
    config = load_config_from_env()
    board = TaskBoard(config=config)

    csv_path = tmp_path / "incoming_tasks.csv"
    csv_path.write_text(
        "id,type,title,priority,status,estimate_hours,extra\n"
        "101,task,Підготувати реліз,high,todo,4.0,\n"
        "102,bug,Виправити верстку форми,medium,in_progress,2.5,minor\n"
        "103,feature,Експорт у PDF,critical,review,10.0,8\n",
        encoding="utf-8",
    )

    imported = import_tasks_from_csv(csv_path, board=board)
    assert len(imported) == 3

    board.get_task(102).change_status("done")
    board.get_task(103).change_status("done")

    json_path = tmp_path / "summary_report.json"
    export_tasks_to_json(board, json_path)

    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["environment"] == "integration_test"
    assert report["total_tasks"] == 3
    assert report["completed_tasks"] == 2
    assert report["incomplete_tasks"] == 1
    assert report["completion_rate"] == pytest.approx(66.67)
    assert report["average_estimate_hours"] == pytest.approx(5.5)
