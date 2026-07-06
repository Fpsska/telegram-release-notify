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
    gitlab_host: str = ""
    gitlab_token: str = ""
    gitlab_project: str = ""

    def is_valid(self) -> bool:
        return all([self.bot_token, self.chat_id, self.jira_host,
                    self.jira_username, self.jira_password])

    def gitlab_ready(self) -> bool:
        return all([self.gitlab_host, self.gitlab_token, self.gitlab_project])


_ENV_MAP = {
    "bot_token": "BOT_TOKEN",
    "chat_id": "CHAT_ID",
    "jira_host": "JIRA_HOST",
    "jira_username": "JIRA_USERNAME",
    "jira_password": "JIRA_PASSWORD",
    "qa_lead": "JIRA_QA_LEAD",
    "telegram_proxy": "TELEGRAM_PROXY",
    "gitlab_host": "GITLAB_HOST",
    "gitlab_token": "GITLAB_TOKEN",
    "gitlab_project": "GITLAB_PROJECT",
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
        json_value = data.get(attr)
        if json_value is not None and not isinstance(json_value, str):
            json_value = str(json_value)
        value = json_value or os.environ.get(env_key, "")
        setattr(cfg, attr, value.strip())

    testers = data.get("qa_testers")
    if isinstance(testers, list):
        cfg.qa_testers = [str(u).strip() for u in testers if str(u).strip()]
    else:
        raw = os.environ.get("JIRA_QA_TESTERS", "")
        cfg.qa_testers = [u.strip() for u in raw.split(",") if u.strip()]
    return cfg


def save_config(cfg: Config, path: Path | None = None) -> None:
    p = path or settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg.__dict__, ensure_ascii=False, indent=2),
                 encoding="utf-8")
