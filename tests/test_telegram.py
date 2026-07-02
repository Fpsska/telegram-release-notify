from core.telegram import build_message


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
