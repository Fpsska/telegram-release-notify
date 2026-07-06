import json

from core import gitlab_client, jira_client
from core.config import Config, load_config, save_config
from core.telegram import build_message, send_telegram
from core.tickets import extract_jira_tickets


class Api:
    def __init__(self):
        # underscore-имя: pywebview не рефлексит приватные атрибуты js_api
        self._window = None         # проставляется в main.py после create_window
        self._jira = None
        self._issues = {}           # key -> Issue
        self._last_message = None   # для «Повторить отправку»

    # ── лог в UI ──
    def _log(self, line: str) -> None:
        if self._window:
            self._window.evaluate_js(f"appendLog({json.dumps(line)})")

    # ── настройки ──
    @staticmethod
    def _config_from(data: dict) -> Config:
        return Config(
            bot_token=data.get("bot_token", ""),
            chat_id=data.get("chat_id", ""),
            jira_host=data.get("jira_host", ""),
            jira_username=data.get("jira_username", ""),
            jira_password=data.get("jira_password", ""),
            qa_testers=data.get("qa_testers", []),
            qa_lead=data.get("qa_lead", ""),
            telegram_proxy=data.get("telegram_proxy", ""),
            gitlab_host=data.get("gitlab_host", ""),
            gitlab_token=data.get("gitlab_token", ""),
            gitlab_project=data.get("gitlab_project", ""),
        )

    def get_settings(self) -> dict:
        cfg = load_config()
        return {**cfg.__dict__, "valid": cfg.is_valid()}

    def save_settings(self, data: dict) -> dict:
        cfg = self._config_from(data)
        save_config(cfg)
        return {"valid": cfg.is_valid()}

    def test_telegram(self, data: dict) -> dict:
        cfg = self._config_from(data)
        ok, error = send_telegram(cfg, "✅ Release Notify: тестовое сообщение")
        return {"ok": ok, "error": error}

    def test_jira(self, data: dict) -> dict:
        cfg = self._config_from(data)
        try:
            jira = jira_client.connect(cfg)
            jira.myself()
            return {"ok": True, "error": ""}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    def test_gitlab(self, data: dict) -> dict:
        cfg = self._config_from(data)
        try:
            gitlab_client.list_tags(cfg)
            return {"ok": True, "error": ""}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    # ── список тегов для выпадающего списка в GitLab-режиме ──
    def get_gitlab_tags(self) -> dict:
        cfg = load_config()
        if not cfg.gitlab_ready():
            return {"error": "gitlab_config"}
        try:
            tags = gitlab_client.list_tags(cfg)
        except Exception as e:
            return {"error": "gitlab_fetch", "detail": str(e)[:200]}
        return {"tags": tags}

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
        if "error" not in result:
            result["from_tag"] = from_tag
            result["to_tag"] = to_tag
        return result

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
