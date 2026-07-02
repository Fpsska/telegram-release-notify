# Desktop UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Десктоп-приложение (pywebview, мастер из 3 шагов, тёмная тема) поверх существующей логики релиз-уведомлений; CLI сохраняется; настройки в `%APPDATA%\release-notify\settings.json` с fallback на `.env`; сборка в standalone .exe.

**Architecture:** Логика выносится из `release_notify.py` в пакет `core/` (config, tickets, jira_client, telegram) без сайд-эффектов при импорте. CLI (`release_notify.py`) и UI (`app/`) зовут одни функции. UI — pywebview-окно с HTML/CSS/JS фронтендом (`app/web/`), мост через `js_api`.

**Tech Stack:** Python 3.10+, jira==3.10.5, python-dotenv, requests[socks], pywebview, pytest, PyInstaller. Спека: `docs/superpowers/specs/2026-07-02-desktop-ui-design.md`.

---

## Структура файлов

| Файл | Ответственность |
|---|---|
| `core/config.py` | Dataclass `Config`, загрузка settings.json → .env, сохранение |
| `core/resources.py` | Пути к ресурсам (исходники / PyInstaller `_MEIPASS`) |
| `core/tickets.py` | `extract_jira_tickets` (regex) |
| `core/jira_client.py` | Подключение, `find_issues`, BFS-путь, смена статуса, исполнитель |
| `core/telegram.py` | `build_message`, `send_telegram` |
| `core/workflow_matrix.json` | Матрица переходов (перенос из корня) |
| `release_notify.py` | CLI-обёртка (та же сигнатура аргументов) |
| `app/api.py` | Класс `Api` — методы для JS |
| `app/main.py` | Точка входа UI |
| `app/web/index.html`, `style.css`, `app.js` | Фронтенд: мастер + настройки |
| `build.spec` | PyInstaller |
| `tests/test_config.py`, `test_tickets.py`, `test_jira_client.py`, `test_telegram.py` | Юнит-тесты |

---

### Task 1: Каркас — пакет core, тестовая инфраструктура

**Files:**
- Create: `core/__init__.py`, `app/__init__.py`, `tests/__init__.py`
- Modify: `requirements.txt`
- Create: `requirements-dev.txt`
- Move: `workflow_matrix.json` → `core/workflow_matrix.json`

- [ ] **Step 1: Создать пакеты и перенести матрицу**

```bash
mkdir -p core app/web tests
touch core/__init__.py app/__init__.py tests/__init__.py
git mv workflow_matrix.json core/workflow_matrix.json
```

- [ ] **Step 2: Обновить зависимости**

`requirements.txt` (полное содержимое):

```
jira==3.10.5
python-dotenv==1.2.1
requests[socks]==2.32.5
pywebview==5.4
```

`requirements-dev.txt` (новый файл):

```
-r requirements.txt
pytest==8.4.1
pyinstaller==6.14.1
```

- [ ] **Step 3: Установить и проверить**

Run: `.venv/Scripts/python -m pip install -r requirements-dev.txt`
Expected: успешная установка, в конце `Successfully installed ... pywebview ... pytest ...`

Run: `.venv/Scripts/python -m pytest --version`
Expected: `pytest 8.4.1`

- [ ] **Step 4: Commit**

```bash
git add core app tests requirements.txt requirements-dev.txt
git commit -m "chore: scaffold core/app packages, add pywebview and pytest"
```

---

### Task 2: core/resources.py + core/config.py

**Files:**
- Create: `core/resources.py`, `core/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Написать падающие тесты**

`tests/test_config.py`:

```python
import json

from core.config import Config, load_config, save_config


def test_settings_json_has_priority_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "env-token")
    monkeypatch.setenv("CHAT_ID", "env-chat")
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"bot_token": "json-token"}), encoding="utf-8")

    cfg = load_config(path=p, load_env_file=False)

    assert cfg.bot_token == "json-token"   # json приоритетнее
    assert cfg.chat_id == "env-chat"       # отсутствующий ключ — из env


def test_env_fallback_when_no_settings_file(tmp_path, monkeypatch):
    monkeypatch.setenv("JIRA_HOST", "jira.example.com")
    monkeypatch.setenv("JIRA_QA_TESTERS", "u1, u2 ,u3")

    cfg = load_config(path=tmp_path / "missing.json", load_env_file=False)

    assert cfg.jira_host == "jira.example.com"
    assert cfg.qa_testers == ["u1", "u2", "u3"]


def test_corrupt_settings_file_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "env-token")
    p = tmp_path / "settings.json"
    p.write_text("{not json", encoding="utf-8")

    cfg = load_config(path=p, load_env_file=False)

    assert cfg.bot_token == "env-token"


def test_save_and_load_roundtrip(tmp_path):
    p = tmp_path / "sub" / "settings.json"
    cfg = Config(bot_token="t", chat_id="c", jira_host="h",
                 jira_username="u", jira_password="p",
                 qa_testers=["a", "b"], qa_lead="lead",
                 telegram_proxy="socks5://x:1080")

    save_config(cfg, path=p)
    loaded = load_config(path=p, load_env_file=False)

    assert loaded == cfg


def test_is_valid():
    assert not Config().is_valid()
    assert Config(bot_token="t", chat_id="c", jira_host="h",
                  jira_username="u", jira_password="p").is_valid()
```

- [ ] **Step 2: Убедиться что падают**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'core.config'`

- [ ] **Step 3: Реализация**

`core/resources.py`:

```python
import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """Путь к ресурсу: работает из исходников и из PyInstaller .exe."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parent.parent / relative
```

`core/config.py`:

```python
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

APP_NAME = "release-notify"


def settings_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / APP_NAME / "settings.json"


@dataclass
class Config:
    bot_token: str = ""
    chat_id: str = ""
    jira_host: str = ""
    jira_username: str = ""
    jira_password: str = ""
    qa_testers: list[str] = field(default_factory=list)
    qa_lead: str = ""
    telegram_proxy: str = ""

    def is_valid(self) -> bool:
        return all([self.bot_token, self.chat_id, self.jira_host,
                    self.jira_username, self.jira_password])


_ENV_MAP = {
    "bot_token": "BOT_TOKEN",
    "chat_id": "CHAT_ID",
    "jira_host": "JIRA_HOST",
    "jira_username": "JIRA_USERNAME",
    "jira_password": "JIRA_PASSWORD",
    "qa_lead": "JIRA_QA_LEAD",
    "telegram_proxy": "TELEGRAM_PROXY",
}


def load_config(path: Path | None = None, load_env_file: bool = True) -> Config:
    """settings.json приоритетнее; отсутствующие в нём ключи берутся из env/.env."""
    if load_env_file:
        load_dotenv()
    p = path or settings_path()
    data: dict = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}

    cfg = Config()
    for attr, env_key in _ENV_MAP.items():
        value = data.get(attr) or os.environ.get(env_key, "")
        setattr(cfg, attr, value.strip() if isinstance(value, str) else "")

    testers = data.get("qa_testers")
    if not isinstance(testers, list):
        raw = os.environ.get("JIRA_QA_TESTERS", "")
        testers = [u.strip() for u in raw.split(",") if u.strip()]
    cfg.qa_testers = testers
    return cfg


def save_config(cfg: Config, path: Path | None = None) -> None:
    p = path or settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg.__dict__, ensure_ascii=False, indent=2),
                 encoding="utf-8")
```

- [ ] **Step 4: Тесты зелёные**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add core/resources.py core/config.py tests/test_config.py
git commit -m "feat: config with settings.json priority and .env fallback"
```

---

### Task 3: core/tickets.py

**Files:**
- Create: `core/tickets.py`
- Test: `tests/test_tickets.py`

- [ ] **Step 1: Падающий тест**

`tests/test_tickets.py`:

```python
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
```

- [ ] **Step 2: Убедиться что падает**

Run: `.venv/Scripts/python -m pytest tests/test_tickets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.tickets'`

- [ ] **Step 3: Реализация** (перенос из `release_notify.py` как есть)

`core/tickets.py`:

```python
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
```

- [ ] **Step 4: Тесты зелёные**

Run: `.venv/Scripts/python -m pytest tests/test_tickets.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add core/tickets.py tests/test_tickets.py
git commit -m "feat: move ticket extraction to core"
```

---

### Task 4: core/jira_client.py

**Files:**
- Create: `core/jira_client.py`
- Test: `tests/test_jira_client.py`

- [ ] **Step 1: Падающие тесты** (BFS — чистая функция; выбор исполнителя — с мок-issue)

`tests/test_jira_client.py`:

```python
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
```

- [ ] **Step 2: Убедиться что падают**

Run: `.venv/Scripts/python -m pytest tests/test_jira_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.jira_client'`

- [ ] **Step 3: Реализация** (логика из `release_notify.py`; `print` заменён на callback `log`, выбор исполнителя выделен в чистую `pick_assignee`)

`core/jira_client.py`:

```python
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
            errors[ticket] = f"JIRA {e.status_code}"
            log(f"Error getting issue {ticket}: {e.status_code}")
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
        assignee = pick_assignee(issue, qa_testers, qa_lead)
        if not assignee:
            log(f"  Warning: {issue.key} - no reporter found")
            return False
        issue.update(assignee={"name": assignee})
        log(f"  {issue.key} assigned to {assignee}")
        return True
    except Exception as e:
        log(f"  Warning: {issue.key} - error changing assignee: {e}")
        return False


def target_status_for(issue: Issue) -> str:
    return "DEV Ready For Testing" if issue.fields.issuetype.name == "Bug" else "Testing"
```

- [ ] **Step 4: Тесты зелёные**

Run: `.venv/Scripts/python -m pytest tests/test_jira_client.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add core/jira_client.py tests/test_jira_client.py
git commit -m "feat: move jira logic to core with log callback"
```

---

### Task 5: core/telegram.py

**Files:**
- Create: `core/telegram.py`
- Test: `tests/test_telegram.py`

- [ ] **Step 1: Падающий тест** (только `build_message` — чистая функция; сетевую `send_telegram` юнитами не покрываем)

`tests/test_telegram.py`:

```python
from core.telegram import build_message


def test_build_message_format_and_escaping():
    msg = build_message("jira.example.com", "QA", "26.1.0", "7",
                        [("DEV-1", "Fix <a> & b")])
    assert msg == (
        "\U0001f4cb На QA 26.1.0-rc7:\n\n"
        '<a href="https://jira.example.com/browse/DEV-1">DEV-1 - Fix &lt;a&gt; &amp; b</a>'
    )


def test_build_message_multiple_items_joined_by_blank_line():
    msg = build_message("h", "QA", "1.0", "1", [("A-1", "x"), ("B-2", "y")])
    assert msg.count("\n\n") == 2
```

- [ ] **Step 2: Убедиться что падает**

Run: `.venv/Scripts/python -m pytest tests/test_telegram.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.telegram'`

- [ ] **Step 3: Реализация**

`core/telegram.py`:

```python
import requests

from .config import Config


def build_message(jira_host: str, environment: str, release: str, rc: str,
                  items: list[tuple[str, str]]) -> str:
    """items: [(ticket_key, summary), ...]"""
    lines = [f"\U0001f4cb На {environment} {release}-rc{rc}:"]
    for key, summary in items:
        url = f"https://{jira_host}/browse/{key}"
        safe = summary.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f'<a href="{url}">{key} - {safe}</a>')
    return "\n\n".join(lines)


def send_telegram(cfg: Config, message: str) -> tuple[bool, str]:
    """Возвращает (успех, текст ошибки)."""
    proxies = {"https": cfg.telegram_proxy} if cfg.telegram_proxy else None
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{cfg.bot_token}/sendMessage",
            json={
                "chat_id": cfg.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            proxies=proxies,
            timeout=15,
        )
        if resp.ok:
            return True, ""
        return False, f"Telegram error: {resp.status_code} {resp.text}"
    except requests.exceptions.ConnectionError:
        return False, "Cannot reach api.telegram.org (network/proxy issue)."
    except requests.exceptions.Timeout:
        return False, "Telegram request timed out."
```

- [ ] **Step 4: Тесты зелёные**

Run: `.venv/Scripts/python -m pytest tests/test_telegram.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add core/telegram.py tests/test_telegram.py
git commit -m "feat: move telegram send/message build to core"
```

---

### Task 6: CLI поверх core

**Files:**
- Modify: `release_notify.py` (полная замена содержимого)

- [ ] **Step 1: Переписать CLI**

`release_notify.py` (полное содержимое):

```python
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
```

- [ ] **Step 2: Смоук-проверка**

Run: `.venv/Scripts/python release_notify.py --help`
Expected: usage с аргументами environment, release, rc, commits — без traceback (импорт без сайд-эффектов).

Run: `.venv/Scripts/python -m pytest -v`
Expected: все тесты зелёные.

- [ ] **Step 3: Commit**

```bash
git add release_notify.py
git commit -m "refactor: CLI is a thin wrapper over core"
```

---

### Task 7: Фронтенд — app/web

**Files:**
- Create: `app/web/index.html`, `app/web/style.css`, `app/web/app.js`

Дизайн — утверждённые макеты: мастер 3 шага, тёмная тема (#0d1117/#1a1f27, акцент #2f81f7), экран настроек с 3 группами.

- [ ] **Step 1: index.html**

`app/web/index.html`:

```html
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Release Notify</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
  <div class="brand"><span class="logo">📋</span> Release Notify</div>
  <button class="icon-btn" id="btn-settings" title="Настройки">⚙</button>
</header>

<nav class="steps" id="steps-bar">
  <div class="step active" id="step-1"><span class="n">1</span><span class="t">Ввод</span></div>
  <div class="step-line"></div>
  <div class="step" id="step-2"><span class="n">2</span><span class="t">Проверка</span></div>
  <div class="step-line"></div>
  <div class="step" id="step-3"><span class="n">3</span><span class="t">Результат</span></div>
</nav>

<!-- Шаг 1: Ввод -->
<main id="screen-input">
  <div class="banner hidden" id="input-banner"></div>
  <div class="row3">
    <label class="field">Окружение
      <input id="env" list="env-list" value="QA">
      <datalist id="env-list"><option>QA</option><option>STAGE</option><option>PROD</option></datalist>
    </label>
    <label class="field">Релиз<input id="release" placeholder="26.1.0"></label>
    <label class="field">RC<input id="rc" placeholder="7"></label>
  </div>
  <label class="field grow">Коммиты
    <textarea id="commits" placeholder="abc12345(BugFix DEV-12345 Fix something)&#10;def67890(Feature DEV-67890 Add thing)"></textarea>
  </label>
  <button class="btn primary" id="btn-find">🔍 Найти тикеты</button>
</main>

<!-- Шаг 2: Проверка -->
<main id="screen-review" hidden>
  <div class="card">
    <div class="card-h"><span>Тикеты · <span id="ticket-count">0</span></span>
      <span class="ok" id="selected-count"></span></div>
    <div id="ticket-list"></div>
  </div>
  <div class="card">
    <div class="card-h">Сообщение в Telegram</div>
    <div class="msg-preview" id="msg-preview"></div>
  </div>
  <div class="row-between">
    <button class="btn ghost" id="btn-back-1">← Назад</button>
    <button class="btn primary" id="btn-execute">▶ Выполнить</button>
  </div>
</main>

<!-- Шаг 3: Результат -->
<main id="screen-result" hidden>
  <div class="card grow">
    <div class="card-h">Лог выполнения</div>
    <pre id="log"></pre>
  </div>
  <div id="result-summary"></div>
  <div class="row-between">
    <button class="btn ghost" id="btn-copy-log">Копировать лог</button>
    <button class="btn ghost hidden" id="btn-resend">↻ Повторить отправку</button>
    <button class="btn primary" id="btn-new-run">Новый прогон</button>
  </div>
</main>

<!-- Настройки -->
<main id="screen-settings" hidden>
  <div class="banner hidden" id="settings-banner"></div>
  <section>
    <h3>✈ Telegram <span class="badge hidden" id="tg-badge"></span></h3>
    <div class="grid2">
      <label class="field">Bot Token<input id="s-bot-token" type="password"></label>
      <label class="field">Chat ID<input id="s-chat-id"></label>
      <label class="field full">Прокси (опционально)
        <input id="s-proxy" placeholder="socks5://user:pass@host:1080">
        <small>SOCKS5 или HTTP, пусто = без прокси</small></label>
    </div>
    <button class="btn ghost" id="btn-test-tg">Проверить: отправить тест в чат</button>
  </section>
  <section>
    <h3>🔧 JIRA <span class="badge hidden" id="jira-badge"></span></h3>
    <div class="grid2">
      <label class="field full">Хост<input id="s-jira-host" placeholder="jira.yourcompany.com"><small>без https://</small></label>
      <label class="field">Логин<input id="s-jira-user"></label>
      <label class="field">Пароль<input id="s-jira-pass" type="password"></label>
    </div>
    <button class="btn ghost" id="btn-test-jira">Проверить подключение</button>
  </section>
  <section>
    <h3>👥 Команда QA</h3>
    <div class="grid2">
      <label class="field full">Тестировщики<input id="s-testers" placeholder="user1, user2">
        <small>логины JIRA через запятую — если репортер в списке, тикет назначается ему</small></label>
      <label class="field full">QA-лид<input id="s-lead"><small>получает тикеты остальных репортеров</small></label>
    </div>
  </section>
  <div class="row-between">
    <button class="btn ghost" id="btn-settings-cancel">Отмена</button>
    <button class="btn primary" id="btn-settings-save">Сохранить</button>
  </div>
</main>

<script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: style.css**

`app/web/style.css`:

```css
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Segoe UI', system-ui, sans-serif;
  background: #1a1f27; color: #e6edf3; font-size: 13px;
  display: flex; flex-direction: column; height: 100vh; overflow: hidden;
}
header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px; background: #12161c; border-bottom: 1px solid #2d333b;
}
.brand { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.logo {
  width: 26px; height: 26px; border-radius: 7px; font-size: 13px;
  background: linear-gradient(135deg, #2f81f7, #a371f7);
  display: flex; align-items: center; justify-content: center;
}
.icon-btn { background: none; border: none; color: #8b949e; font-size: 16px; cursor: pointer; }
.icon-btn:hover { color: #e6edf3; }

.steps { display: flex; justify-content: center; padding: 16px 0 8px; }
.step { display: flex; align-items: center; gap: 8px; }
.step .n {
  width: 26px; height: 26px; border-radius: 50%; font-size: 12px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  background: #21262d; color: #8b949e; border: 1px solid #30363d;
}
.step.active .n { background: #2f81f7; color: #fff; border-color: #2f81f7; }
.step.done .n { background: #12261e; color: #3fb950; border-color: #238636; }
.step .t { font-size: 12px; color: #8b949e; }
.step.active .t { color: #e6edf3; }
.step-line { width: 70px; height: 1px; background: #30363d; margin: 0 12px; align-self: center; }

main {
  flex: 1; overflow-y: auto; padding: 14px 24px 20px;
  display: flex; flex-direction: column; gap: 10px;
}
.grow { flex: 1; display: flex; flex-direction: column; }
.row3 { display: flex; gap: 10px; }
.row3 .field:first-child { flex: 1; }
.row3 .field:nth-child(2) { flex: 1.4; }
.row3 .field:last-child { width: 70px; }
.row-between { display: flex; justify-content: space-between; gap: 10px; margin-top: 4px; }

.field { display: flex; flex-direction: column; gap: 4px; font-size: 11px; color: #8b949e; }
.field small { color: #6e7681; font-size: 10px; }
input, textarea {
  background: #0d1117; border: 1px solid #30363d; color: #e6edf3;
  border-radius: 8px; padding: 8px 11px; font-size: 13px; font-family: inherit;
}
textarea { flex: 1; min-height: 120px; resize: none;
  font-family: 'Cascadia Code', Consolas, monospace; font-size: 12px; line-height: 1.7; }
input:focus, textarea:focus { outline: none; border-color: #2f81f7; }

.btn {
  border: none; border-radius: 8px; padding: 10px 20px;
  font-weight: 600; font-size: 13px; cursor: pointer; font-family: inherit;
}
.btn.primary { background: linear-gradient(135deg, #2f81f7, #1f6feb); color: #fff; }
.btn.primary:disabled { opacity: .5; cursor: wait; }
.btn.ghost { background: #21262d; border: 1px solid #30363d; color: #c9d1d9; }
.btn:hover:not(:disabled) { filter: brightness(1.15); }

.card { background: #0d1117; border: 1px solid #2d333b; border-radius: 10px; overflow: hidden; }
.card-h {
  padding: 10px 14px; border-bottom: 1px solid #2d333b; color: #8b949e;
  font-size: 11px; text-transform: uppercase; letter-spacing: .8px;
  display: flex; justify-content: space-between;
}
.ok { color: #3fb950; }

.ticket { display: flex; align-items: center; gap: 10px; padding: 9px 14px; border-bottom: 1px solid #21262d; }
.ticket:last-child { border-bottom: none; }
.ticket.err { opacity: .55; }
.ticket input[type=checkbox] { accent-color: #2f81f7; width: 15px; height: 15px; }
.tkey { color: #2f81f7; font-weight: 600; min-width: 78px; }
.tsum { flex: 1; color: #c9d1d9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.terr { color: #f85149; font-size: 11px; }
.chip { font-size: 11px; padding: 2px 9px; border-radius: 20px; white-space: nowrap; }
.chip.bug { background: #3d1d20; color: #f85149; }
.chip.task { background: #1b2d45; color: #58a6ff; }
.chip.st { background: #2d2611; color: #d29922; }

.msg-preview { padding: 14px; line-height: 1.65; color: #c9d1d9; }
.msg-preview a { color: #58a6ff; text-decoration: none; }

pre#log {
  padding: 12px 14px; font-family: Consolas, monospace; font-size: 11.5px;
  line-height: 1.6; color: #3fb950; white-space: pre-wrap; overflow-y: auto; flex: 1;
}
#result-summary { line-height: 1.8; }
#result-summary .warn { color: #d29922; }

.banner {
  background: #3d1d20; border: 1px solid #f85149; color: #ffa198;
  border-radius: 8px; padding: 10px 14px; font-size: 12px;
}
.banner a { color: #58a6ff; cursor: pointer; }
.hidden { display: none !important; }

section { display: flex; flex-direction: column; gap: 10px; padding-bottom: 14px;
  border-bottom: 1px solid #2d333b; }
section:last-of-type { border-bottom: none; }
section h3 { font-size: 12px; text-transform: uppercase; letter-spacing: 1px;
  color: #8b949e; display: flex; align-items: center; gap: 8px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 12px; }
.grid2 .full { grid-column: 1 / -1; }
.badge { font-size: 11px; padding: 2px 10px; border-radius: 20px; text-transform: none; letter-spacing: 0; }
.badge.good { background: #12261e; color: #3fb950; }
.badge.bad { background: #3d1d20; color: #f85149; }
```

- [ ] **Step 3: app.js**

`app/web/app.js`:

```javascript
const $ = (id) => document.getElementById(id);
const state = { tickets: [], errors: {}, env: '', release: '', rc: '', telegramFailed: false };

// ── навигация ────────────────────────────────────────────────────────────────
function goStep(n) {
  ['input', 'review', 'result'].forEach((name, i) => {
    $('screen-' + name).hidden = (i !== n - 1);
    const st = $('step-' + (i + 1));
    st.classList.toggle('active', i === n - 1);
    st.classList.toggle('done', i < n - 1);
  });
  $('screen-settings').hidden = true;
  $('steps-bar').style.visibility = 'visible';
}

function showSettings(bannerText) {
  ['input', 'review', 'result'].forEach(n => $('screen-' + n).hidden = true);
  $('screen-settings').hidden = false;
  $('steps-bar').style.visibility = 'hidden';
  const b = $('settings-banner');
  b.classList.toggle('hidden', !bannerText);
  if (bannerText) b.textContent = bannerText;
}

function showBanner(id, text) {
  const b = $(id);
  b.classList.toggle('hidden', !text);
  if (text) b.innerHTML = text;
}

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

// ── шаг 1 → 2 ────────────────────────────────────────────────────────────────
async function onFind() {
  state.env = $('env').value.trim();
  state.release = $('release').value.trim();
  state.rc = $('rc').value.trim();
  const text = $('commits').value.trim();
  if (!state.env || !state.release || !state.rc || !text) {
    showBanner('input-banner', 'Заполни окружение, релиз, RC и коммиты.');
    return;
  }
  showBanner('input-banner', null);
  const btn = $('btn-find');
  btn.disabled = true; btn.textContent = '⏳ Загружаю тикеты…';
  try {
    const res = await pywebview.api.parse_and_fetch(text);
    if (res.error === 'config') { showSettings('Настройки неполные — заполни и сохрани.'); return; }
    if (res.error === 'no_tickets') { showBanner('input-banner', 'Тикеты в тексте не найдены (ожидается формат DEV-12345).'); return; }
    if (res.error === 'jira_connect') {
      showBanner('input-banner',
        'JIRA недоступна — проверь логин/пароль в <a id="banner-open-settings">настройках</a>.<br><small>' + esc(res.detail || '') + '</small>');
      $('banner-open-settings').onclick = () => showSettings(null);
      return;
    }
    state.tickets = res.tickets.map(t => ({ ...t, selected: true }));
    state.errors = res.errors || {};
    renderTickets();
    updatePreview();
    goStep(2);
  } finally {
    btn.disabled = false; btn.textContent = '🔍 Найти тикеты';
  }
}

// ── шаг 2 ────────────────────────────────────────────────────────────────────
function renderTickets() {
  const box = $('ticket-list');
  box.innerHTML = '';
  for (const t of state.tickets) {
    const row = document.createElement('div');
    row.className = 'ticket';
    const chipType = t.type === 'Bug' ? 'bug' : 'task';
    row.innerHTML =
      `<input type="checkbox" ${t.selected ? 'checked' : ''}>` +
      `<span class="tkey">${esc(t.key)}</span>` +
      `<span class="tsum">${esc(t.summary)}</span>` +
      `<span class="chip ${chipType}">${esc(t.type)}</span>` +
      `<span class="chip st">${esc(t.status)}</span>`;
    row.querySelector('input').onchange = (e) => {
      t.selected = e.target.checked;
      updatePreview();
    };
    box.appendChild(row);
  }
  for (const [key, err] of Object.entries(state.errors)) {
    const row = document.createElement('div');
    row.className = 'ticket err';
    row.innerHTML =
      `<input type="checkbox" disabled>` +
      `<span class="tkey">${esc(key)}</span>` +
      `<span class="tsum">не загружен</span>` +
      `<span class="terr">⚠ ${esc(err)}</span>`;
    box.appendChild(row);
  }
  $('ticket-count').textContent = state.tickets.length + Object.keys(state.errors).length;
}

function updatePreview() {
  const selected = state.tickets.filter(t => t.selected);
  $('selected-count').textContent = '✓ выбрано ' + selected.length;
  const lines = [`📋 На ${esc(state.env)} ${esc(state.release)}-rc${esc(state.rc)}:`];
  for (const t of selected) lines.push(`<a>${esc(t.key)} - ${esc(t.summary)}</a>`);
  $('msg-preview').innerHTML = lines.join('<br><br>');
  $('btn-execute').disabled = selected.length === 0;
}

// ── шаг 3 ────────────────────────────────────────────────────────────────────
function appendLog(line) {          // зовётся из Python через evaluate_js
  const log = $('log');
  log.textContent += line + '\n';
  log.scrollTop = log.scrollHeight;
}

async function onExecute() {
  const keys = state.tickets.filter(t => t.selected).map(t => t.key);
  goStep(3);
  $('log').textContent = '';
  $('result-summary').innerHTML = '';
  $('btn-resend').classList.add('hidden');
  const res = await pywebview.api.execute(keys, state.env, state.release, state.rc);
  const parts = res.results.map(r =>
    r.ok ? `✓ ${esc(r.key)}` : `<span class="warn">⚠ ${esc(r.key)}: ${esc(r.detail)}</span>`);
  parts.push(res.telegram_ok
    ? '✓ Сообщение отправлено в Telegram'
    : `<span class="warn">⚠ Telegram: ${esc(res.telegram_error)}</span>`);
  $('result-summary').innerHTML = parts.join('<br>');
  state.telegramFailed = !res.telegram_ok;
  $('btn-resend').classList.toggle('hidden', res.telegram_ok);
}

async function onResend() {
  $('btn-resend').disabled = true;
  const res = await pywebview.api.resend_telegram();
  $('btn-resend').disabled = false;
  appendLog(res.ok ? '✓ Отправлено со второй попытки' : '⚠ Снова ошибка: ' + res.error);
  $('btn-resend').classList.toggle('hidden', res.ok);
}

// ── настройки ────────────────────────────────────────────────────────────────
function fillSettingsForm(s) {
  $('s-bot-token').value = s.bot_token; $('s-chat-id').value = s.chat_id;
  $('s-proxy').value = s.telegram_proxy;
  $('s-jira-host').value = s.jira_host; $('s-jira-user').value = s.jira_username;
  $('s-jira-pass').value = s.jira_password;
  $('s-testers').value = s.qa_testers.join(', '); $('s-lead').value = s.qa_lead;
}

function collectSettingsForm() {
  return {
    bot_token: $('s-bot-token').value.trim(),
    chat_id: $('s-chat-id').value.trim(),
    telegram_proxy: $('s-proxy').value.trim(),
    jira_host: $('s-jira-host').value.trim(),
    jira_username: $('s-jira-user').value.trim(),
    jira_password: $('s-jira-pass').value,
    qa_testers: $('s-testers').value.split(',').map(s => s.trim()).filter(Boolean),
    qa_lead: $('s-lead').value.trim(),
  };
}

function setBadge(id, good, text) {
  const b = $(id);
  b.classList.remove('hidden', 'good', 'bad');
  b.classList.add(good ? 'good' : 'bad');
  b.textContent = text;
}

async function onSaveSettings() {
  const res = await pywebview.api.save_settings(collectSettingsForm());
  if (!res.valid) { showSettings('Не хватает обязательных полей.'); return; }
  goStep(1);
}

async function onTestTelegram() {
  await pywebview.api.save_settings(collectSettingsForm());
  const res = await pywebview.api.test_telegram();
  setBadge('tg-badge', res.ok, res.ok ? '✓ подключено' : '✗ ' + res.error);
}

async function onTestJira() {
  await pywebview.api.save_settings(collectSettingsForm());
  const res = await pywebview.api.test_jira();
  setBadge('jira-badge', res.ok, res.ok ? '✓ подключено' : '✗ ' + res.error);
}

// ── init ─────────────────────────────────────────────────────────────────────
async function init() {
  $('btn-find').onclick = onFind;
  $('btn-back-1').onclick = () => goStep(1);
  $('btn-execute').onclick = onExecute;
  $('btn-new-run').onclick = () => { $('commits').value = ''; goStep(1); };
  $('btn-copy-log').onclick = () => navigator.clipboard.writeText($('log').textContent);
  $('btn-resend').onclick = onResend;
  $('btn-settings').onclick = () => showSettings(null);
  $('btn-settings-cancel').onclick = () => goStep(1);
  $('btn-settings-save').onclick = onSaveSettings;
  $('btn-test-tg').onclick = onTestTelegram;
  $('btn-test-jira').onclick = onTestJira;

  const s = await pywebview.api.get_settings();
  fillSettingsForm(s);
  if (!s.valid) showSettings('Первый запуск: заполни настройки, чтобы начать.');
  else goStep(1);
}
window.addEventListener('pywebviewready', init);
```

- [ ] **Step 4: Commit**

```bash
git add app/web
git commit -m "feat: wizard frontend (3 steps + settings, dark theme)"
```

---

### Task 8: app/api.py + app/main.py

**Files:**
- Create: `app/api.py`, `app/main.py`

- [ ] **Step 1: api.py**

`app/api.py`:

```python
import json

from core import jira_client
from core.config import Config, load_config, save_config
from core.telegram import build_message, send_telegram
from core.tickets import extract_jira_tickets


class Api:
    def __init__(self):
        self.window = None          # проставляется в main.py после create_window
        self._jira = None
        self._issues = {}           # key -> Issue
        self._last_message = None   # для «Повторить отправку»

    # ── лог в UI ──
    def _log(self, line: str) -> None:
        if self.window:
            self.window.evaluate_js(f"appendLog({json.dumps(line)})")

    # ── настройки ──
    def get_settings(self) -> dict:
        cfg = load_config()
        return {**cfg.__dict__, "valid": cfg.is_valid()}

    def save_settings(self, data: dict) -> dict:
        cfg = Config(
            bot_token=data.get("bot_token", ""),
            chat_id=data.get("chat_id", ""),
            jira_host=data.get("jira_host", ""),
            jira_username=data.get("jira_username", ""),
            jira_password=data.get("jira_password", ""),
            qa_testers=data.get("qa_testers", []),
            qa_lead=data.get("qa_lead", ""),
            telegram_proxy=data.get("telegram_proxy", ""),
        )
        save_config(cfg)
        return {"valid": cfg.is_valid()}

    def test_telegram(self) -> dict:
        cfg = load_config()
        ok, error = send_telegram(cfg, "✅ Release Notify: тестовое сообщение")
        return {"ok": ok, "error": error}

    def test_jira(self) -> dict:
        cfg = load_config()
        try:
            jira = jira_client.connect(cfg)
            jira.myself()
            return {"ok": True, "error": ""}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    # ── шаг 1 → 2 ──
    def parse_and_fetch(self, commits_text: str) -> dict:
        cfg = load_config()
        if not cfg.is_valid():
            return {"error": "config"}
        lines = [l for l in commits_text.splitlines() if l.strip()]
        tickets = extract_jira_tickets(lines)
        if not tickets:
            return {"error": "no_tickets"}
        try:
            self._jira = jira_client.connect(cfg)
        except Exception as e:
            return {"error": "jira_connect", "detail": str(e)[:200]}
        issues, errors = jira_client.find_issues(self._jira, tickets, log=self._log)
        self._issues = {i.key: i for i in issues}
        return {
            "tickets": [
                {"key": i.key, "summary": i.fields.summary,
                 "type": i.fields.issuetype.name, "status": i.fields.status.name}
                for i in issues
            ],
            "errors": errors,
        }

    # ── шаг 3 ──
    def execute(self, selected_keys: list, environment: str,
                release: str, rc: str) -> dict:
        cfg = load_config()
        matrix = jira_client.load_workflow_matrix(log=self._log)
        results = []

        self._log("Меняю статусы…")
        for key in selected_keys:
            issue = self._issues.get(key)
            if issue is None:
                results.append({"key": key, "ok": False, "detail": "тикет не загружен"})
                continue
            target = jira_client.target_status_for(issue)
            status_ok = jira_client.change_issue_status(
                self._jira, issue, matrix, target, log=self._log)
            assignee_ok = jira_client.change_assignee(
                issue, cfg.qa_testers, cfg.qa_lead, log=self._log)
            detail = []
            if not status_ok:
                detail.append("статус не изменён")
            if not assignee_ok:
                detail.append("исполнитель не назначен")
            results.append({"key": key, "ok": status_ok and assignee_ok,
                            "detail": ", ".join(detail)})

        self._log("Отправляю в Telegram…")
        items = [(k, self._issues[k].fields.summary)
                 for k in selected_keys if k in self._issues]
        self._last_message = build_message(cfg.jira_host, environment, release, rc, items)
        tg_ok, tg_error = send_telegram(cfg, self._last_message)
        self._log("✓ Готово" if tg_ok else f"⚠ {tg_error}")
        if not tg_ok:
            self._log("Сообщение, которое не ушло:")
            self._log(self._last_message)

        return {"results": results, "telegram_ok": tg_ok, "telegram_error": tg_error}

    def resend_telegram(self) -> dict:
        if not self._last_message:
            return {"ok": False, "error": "нет сообщения для повтора"}
        cfg = load_config()
        ok, error = send_telegram(cfg, self._last_message)
        return {"ok": ok, "error": error}
```

- [ ] **Step 2: main.py**

`app/main.py`:

```python
import webview

from app.api import Api
from core.resources import resource_path


def main() -> None:
    api = Api()
    window = webview.create_window(
        "Release Notify",
        str(resource_path("app/web/index.html")),
        js_api=api,
        width=760, height=640, min_size=(640, 560),
        background_color="#1a1f27",
    )
    api.window = window
    webview.start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Ручная проверка UI**

Run: `.venv/Scripts/python -m app.main`
Expected: окно 760×640, тёмная тема. Проверить руками:
1. Первый запуск без настроек → экран настроек с баннером.
2. Заполнить настройки (тестовые), «Проверить» обе кнопки → бейджи (✓ или ✗ — по доступности сервисов).
3. Сохранить → шаг 1. Вставить `abc(BugFix DEV-1 Test)`, «Найти тикеты» → при недоступной JIRA баннер с ссылкой на настройки; при доступной — шаг 2 с таблицей.

- [ ] **Step 4: Все тесты по-прежнему зелёные**

Run: `.venv/Scripts/python -m pytest -v`
Expected: passed, 0 failed

- [ ] **Step 5: Commit**

```bash
git add app/api.py app/main.py
git commit -m "feat: pywebview app entry and js api bridge"
```

---

### Task 9: Сборка .exe

**Files:**
- Create: `build.spec`
- Modify: `.gitignore`

- [ ] **Step 1: build.spec**

`build.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('core/workflow_matrix.json', 'core'),
        ('app/web', 'app/web'),
    ],
    hiddenimports=['webview.platforms.edgechromium'],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ReleaseNotify',
    console=False,
    upx=True,
)
```

- [ ] **Step 2: .gitignore — артефакты сборки**

Добавить в конец `.gitignore`:

```
build/
dist/
```

- [ ] **Step 3: Сборка**

Run: `.venv/Scripts/python -m PyInstaller build.spec --noconfirm`
Expected: `Building EXE ... completed successfully`, файл `dist/ReleaseNotify.exe`

- [ ] **Step 4: Проверка .exe**

Run: `./dist/ReleaseNotify.exe` (двойной клик или из терминала)
Expected: окно открывается, настройки читаются из `%APPDATA%\release-notify\settings.json` (заполнены с Task 8), фронтенд и workflow_matrix найдены (нет ошибок про отсутствующие файлы).

- [ ] **Step 5: Commit**

```bash
git add build.spec .gitignore
git commit -m "build: pyinstaller spec for standalone exe"
```

---

### Task 10: Документация

**Files:**
- Modify: `README.md`, `CLAUDE.md`

- [ ] **Step 1: README — секции про UI**

В `README.md` заменить секции Setup/Running на:

```markdown
## Desktop app

Скачай `ReleaseNotify.exe` (или собери: см. Building) и запусти.
При первом запуске заполни настройки (⚙): Telegram, JIRA, команда QA.
Настройки хранятся в `%APPDATA%\release-notify\settings.json`.

## CLI

```bash
pip install -r requirements.txt
python release_notify.py QA 26.1.0 7 \
  "abc12345(BugFix DEV-12345 Fix something)"
```

Конфиг CLI: тот же `settings.json`, при его отсутствии — `.env` (см. `.env.example`).

## Building

```bash
pip install -r requirements-dev.txt
python -m PyInstaller build.spec --noconfirm
# результат: dist/ReleaseNotify.exe
```

## Development

```bash
pip install -r requirements-dev.txt
python -m app.main    # UI из исходников
python -m pytest      # тесты
```
```

- [ ] **Step 2: CLAUDE.md — обновить архитектуру**

Заменить в `CLAUDE.md` секции Setup/Running/Architecture: структура `core/` + `app/` (как в этом плане), запуск UI `python -m app.main`, тесты `python -m pytest`, сборка `python -m PyInstaller build.spec`. Убрать упоминания Playwright/browser_session (устарели). Таблицу env-переменных дополнить: приоритет `%APPDATA%\release-notify\settings.json`, `.env` — fallback.

- [ ] **Step 3: Финальная проверка**

Run: `.venv/Scripts/python -m pytest -v && .venv/Scripts/python release_notify.py --help`
Expected: тесты зелёные, help выводится.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: desktop app usage, updated architecture"
```
