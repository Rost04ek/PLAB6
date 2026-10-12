import pytest
from src.tasks.core import TaskBoard

def test_empty_board():
    board = TaskBoard()
    assert board.count_completed() == 0
    assert board.count_incomplete() == 0
    assert board.average_estimation() == 0.0

def test_board_add_and_find(populated_board, basic_task):
    assert populated_board.find_task(1) == basic_task
    assert populated_board.find_task(999) is None

def test_board_filters(populated_board, basic_task):
    high_tasks = populated_board.filter_by_priority("High")
    assert len(high_tasks) == 1
    
    basic_task.change_status("In Progress")
    in_progress = populated_board.filter_by_status("In Progress")
    assert len(in_progress) == 1

def test_board_counts(populated_board, basic_task):
    assert populated_board.count_completed() == 0
    assert populated_board.count_incomplete() == 3
    
    basic_task.change_status("Closed")
    assert populated_board.count_completed() == 1
    assert populated_board.count_incomplete() == 2

def test_average_estimation_approx(populated_board):
    # 4.5 + 1.5 + 5.0 = 11.0 / 3 = 3.6666...
    assert populated_board.average_estimation() == pytest.approx(3.6666666666666665)