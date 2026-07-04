# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language

Communicate with the user in Russian.

## Setup

```bash
pip install -r requirements-dev.txt
```

## Running

UI (desktop app, pywebview):
```bash
python -m app.main
```

CLI:
```bash
python release_notify.py <environment> <release> <rc> <commit1> [commit2 ...]
```

Example:
```bash
python release_notify.py QA 26.1.0 7 \
  "abc12345(BugFix DEV-12345 Fix something)" \
  "def67890(BugFix DEV-67890 Fix something else)"
```

Tests:
```bash
python -m pytest
```

Build via PyInstaller (`dist/ReleaseNotify.exe` on Windows, `dist/ReleaseNotify.app` on macOS; no cross-compilation — build on the target OS):
```bash
python -m PyInstaller build.spec --noconfirm
```

CI (`.github/workflows/build.yml`) runs tests and builds Windows + macOS (arm64, Intel) on every push to `main`; pushing a `v*` tag publishes the builds to GitHub Releases. macOS `.app` is unsigned — first launch requires right-click → Open (Gatekeeper).

## Architecture

`core/` — framework-agnostic logic shared by the UI and the CLI:

- `config.py` — `Config` dataclass + `load_config()`/`save_config()`. Settings resolve from `%APPDATA%\release-notify\settings.json` (or `~/.config/release-notify/settings.json` if `APPDATA` unset) first; any field missing there falls back to environment variables / `.env` (loaded via `python-dotenv`). `settings_path()` uses `APP_NAME = "release-notify"`.
- `tickets.py` — `extract_jira_tickets()` extracts Jira ticket IDs (e.g. `DEV-12345`) from commit strings via regex `[A-Z]+-\d+`, de-duplicated in order of appearance.
- `jira_client.py` — JIRA API access via `python-jira`. `connect()` opens a session; `find_issues()` fetches issues and collects per-ticket errors; `load_workflow_matrix()` reads `core/workflow_matrix.json` (via `resource_path()`, so it works both from source and from the PyInstaller bundle); `find_path_to_target()` does BFS over the matrix to find the transition path from an issue's current status to its target status; `change_issue_status()` walks that path calling `jira.transition_issue()`; `target_status_for()` maps issue type → target status (`Bug` → `DEV Ready For Testing`, others → `Testing`); `pick_assignee()`/`change_assignee()` assign to the reporter if they're a QA tester, otherwise to the QA lead.
- `telegram.py` — `build_message()` builds the HTML-formatted Telegram message; `send_telegram()` posts it via the Bot API, with optional SOCKS5/HTTP proxy support (`cfg.telegram_proxy`, requires `requests[socks]`).
- `resources.py` — `resource_path()` resolves a relative path against `sys._MEIPASS` when frozen by PyInstaller, or against the repo root when running from source.

`app/` — desktop UI:

- `main.py` — creates the pywebview window (`app/web/index.html`) with `js_api=Api()`. pywebview picks the backend per platform (EdgeChromium/WebView2 on Windows, Cocoa/WebKit on macOS); `build.spec` lists the matching backend in `hiddenimports` since PyInstaller can't see that dynamic import.
- `api.py` — `Api` class, the js_api bridge exposed to the frontend (`get_settings`, `save_settings`, `test_telegram`, `test_jira`, `parse_and_fetch`, `execute`, `resend_telegram`). **Important:** the window reference is stored as `self._window` (leading underscore) and assigned *after* `create_window()` in `main.py`. pywebview reflects only public (non-underscore) attributes of the js_api object to build the JS bridge — a public `window`/similar attribute here would break that reflection and expose/shadow unintended methods to the frontend. Keep any non-API internal state on underscore-prefixed attributes.
- `web/` — frontend (`index.html`, `app.js`, `style.css`): a 3-step wizard (Ввод → Проверка → Результат) plus a Settings screen (Telegram / JIRA / QA team), talking to `Api` via pywebview's js_api.

`release_notify.py` — thin CLI: parses args with `argparse`, loads config via `core.config.load_config()`, then calls the same `core` functions the UI uses (extract tickets → fetch issues → change status → change assignee → build & send Telegram message).

`tests/` — pytest suite covering `core/config.py`, `core/jira_client.py`, `core/telegram.py`, `core/tickets.py`.

## Environment variables

Only used as a fallback when a field is missing from `%APPDATA%\release-notify\settings.json` (see `core/config.py`); normally configured through the app's Settings screen instead.

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | yes | Telegram bot token |
| `CHAT_ID` | yes | Target Telegram chat/group ID |
| `JIRA_HOST` | yes | Jira hostname, e.g. `jira.yourcompany.com` |
| `JIRA_USERNAME` | yes | Jira API username |
| `JIRA_PASSWORD` | yes | Jira API password |
| `JIRA_QA_TESTERS` | no | Comma-separated Jira usernames of QA testers |
| `JIRA_QA_LEAD` | no | Jira username of the QA lead (fallback assignee) |
| `TELEGRAM_PROXY` | no | Proxy for Telegram API, e.g. `socks5://user:pass@host:port` |
