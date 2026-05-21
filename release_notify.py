import argparse
import json
import os
import re
import sys
from collections import deque
from jira import JIRA, Issue, JIRAError

import requests
from dotenv import load_dotenv

load_dotenv()


# ── Config ──────────────────────────────────────────────────────────────────
JIRA_HOST = os.environ["JIRA_HOST"]
JIRA_BASE = f"https://{JIRA_HOST}/browse"
JIRA_USERNAME = os.environ["JIRA_USERNAME"]
JIRA_PASSWORD = os.environ["JIRA_PASSWORD"]
JIRA_QA_TESTERS = [u.strip() for u in os.environ["JIRA_QA_TESTERS"].split(",")]
JIRA_QA_LEAD = os.environ["JIRA_QA_LEAD"]

jira = JIRA(f"https://{JIRA_HOST}", auth=(JIRA_USERNAME, JIRA_PASSWORD))

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
TELEGRAM_PROXY = os.environ.get("TELEGRAM_PROXY")


# ── Helpers ──────────────────────────────────────────────────────────────────
def extract_jira_tickets(commits: list[str]) -> list[str]:
    pattern = re.compile(r'[A-Z]+-\d+')
    tickets, seen = [], set()
    for commit in commits:
        for match in pattern.findall(commit):
            if match not in seen:
                seen.add(match)
                tickets.append(match)
    return tickets


def find_issues(tickets: list[str]) -> list[Issue]:
    issues: list[Issue] = []
    for ticket in tickets:
        try:
            issue = jira.issue(ticket)
            issues.append(issue)
        except JIRAError as e:
            print(f"Error getting issue: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
    return issues


def load_workflow_matrix() -> dict:
    """Load workflow matrix from JSON file."""
    try:
        with open("workflow_matrix.json", "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading workflow_matrix.json: {e}")
        return {}


def find_path_to_target(workflow_matrix: dict, issue_type: str, current_status: str, target_status: str) -> list[str]:
    """
    Find path from current_status to target_status using BFS.
    Returns list of statuses to transition through.
    """
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

        for next_status in issue_workflow[status].keys():
            if next_status == target_status:
                return path + [next_status]

            if next_status not in visited:
                visited.add(next_status)
                queue.append((next_status, path + [next_status]))

    return []


def change_issue_status(issue: Issue, workflow_matrix: dict, target_status: str) -> bool:
    """
    Transition issue to target status using workflow matrix path.
    Returns True if successful.
    """
    try:
        issue_type = issue.fields.issuetype.name
        current_status = issue.fields.status.name

        if issue_type not in workflow_matrix:
            print(f"  Warning: {issue.key} - issue type '{issue_type}' not in workflow matrix")
            return False

        path = find_path_to_target(workflow_matrix, issue_type, current_status, target_status)

        if not path:
            print(f"  Warning: {issue.key} - no path from '{current_status}' to '{target_status}'")
            return False

        # Follow the path, transitioning through each status
        for i in range(len(path) - 1):
            from_status = path[i]
            to_status = path[i + 1]

            transition_name = workflow_matrix[issue_type][from_status][to_status]

            # Find transition ID by name
            transitions = jira.transitions(issue)
            transition_id = None
            for t in transitions:
                if t['name'] == transition_name:
                    transition_id = t['id']
                    break

            if transition_id:
                jira.transition_issue(issue, transition_id)
                print(f"  {issue.key}: {from_status} -> {to_status}")
                # Refresh issue to get updated status
                issue = jira.issue(issue.key)
            else:
                print(f"  Warning: {issue.key} - transition '{transition_name}' not available from {from_status}")
                return False

        return True
    except Exception as e:
        print(f"  Warning: {issue.key} - error changing status: {e}")
        return False


def change_assignee(issue: Issue) -> bool:
    """
    Change issue assignee based on Reporter.
    If Reporter in JIRA_QA_TESTERS, assign to Reporter.
    Otherwise assign to JIRA_QA_LEAD.
    """
    try:
        reporter = issue.fields.reporter.name if issue.fields.reporter else None

        if not reporter:
            print(f"  Warning: {issue.key} - no reporter found")
            return False

        if reporter in JIRA_QA_TESTERS:
            assignee = reporter
        else:
            assignee = JIRA_QA_LEAD

        issue.update(assignee={"name": assignee})
        print(f"  {issue.key} assigned to {assignee}")
        return True
    except Exception as e:
        print(f"  Warning: {issue.key} - error changing assignee: {e}")
        return False


# ── Telegram ─────────────────────────────────────────────────────────────────
def send_telegram(message: str) -> None:
    try:
        proxies = {"https": TELEGRAM_PROXY} if TELEGRAM_PROXY else None
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            proxies=proxies,
            timeout=15,
        )
        if resp.ok:
            print("Message sent to Telegram successfully.")
        else:
            print(f"Telegram error: {resp.status_code} {resp.text}")
    except requests.exceptions.ConnectionError:
        print("Cannot reach api.telegram.org (network/proxy issue).")
        print("Message that would be sent:")
        print(message)
    except requests.exceptions.Timeout:
        print("Telegram request timed out.")
        print("Message that would be sent:")
        print(message)


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Send release notification to Telegram")
    parser.add_argument("environment", help="Environment, e.g. QA")
    parser.add_argument("release", help="Release version, e.g. 26.1.0")
    parser.add_argument("rc", help="RC number, e.g. 7")
    parser.add_argument("commits", nargs="+", help='Commit strings, e.g. "abc123(BugFix DEV-123 Fix something)"')
    args = parser.parse_args()

    ENVIRONMENT = args.environment
    RELEASE = args.release
    RC = args.rc
    COMMITS = args.commits

    print(f"Release: {RELEASE}-rc{RC}")

    tickets = extract_jira_tickets(COMMITS)
    if not tickets:
        print("No Jira tickets found in commits.")
        return
    print(f"Tickets found: {tickets}")

    print("\nFetching issues...")
    issues = find_issues(tickets)
    if not issues:
        print("No issues found.")
        return

    print("\nChanging issue statuses...")
    workflow_matrix = load_workflow_matrix()
    for issue in issues:
        issue_type = issue.fields.issuetype.name
        if issue_type == "Bug":
            change_issue_status(issue, workflow_matrix, "DEV Ready For Testing")
        else:
            change_issue_status(issue, workflow_matrix, "Testing")

    print("\nChanging assignees...")
    for issue in issues:
        change_assignee(issue)

    print("\nBuilding Telegram message...")
    lines = [f"\U0001f4cb На {ENVIRONMENT} {RELEASE}-rc{RC}:"]
    for issue in issues:
        url = f"{JIRA_BASE}/{issue.key}"
        title = issue.fields.summary
        safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f'<a href="{url}">{issue.key} - {safe_title}</a>')
    message = "\n\n".join(lines)

    print("\n--- Telegram message ---")
    print(message)
    print("-----------------------\n")

    send_telegram(message)


if __name__ == "__main__":
    main()
