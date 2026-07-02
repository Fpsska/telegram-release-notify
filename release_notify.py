import argparse
import sys

from core.config import load_config
from core.tickets import extract_jira_tickets
from core import jira_client
from core.telegram import build_message, send_telegram


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Send release notification to Telegram")
    parser.add_argument("environment", help="Environment, e.g. QA")
    parser.add_argument("release", help="Release version, e.g. 26.1.0")
    parser.add_argument("rc", help="RC number, e.g. 7")
    parser.add_argument("commits", nargs="+",
                        help='Commit strings, e.g. "abc123(BugFix DEV-123 Fix something)"')
    args = parser.parse_args()

    cfg = load_config()
    if not cfg.is_valid():
        print("Config incomplete: fill settings in the UI app or provide .env")
        sys.exit(1)

    print(f"Release: {args.release}-rc{args.rc}")

    tickets = extract_jira_tickets(args.commits)
    if not tickets:
        print("No Jira tickets found in commits.")
        return
    print(f"Tickets found: {tickets}")

    print("\nFetching issues...")
    jira = jira_client.connect(cfg)
    issues, _errors = jira_client.find_issues(jira, tickets)
    if not issues:
        print("No issues found.")
        return

    print("\nChanging issue statuses...")
    workflow_matrix = jira_client.load_workflow_matrix()
    for issue in issues:
        jira_client.change_issue_status(jira, issue, workflow_matrix,
                                        jira_client.target_status_for(issue))

    print("\nChanging assignees...")
    for issue in issues:
        jira_client.change_assignee(issue, cfg.qa_testers, cfg.qa_lead)

    print("\nBuilding Telegram message...")
    message = build_message(cfg.jira_host, args.environment, args.release, args.rc,
                            [(i.key, i.fields.summary) for i in issues])

    print("\n--- Telegram message ---")
    print(message)
    print("-----------------------\n")

    ok, error = send_telegram(cfg, message)
    if ok:
        print("Message sent to Telegram successfully.")
    else:
        print(error)
        print("Message that would be sent:")
        print(message)


if __name__ == "__main__":
    main()
