import json
from collections import deque
from typing import Callable

from jira import JIRA, Issue, JIRAError

from .config import Config
from .resources import resource_path

Log = Callable[[str], None]


def connect(cfg: Config) -> JIRA:
    return JIRA(f"https://{cfg.jira_host}",
                auth=(cfg.jira_username, cfg.jira_password),
                max_retries=0, timeout=15)


def load_workflow_matrix(log: Log = print) -> dict:
    try:
        with open(resource_path("core/workflow_matrix.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log(f"Error loading workflow_matrix.json: {e}")
        return {}


def find_issues(jira: JIRA, tickets: list[str],
                log: Log = print) -> tuple[list[Issue], dict[str, str]]:
    """Возвращает (найденные issue, {ключ: текст ошибки} для остальных)."""
    issues, errors = [], {}
    for ticket in tickets:
        try:
            issues.append(jira.issue(ticket))
        except JIRAError as e:
            detail = e.status_code or e.text or "error"
            errors[ticket] = f"JIRA {detail}"
            log(f"Error getting issue {ticket}: {detail}")
        except Exception as e:
            errors[ticket] = str(e)
            log(f"Unexpected error for {ticket}: {e}")
    return issues, errors


def find_path_to_target(workflow_matrix: dict, issue_type: str,
                        current_status: str, target_status: str) -> list[str]:
    if issue_type not in workflow_matrix:
        return []
    if current_status == target_status:
        return [current_status]

    issue_workflow = workflow_matrix[issue_type]
    queue = deque([(current_status, [current_status])])
    visited = {current_status}

    while queue:
        status, path = queue.popleft()
        if status not in issue_workflow:
            continue
        for next_status in issue_workflow[status]:
            if next_status == target_status:
                return path + [next_status]
            if next_status not in visited:
                visited.add(next_status)
                queue.append((next_status, path + [next_status]))
    return []


def change_issue_status(jira: JIRA, issue: Issue, workflow_matrix: dict,
                        target_status: str, log: Log = print) -> bool:
    try:
        issue_type = issue.fields.issuetype.name
        current_status = issue.fields.status.name

        if issue_type not in workflow_matrix:
            log(f"  Warning: {issue.key} - issue type '{issue_type}' not in workflow matrix")
            return False

        path = find_path_to_target(workflow_matrix, issue_type,
                                   current_status, target_status)
        if not path:
            log(f"  Warning: {issue.key} - no path from '{current_status}' to '{target_status}'")
            return False

        for i in range(len(path) - 1):
            from_status, to_status = path[i], path[i + 1]
            transition_name = workflow_matrix[issue_type][from_status][to_status]
            transition_id = None
            for t in jira.transitions(issue):
                if t["name"] == transition_name:
                    transition_id = t["id"]
                    break
            if not transition_id:
                log(f"  Warning: {issue.key} - transition '{transition_name}' not available from {from_status}")
                return False
            jira.transition_issue(issue, transition_id)
            log(f"  {issue.key}: {from_status} -> {to_status}")
            issue = jira.issue(issue.key)
        return True
    except Exception as e:
        log(f"  Warning: {issue.key} - error changing status: {e}")
        return False


def pick_assignee(issue: Issue, qa_testers: list[str], qa_lead: str) -> str | None:
    reporter = issue.fields.reporter.name if issue.fields.reporter else None
    if not reporter:
        return None
    return reporter if reporter in qa_testers else qa_lead


def change_assignee(issue: Issue, qa_testers: list[str], qa_lead: str,
                    log: Log = print) -> bool:
    try:
        if not issue.fields.reporter:
            log(f"  Warning: {issue.key} - no reporter found")
            return False
        assignee = pick_assignee(issue, qa_testers, qa_lead)
        if not assignee:
            log(f"  Warning: {issue.key} - QA lead not configured")
            return False
        issue.update(assignee={"name": assignee})
        log(f"  {issue.key} assigned to {assignee}")
        return True
    except Exception as e:
        log(f"  Warning: {issue.key} - error changing assignee: {e}")
        return False


def target_status_for(issue: Issue) -> str:
    return "DEV Ready For Testing" if issue.fields.issuetype.name == "Bug" else "Testing"
