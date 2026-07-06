# GitLab Tag-Based Ticket Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second input mode where the user supplies one release tag (e.g. `26.1.0-rc7`) and the tool pulls commits from GitLab between that tag and the previous one, then extracts Jira tickets the same way as manual paste.

**Architecture:** New framework-agnostic `core/gitlab_client.py` fetches tags and compares two refs via GitLab REST API. `previous_tag()` computes the `from` tag by semver sort. Commit titles feed the existing `extract_jira_tickets()`. Config gets three GitLab fields; `Api` gets a `fetch_from_gitlab()` method reusing shared ticket-fetch logic; the web wizard gets a mode switcher; the CLI gets a `--tag` flag. Manual paste is untouched.

**Tech Stack:** Python 3.11+, `requests`, `pytest`, pywebview (vanilla JS/HTML/CSS frontend).

---

## File Structure

- Create: `core/gitlab_client.py` — GitLab API access + `previous_tag()` semver logic.
- Modify: `core/config.py` — add `gitlab_host`/`gitlab_token`/`gitlab_project` fields, env map, `gitlab_ready()`.
- Modify: `app/api.py` — `_config_from()` reads new fields; new `fetch_from_gitlab()`; extract shared `_fetch_tickets()`.
- Modify: `app/web/index.html`, `app/web/app.js`, `app/web/style.css` — mode switcher + GitLab tag field + Settings GitLab section.
- Modify: `release_notify.py` — `--tag` flag, `commits` becomes optional.
- Create: `tests/test_gitlab_client.py` — `previous_tag`, `list_tags`, `compare`, `commits_for_tag`.
- Modify: `tests/test_config.py` — new-field resolution + `gitlab_ready()`.

---

## Task 1: Config — GitLab fields

**Files:**
- Modify: `core/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
def test_gitlab_fields_from_json(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({
        "gitlab_host": "gitlab.example.com",
        "gitlab_token": "glpat-xxx",
        "gitlab_project": "group/repo",
    }), encoding="utf-8")

    cfg = load_config(path=p, load_env_file=False)

    assert cfg.gitlab_host == "gitlab.example.com"
    assert cfg.gitlab_token == "glpat-xxx"
    assert cfg.gitlab_project == "group/repo"


def test_gitlab_fields_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("GITLAB_HOST", "gitlab.env.com")
    monkeypatch.setenv("GITLAB_TOKEN", "env-token")
    monkeypatch.setenv("GITLAB_PROJECT", "42")

    cfg = load_config(path=tmp_path / "missing.json", load_env_file=False)

    assert cfg.gitlab_host == "gitlab.env.com"
    assert cfg.gitlab_token == "env-token"
    assert cfg.gitlab_project == "42"


def test_gitlab_ready():
    assert not Config().gitlab_ready()
    assert not Config(gitlab_host="h", gitlab_token="t").gitlab_ready()
    assert Config(gitlab_host="h", gitlab_token="t",
                  gitlab_project="p").gitlab_ready()


def test_gitlab_fields_do_not_affect_is_valid():
    # is_valid ignores GitLab (optional feature)
    base = Config(bot_token="t", chat_id="c", jira_host="h",
                  jira_username="u", jira_password="p")
    assert base.is_valid()
    assert Config(gitlab_host="h").is_valid() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `Config` has no `gitlab_host` / `gitlab_ready`.

- [ ] **Step 3: Add fields, env map, and `gitlab_ready()`**

In `core/config.py`, add to the `Config` dataclass after `telegram_proxy`:

```python
    gitlab_host: str = ""
    gitlab_token: str = ""
    gitlab_project: str = ""
```

Add `gitlab_ready()` method to `Config` (after `is_valid`):

```python
    def gitlab_ready(self) -> bool:
        return all([self.gitlab_host, self.gitlab_token, self.gitlab_project])
```

Add to `_ENV_MAP`:

```python
    "gitlab_host": "GITLAB_HOST",
    "gitlab_token": "GITLAB_TOKEN",
    "gitlab_project": "GITLAB_PROJECT",
```

(No other changes needed — the generic `_ENV_MAP` loop in `load_config` and
`save_config`'s `cfg.__dict__` dump already cover string fields.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (all, including the pre-existing roundtrip test which now also
roundtrips the new fields via `cfg.__dict__`).

- [ ] **Step 5: Commit**

```bash
git add core/config.py tests/test_config.py
git commit -m "feat: add GitLab config fields (host/token/project)"
```

---

## Task 2: gitlab_client — `previous_tag()` semver logic

**Files:**
- Create: `core/gitlab_client.py`
- Test: `tests/test_gitlab_client.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gitlab_client.py`:

```python
import pytest

from core.gitlab_client import previous_tag


def test_previous_tag_within_release():
    tags = ["26.1.0-rc5", "26.1.0-rc6", "26.1.0-rc7"]
    assert previous_tag(tags, "26.1.0-rc7") == "26.1.0-rc6"


def test_previous_tag_crosses_release_boundary():
    tags = ["26.0.5-rc4", "26.1.0-rc1", "26.1.0-rc2"]
    assert previous_tag(tags, "26.1.0-rc1") == "26.0.5-rc4"


def test_previous_tag_input_order_irrelevant():
    tags = ["26.1.0-rc7", "26.1.0-rc5", "26.1.0-rc6"]
    assert previous_tag(tags, "26.1.0-rc7") == "26.1.0-rc6"


def test_previous_tag_ignores_non_matching_tags():
    tags = ["latest", "release", "26.1.0-rc1", "26.1.0-rc2"]
    assert previous_tag(tags, "26.1.0-rc2") == "26.1.0-rc1"


def test_previous_tag_raises_when_target_is_earliest():
    tags = ["26.1.0-rc1", "26.1.0-rc2"]
    with pytest.raises(ValueError):
        previous_tag(tags, "26.1.0-rc1")


def test_previous_tag_raises_when_target_missing():
    tags = ["26.1.0-rc1", "26.1.0-rc2"]
    with pytest.raises(ValueError):
        previous_tag(tags, "99.9.9-rc9")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_gitlab_client.py -v`
Expected: FAIL — module `core.gitlab_client` does not exist.

- [ ] **Step 3: Create module with `previous_tag()`**

Create `core/gitlab_client.py`:

```python
import re

import requests

from .config import Config

_TAG_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)-rc(\d+)$")


def _version_key(tag: str) -> tuple[int, int, int, int] | None:
    m = _TAG_RE.match(tag)
    if not m:
        return None
    return tuple(int(g) for g in m.groups())


def previous_tag(tags: list[str], target: str) -> str:
    """Ближайший меньший тег по semver. ValueError если target не найден
    или предыдущего нет."""
    if _version_key(target) is None:
        raise ValueError(f"Тег '{target}' не соответствует формату X.Y.Z-rcN")
    parsed = [(t, _version_key(t)) for t in tags]
    parsed = [(t, k) for t, k in parsed if k is not None]
    parsed.sort(key=lambda tk: tk[1])
    target_key = _version_key(target)
    prev = None
    for t, k in parsed:
        if k < target_key:
            prev = t
        elif k >= target_key:
            break
    if prev is None:
        raise ValueError(f"Нет предыдущего тега для '{target}'")
    return prev
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_gitlab_client.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add core/gitlab_client.py tests/test_gitlab_client.py
git commit -m "feat: add previous_tag semver resolution for GitLab tags"
```

---

## Task 3: gitlab_client — `list_tags()` with pagination

**Files:**
- Modify: `core/gitlab_client.py`
- Test: `tests/test_gitlab_client.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gitlab_client.py`:

```python
from unittest.mock import MagicMock

from core.config import Config
from core.gitlab_client import list_tags


def _cfg():
    return Config(gitlab_host="gitlab.example.com",
                  gitlab_token="tok", gitlab_project="group/repo")


def test_list_tags_paginates(monkeypatch):
    page1 = [{"name": f"26.1.0-rc{i}"} for i in range(1, 101)]
    page2 = [{"name": "26.1.0-rc101"}]
    responses = [page1, page2]
    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append((url, dict(params)))
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = responses[params["page"] - 1]
        return resp

    monkeypatch.setattr("core.gitlab_client.requests.get", fake_get)

    tags = list_tags(_cfg())

    assert tags[0] == "26.1.0-rc1"
    assert tags[-1] == "26.1.0-rc101"
    assert len(tags) == 101
    # project id URL-encoded
    assert "group%2Frepo" in calls[0][0]


def test_list_tags_raises_on_http_error(monkeypatch):
    def fake_get(url, headers=None, params=None, timeout=None):
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 401
        resp.text = "unauthorized"
        return resp

    monkeypatch.setattr("core.gitlab_client.requests.get", fake_get)

    with pytest.raises(RuntimeError):
        list_tags(_cfg())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_gitlab_client.py -k list_tags -v`
Expected: FAIL — `list_tags` not defined.

- [ ] **Step 3: Implement `list_tags` + shared helpers**

Add to `core/gitlab_client.py` (after imports / `_version_key`):

```python
def _headers(cfg: Config) -> dict:
    return {"PRIVATE-TOKEN": cfg.gitlab_token}


def _project_url(cfg: Config, suffix: str) -> str:
    project = requests.utils.quote(cfg.gitlab_project, safe="")
    return f"https://{cfg.gitlab_host}/api/v4/projects/{project}{suffix}"


def list_tags(cfg: Config) -> list[str]:
    tags: list[str] = []
    page = 1
    while True:
        resp = requests.get(
            _project_url(cfg, "/repository/tags"),
            headers=_headers(cfg),
            params={"per_page": 100, "page": page},
            timeout=15,
        )
        if not resp.ok:
            raise RuntimeError(
                f"GitLab tags error: {resp.status_code} {resp.text}")
        batch = resp.json()
        if not batch:
            break
        tags.extend(item["name"] for item in batch)
        if len(batch) < 100:
            break
        page += 1
    return tags
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_gitlab_client.py -k list_tags -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add core/gitlab_client.py tests/test_gitlab_client.py
git commit -m "feat: add GitLab list_tags with pagination"
```

---

## Task 4: gitlab_client — `compare()`

**Files:**
- Modify: `core/gitlab_client.py`
- Test: `tests/test_gitlab_client.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gitlab_client.py`:

```python
from core.gitlab_client import compare


def test_compare_returns_commit_titles(monkeypatch):
    def fake_get(url, headers=None, params=None, timeout=None):
        assert params["from"] == "26.1.0-rc6"
        assert params["to"] == "26.1.0-rc7"
        resp = MagicMock()
        resp.ok = True
        resp.json.return_value = {"commits": [
            {"title": "BugFix DEV-123 fix a"},
            {"title": "BugFix DEV-456 fix b"},
        ]}
        return resp

    monkeypatch.setattr("core.gitlab_client.requests.get", fake_get)

    commits = compare(_cfg(), "26.1.0-rc6", "26.1.0-rc7")

    assert commits == ["BugFix DEV-123 fix a", "BugFix DEV-456 fix b"]


def test_compare_raises_on_http_error(monkeypatch):
    def fake_get(url, headers=None, params=None, timeout=None):
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 404
        resp.text = "not found"
        return resp

    monkeypatch.setattr("core.gitlab_client.requests.get", fake_get)

    with pytest.raises(RuntimeError):
        compare(_cfg(), "a", "b")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_gitlab_client.py -k compare -v`
Expected: FAIL — `compare` not defined.

- [ ] **Step 3: Implement `compare`**

Add to `core/gitlab_client.py`:

```python
def compare(cfg: Config, from_tag: str, to_tag: str) -> list[str]:
    resp = requests.get(
        _project_url(cfg, "/repository/compare"),
        headers=_headers(cfg),
        params={"from": from_tag, "to": to_tag},
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(
            f"GitLab compare error: {resp.status_code} {resp.text}")
    return [c["title"] for c in resp.json().get("commits", [])]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_gitlab_client.py -k compare -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add core/gitlab_client.py tests/test_gitlab_client.py
git commit -m "feat: add GitLab compare (commit titles between two refs)"
```

---

## Task 5: gitlab_client — `commits_for_tag()` orchestrator

**Files:**
- Modify: `core/gitlab_client.py`
- Test: `tests/test_gitlab_client.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gitlab_client.py`:

```python
from core.gitlab_client import commits_for_tag


def test_commits_for_tag_orchestrates(monkeypatch):
    monkeypatch.setattr("core.gitlab_client.list_tags",
                        lambda cfg: ["26.1.0-rc6", "26.1.0-rc7"])
    monkeypatch.setattr("core.gitlab_client.compare",
                        lambda cfg, f, t: [f"commits {f}->{t}"])

    from_tag, to_tag, commits = commits_for_tag(_cfg(), "26.1.0-rc7")

    assert from_tag == "26.1.0-rc6"
    assert to_tag == "26.1.0-rc7"
    assert commits == ["commits 26.1.0-rc6->26.1.0-rc7"]


def test_commits_for_tag_propagates_no_previous(monkeypatch):
    monkeypatch.setattr("core.gitlab_client.list_tags",
                        lambda cfg: ["26.1.0-rc7"])
    with pytest.raises(ValueError):
        commits_for_tag(_cfg(), "26.1.0-rc7")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_gitlab_client.py -k commits_for_tag -v`
Expected: FAIL — `commits_for_tag` not defined.

- [ ] **Step 3: Implement `commits_for_tag`**

Add to `core/gitlab_client.py`:

```python
def commits_for_tag(cfg: Config, target: str) -> tuple[str, str, list[str]]:
    """Возвращает (from_tag, to_tag, commit_titles). ValueError если нет
    предыдущего тега."""
    tags = list_tags(cfg)
    from_tag = previous_tag(tags, target)
    commits = compare(cfg, from_tag, target)
    return from_tag, target, commits
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_gitlab_client.py -v`
Expected: PASS (all gitlab_client tests).

- [ ] **Step 5: Commit**

```bash
git add core/gitlab_client.py tests/test_gitlab_client.py
git commit -m "feat: add commits_for_tag orchestrator"
```

---

## Task 6: Api — shared `_fetch_tickets()` + `fetch_from_gitlab()`

**Files:**
- Modify: `app/api.py`

- [ ] **Step 1: Read current `parse_and_fetch`**

Confirm the current body of `parse_and_fetch` in `app/api.py:60-81` (extract →
connect → find_issues → build response). No test file exists for `Api`
(pywebview bridge); this task is refactor + new method verified manually and by
the CLI/core tests. Keep changes behavior-preserving for the manual path.

- [ ] **Step 2: Add GitLab import and update `_config_from`**

In `app/api.py`, add import at top:

```python
from core import gitlab_client
```

In `_config_from`, add the three fields to the `Config(...)` call:

```python
            gitlab_host=data.get("gitlab_host", ""),
            gitlab_token=data.get("gitlab_token", ""),
            gitlab_project=data.get("gitlab_project", ""),
```

- [ ] **Step 3: Extract shared `_fetch_tickets` and rewrite `parse_and_fetch`**

Replace the current `parse_and_fetch` method with:

```python
    # ── общий путь: строки коммитов → тикеты из JIRA ──
    def _fetch_tickets(self, cfg, commits: list[str]) -> dict:
        tickets = extract_jira_tickets(commits)
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

    # ── шаг 1 → 2: ручная вставка ──
    def parse_and_fetch(self, commits_text: str) -> dict:
        cfg = load_config()
        if not cfg.is_valid():
            return {"error": "config"}
        lines = [l for l in commits_text.splitlines() if l.strip()]
        return self._fetch_tickets(cfg, lines)

    # ── шаг 1 → 2: из GitLab по тегу ──
    def fetch_from_gitlab(self, tag: str) -> dict:
        cfg = load_config()
        if not cfg.is_valid():
            return {"error": "config"}
        if not cfg.gitlab_ready():
            return {"error": "gitlab_config"}
        tag = (tag or "").strip()
        if not tag:
            return {"error": "no_tag"}
        try:
            from_tag, to_tag, commits = gitlab_client.commits_for_tag(cfg, tag)
        except ValueError as e:
            return {"error": "no_previous_tag", "detail": str(e)}
        except Exception as e:
            return {"error": "gitlab_fetch", "detail": str(e)[:200]}
        self._log(f"GitLab: коммиты {from_tag} → {to_tag}")
        result = self._fetch_tickets(cfg, commits)
        result["from_tag"] = from_tag
        result["to_tag"] = to_tag
        return result
```

- [ ] **Step 4: Verify nothing else broke — run full test suite**

Run: `python -m pytest -v`
Expected: PASS (all existing + new core tests; `app/api.py` has no dedicated
tests but importing it during collection must not error).

- [ ] **Step 5: Add a settings test-connection method (optional but paired)**

Add to `app/api.py` after `test_jira`:

```python
    def test_gitlab(self, data: dict) -> dict:
        cfg = self._config_from(data)
        try:
            gitlab_client.list_tags(cfg)
            return {"ok": True, "error": ""}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}
```

- [ ] **Step 6: Commit**

```bash
git add app/api.py
git commit -m "feat: add fetch_from_gitlab and GitLab settings test to Api"
```

---

## Task 7: CLI — `--tag` flag

**Files:**
- Modify: `release_notify.py`

- [ ] **Step 1: Make `commits` optional and add `--tag`**

In `release_notify.py`, change the `commits` argument and add `--tag`:

```python
    parser.add_argument("commits", nargs="*",
                        help='Commit strings, e.g. "abc123(BugFix DEV-123 Fix something)"')
    parser.add_argument("--tag",
                        help="GitLab release tag, e.g. 26.1.0-rc7 "
                             "(pulls commits between it and the previous tag)")
```

- [ ] **Step 2: Add import**

Add near the other core imports:

```python
from core import gitlab_client
```

- [ ] **Step 3: Branch on `--tag` before ticket extraction**

Replace the block that builds `tickets` (currently
`tickets = extract_jira_tickets(args.commits)` and the following check) with:

```python
    if args.tag:
        if not cfg.gitlab_ready():
            print("GitLab not configured: set gitlab_host/token/project.")
            sys.exit(1)
        try:
            from_tag, to_tag, commits = gitlab_client.commits_for_tag(cfg, args.tag)
        except ValueError as e:
            print(str(e))
            sys.exit(1)
        except Exception as e:
            print(f"GitLab error: {e}")
            sys.exit(1)
        print(f"GitLab commits: {from_tag} -> {to_tag} ({len(commits)} commits)")
    elif args.commits:
        commits = args.commits
    else:
        print("Provide commit strings or --tag <release-tag>.")
        sys.exit(1)

    tickets = extract_jira_tickets(commits)
    if not tickets:
        print("No Jira tickets found in commits.")
        return
    print(f"Tickets found: {tickets}")
```

- [ ] **Step 4: Manual smoke test (no network needed for arg parsing)**

Run: `python release_notify.py QA 26.1.0 7`
Expected: exits with "Provide commit strings or --tag <release-tag>." (config
must be valid; if config incomplete it exits earlier — that's fine).

Run: `python release_notify.py --help`
Expected: help shows `--tag` and optional `commits`.

- [ ] **Step 5: Commit**

```bash
git add release_notify.py
git commit -m "feat: add --tag flag to CLI for GitLab-based ticket extraction"
```

---

## Task 8: Web UI — Settings GitLab section

**Files:**
- Modify: `app/web/index.html`, `app/web/app.js`, `app/web/style.css`

- [ ] **Step 1: Read current Settings markup and save/load JS**

Open `app/web/index.html` and `app/web/app.js`. Locate the Settings screen
(JIRA / Telegram / QA sections) and the functions that read settings into the
form and collect the form into the payload passed to `save_settings` /
`test_jira`. Match their exact patterns (field ids, container classes).

- [ ] **Step 2: Add GitLab fields to Settings markup**

In `app/web/index.html`, add a GitLab section mirroring the JIRA section, with
inputs `#gitlab_host`, `#gitlab_token` (type=password), `#gitlab_project`, and
a "Проверить" button `#test-gitlab-btn` mirroring the JIRA test button.

- [ ] **Step 3: Wire load/save/test in app.js**

In the settings-load function, set the three inputs from the settings object
(`s.gitlab_host` etc.). In the settings-collect function, include
`gitlab_host`, `gitlab_token`, `gitlab_project` in the payload object. Add a
click handler for `#test-gitlab-btn` calling `window.pywebview.api.test_gitlab(payload)`
and showing ok/error the same way the JIRA test does.

- [ ] **Step 4: Manual verify**

Run: `python -m app.main`
Fill GitLab fields, Save, reopen Settings — values persist. Click Проверить —
shows success/failure. (Requires real GitLab creds for a green result; a wrong
token should show the error string, proving the round-trip works.)

- [ ] **Step 5: Commit**

```bash
git add app/web/index.html app/web/app.js app/web/style.css
git commit -m "feat: add GitLab section to Settings screen"
```

---

## Task 9: Web UI — Step 1 mode switcher

**Files:**
- Modify: `app/web/index.html`, `app/web/app.js`, `app/web/style.css`

- [ ] **Step 1: Read current Step 1 markup and its submit handler**

In `app/web/index.html` find the Step 1 (Ввод) block with the commits textarea
and its "next" button. In `app/web/app.js` find the handler that calls
`window.pywebview.api.parse_and_fetch(textarea.value)` and renders the returned
tickets into Step 2.

- [ ] **Step 2: Add mode switcher markup**

In Step 1, add two radio buttons / tabs above the input area:
«Из GitLab по тегу» (`#mode-gitlab`) and «Вставить вручную» (`#mode-manual`,
default checked). Add a GitLab sub-block (hidden unless GitLab mode) with a
single text input `#gitlab-tag` (placeholder `26.1.0-rc7`) and keep the existing
textarea in a manual sub-block. Add a small read-only line `#range-info` to show
the computed `from → to` after a GitLab fetch.

- [ ] **Step 3: Toggle sub-blocks and branch the submit handler**

In `app/web/app.js`:
- Add change handlers on the radios that show/hide the two sub-blocks.
- In the Step-1 submit handler, branch on the selected mode:

```javascript
let result;
if (document.querySelector('#mode-gitlab').checked) {
  const tag = document.querySelector('#gitlab-tag').value.trim();
  result = await window.pywebview.api.fetch_from_gitlab(tag);
} else {
  result = await window.pywebview.api.parse_and_fetch(textarea.value);
}
```

- After a successful GitLab result, show the range:

```javascript
if (result.from_tag) {
  document.querySelector('#range-info').textContent =
    `Коммиты: ${result.from_tag} → ${result.to_tag}`;
}
```

- [ ] **Step 4: Handle new error codes**

In the same handler's error branch, map the new `result.error` values to
Russian messages (reuse the existing error-display mechanism):

```javascript
const messages = {
  config: 'Заполните настройки (Telegram/JIRA).',
  gitlab_config: 'GitLab не настроен — заполните host/token/project в настройках.',
  no_tag: 'Укажите тег релиза.',
  no_previous_tag: result.detail || 'Нет предыдущего тега.',
  gitlab_fetch: 'Ошибка GitLab: ' + (result.detail || ''),
  no_tickets: 'В коммитах не найдено тикетов.',
  jira_connect: 'Не удалось подключиться к JIRA: ' + (result.detail || ''),
};
// show messages[result.error] || result.error
```

Match the exact call the existing code uses to display an error (alert, a status
div, etc.) — do not invent a new mechanism; reuse what manual mode already does.

- [ ] **Step 5: Manual verify both modes**

Run: `python -m app.main`
- Manual mode: paste a commit line with a ticket → Step 2 lists it (unchanged
  behavior).
- GitLab mode: enter a real tag → Step 2 lists tickets and `#range-info` shows
  `from → to`. Enter the earliest tag → error message "Нет предыдущего тега".

- [ ] **Step 6: Commit**

```bash
git add app/web/index.html app/web/app.js app/web/style.css
git commit -m "feat: add GitLab/manual mode switcher to Step 1"
```

---

## Task 10: Docs

**Files:**
- Modify: `CLAUDE.md`, `README` (if it documents env vars / usage), `.env.example`

- [ ] **Step 1: Update env var table and architecture notes**

In `CLAUDE.md`:
- Add `core/gitlab_client.py` to the `core/` architecture list: "GitLab API
  access — `list_tags()`, `previous_tag()` (semver sort), `compare()`,
  `commits_for_tag()` (previous-tag → compare orchestrator)."
- Add rows to the env-var table: `GITLAB_HOST`, `GITLAB_TOKEN`,
  `GITLAB_PROJECT` (all "no" required — optional feature).
- Note the CLI `--tag` alternative in the Running section.

- [ ] **Step 2: Update `.env.example`**

Add:

```
# GitLab (optional — enables --tag / "Из GitLab по тегу" mode)
GITLAB_HOST=gitlab.yourcompany.com
GITLAB_TOKEN=glpat-xxxxxxxx
GITLAB_PROJECT=group/repo
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md .env.example README*
git commit -m "docs: document GitLab tag mode (config, CLI --tag, env vars)"
```

---

## Self-Review Notes

- **Spec coverage:** config fields (T1), `previous_tag`/`list_tags`/`compare`/
  `commits_for_tag` (T2–T5), Api `fetch_from_gitlab` + shared helper (T6), CLI
  `--tag` (T7), Settings GitLab section (T8), Step-1 switcher + errors (T9),
  docs (T10). All spec sections mapped.
- **Error handling:** `gitlab_config`, `no_previous_tag`, `gitlab_fetch`,
  `no_tag`, `no_tickets` covered in T6/T9; CLI equivalents in T7.
- **Type consistency:** `commits_for_tag` returns `(from_tag, to_tag, commits)`
  everywhere; `previous_tag(tags, target)` signature stable across T2/T5; Api
  method names `fetch_from_gitlab`/`test_gitlab` consistent between api and JS.
- **Out of scope (per spec):** local git, clone-by-URL, other hosts, per-release
  project, "from start of history" fallback — none added.
