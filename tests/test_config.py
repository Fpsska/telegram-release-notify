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
