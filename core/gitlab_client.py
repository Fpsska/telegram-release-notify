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
