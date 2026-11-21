from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_no_session_links.py"
spec = importlib.util.spec_from_file_location("check_no_session_links", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

# Built from pieces so this file never contains a real session link itself.
LINK = "https://claude." + "ai/code/" + "session_" + "0123abcd"


def test_clean_messages_pass():
    messages = [("a1", "Add the field\n\nCo-Authored-By: Someone <x@example.com>"), ("b2", "Fix")]
    assert check.find_violations(messages) == []


def test_session_link_in_body_is_caught():
    found = check.find_violations([("a1", f"Add the field\n\nSee {LINK}")])
    assert [sha for sha, _ in found] == ["a1"]


def test_session_trailer_is_caught():
    found = check.find_violations([("a1", "Add the field\n\nClaude-Session: whatever")])
    assert [sha for sha, _ in found] == ["a1"]


def test_only_the_bad_commit_is_reported():
    messages = [("a1", "fine"), ("b2", f"bad {LINK}"), ("c3", "also fine")]
    assert [sha for sha, _ in check.find_violations(messages)] == ["b2"]


def test_ordinary_claude_mentions_are_allowed():
    assert (
        check.find_violations([("a1", "Docs for the Claude GitHub App at claude.ai/settings")])
        == []
    )


def test_pull_request_text_is_checked(capsys):
    assert check.check_text("Adds the field\n\nSummary here.") == 0
    assert check.check_text(f"Adds the field\n\n{LINK}") == 1
    assert "pull request contains a session link" in capsys.readouterr().out


def test_pull_request_link_in_title_is_caught():
    assert check.check_text(f"Fix {LINK}\n\nbody") == 1
