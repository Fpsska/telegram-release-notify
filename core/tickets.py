import re

_PATTERN = re.compile(r"[A-Z]+-\d+")


def extract_jira_tickets(commits: list[str]) -> list[str]:
    tickets, seen = [], set()
    for commit in commits:
        for match in _PATTERN.findall(commit):
            if match not in seen:
                seen.add(match)
                tickets.append(match)
    return tickets
