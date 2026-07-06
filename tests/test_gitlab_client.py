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


def test_previous_tag_raises_when_target_bad_format():
    tags = ["26.1.0-rc1", "26.1.0-rc2"]
    with pytest.raises(ValueError):
        previous_tag(tags, "not-a-tag")
