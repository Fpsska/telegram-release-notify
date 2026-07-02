from unittest.mock import MagicMock

from core.jira_client import find_path_to_target, pick_assignee

MATRIX = {
    "Bug": {
        "Open": {"In Progress": "Start Progress"},
        "In Progress": {"DEV Ready For Testing": "Ready", "Open": "Stop"},
        "DEV Ready For Testing": {},
    }
}


def test_bfs_finds_shortest_path():
    path = find_path_to_target(MATRIX, "Bug", "Open", "DEV Ready For Testing")
    assert path == ["Open", "In Progress", "DEV Ready For Testing"]


def test_bfs_same_status():
    assert find_path_to_target(MATRIX, "Bug", "Open", "Open") == ["Open"]


def test_bfs_no_path():
    assert find_path_to_target(MATRIX, "Bug", "DEV Ready For Testing", "Open") == []


def test_bfs_unknown_issue_type():
    assert find_path_to_target(MATRIX, "Epic", "Open", "Testing") == []


def _issue_with_reporter(name):
    issue = MagicMock()
    issue.fields.reporter.name = name
    return issue


def test_pick_assignee_reporter_is_tester():
    issue = _issue_with_reporter("tester1")
    assert pick_assignee(issue, ["tester1", "tester2"], "lead") == "tester1"


def test_pick_assignee_reporter_not_tester():
    issue = _issue_with_reporter("someone")
    assert pick_assignee(issue, ["tester1"], "lead") == "lead"


def test_pick_assignee_no_reporter():
    issue = MagicMock()
    issue.fields.reporter = None
    assert pick_assignee(issue, ["tester1"], "lead") is None
