import re

import requests

from .config import Config

_TAG_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)-rc(\d+)$")


def _version_key(tag: str) -> tuple[int, int, int, int] | None:
    m = _TAG_RE.match(tag)
    if not m:
        return None
    a, b, c, d = m.groups()
    return (int(a), int(b), int(c), int(d))


def _headers(cfg: Config) -> dict:
    return {"PRIVATE-TOKEN": cfg.gitlab_token}


def _project_url(cfg: Config, suffix: str) -> str:
    host = re.sub(r"^https?://", "", cfg.gitlab_host.strip()).rstrip("/")
    project = requests.utils.quote(cfg.gitlab_project, safe="")
    return f"https://{host}/api/v4/projects/{project}{suffix}"


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


def commits_for_tag(cfg: Config, target: str) -> tuple[str, str, list[str]]:
    """Возвращает (from_tag, to_tag, commit_titles). ValueError если нет
    предыдущего тега."""
    tags = list_tags(cfg)
    from_tag = previous_tag(tags, target)
    commits = compare(cfg, from_tag, target)
    return from_tag, target, commits


def previous_tag(tags: list[str], target: str) -> str:
    """Ближайший меньший тег по semver. ValueError если target не найден
    или предыдущего нет."""
    if _version_key(target) is None:
        raise ValueError(f"Тег '{target}' не соответствует формату X.Y.Z-rcN")
    parsed = [(t, _version_key(t)) for t in tags]
    parsed = [(t, k) for t, k in parsed if k is not None]
    parsed.sort(key=lambda tk: tk[1])
    target_key = _version_key(target)
    keys = [k for _, k in parsed]
    if target_key not in keys:
        raise ValueError(f"Тег '{target}' не найден в списке тегов")
    prev = None
    for t, k in parsed:
        if k < target_key:
            prev = t
        elif k >= target_key:
            break
    if prev is None:
        raise ValueError(f"Нет предыдущего тега для '{target}'")
    return prev
