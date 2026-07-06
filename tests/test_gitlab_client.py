from unittest.mock import MagicMock

import pytest

from core.config import Config
from core.gitlab_client import commits_for_tag, compare, list_tags, previous_tag


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


def test_previous_tag_raises_when_target_bad_format():
    tags = ["26.1.0-rc1", "26.1.0-rc2"]
    with pytest.raises(ValueError):
        previous_tag(tags, "not-a-tag")


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
