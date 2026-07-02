import requests

from core.config import Config
from core.telegram import build_message, send_telegram


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


def test_send_telegram_catches_request_exceptions(monkeypatch):
    def raise_invalid_proxy(*args, **kwargs):
        raise requests.exceptions.InvalidProxyURL("bad proxy")

    monkeypatch.setattr(requests, "post", raise_invalid_proxy)
    cfg = Config(bot_token="t", chat_id="c")
    ok, err = send_telegram(cfg, "msg")
    assert ok is False
    assert "bad proxy" in err
