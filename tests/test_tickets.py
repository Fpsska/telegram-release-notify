from core.tickets import extract_jira_tickets


def test_extracts_unique_tickets_in_order():
    commits = [
        "abc123(BugFix DEV-12345 Fix login)",
        "def456(Feature DEV-67890 Add export, relates DEV-12345)",
        "ghi789(no ticket here)",
    ]
    assert extract_jira_tickets(commits) == ["DEV-12345", "DEV-67890"]


def test_multiple_projects():
    assert extract_jira_tickets(["x(OPS-1 and DEV-2)"]) == ["OPS-1", "DEV-2"]


def test_empty():
    assert extract_jira_tickets([]) == []
