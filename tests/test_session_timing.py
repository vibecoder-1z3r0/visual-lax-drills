from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "session_timing.py"
spec = importlib.util.spec_from_file_location("session_timing", SCRIPT)
timing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timing)

# Fake secrets are built from pieces so this file never holds a real-looking one.
AT = "@"
EMAIL = "someone" + AT + "example.com"
GITHUB_TOKEN = "gh" + "p_" + "a1B2c3D4" * 5
API_KEY = "sk" + "-" + "Zy9Xw8Vu7Ts6Rq5P" * 2
AWS_KEY = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
HEX = "0123456789abcdef" * 3
SESSION_LINK = "https://claude." + "ai/code/" + "session_" + "0123abcd4567"


# ---- redaction ----------------------------------------------------------------------------


def test_secret_shaped_strings_are_redacted():
    for secret in (GITHUB_TOKEN, API_KEY, AWS_KEY, HEX):
        out = timing.redact(f"please use {secret} for the call")
        assert secret not in out, secret
        assert "[" in out


def test_key_value_secrets_keep_the_name_but_not_the_value():
    out = timing.redact("set password=hunter22 and API_KEY: abc12345")
    assert "hunter22" not in out and "abc12345" not in out
    assert "password" in out.lower()


def test_emails_and_session_links_are_removed():
    out = timing.redact(f"mail {EMAIL} or open {SESSION_LINK} now")
    assert EMAIL not in out
    assert "0123abcd4567" not in out
    assert "claude" not in out


def test_ordinary_text_is_left_alone():
    text = "Move the coach right next to the cone at src/js/drills.js, 2.3 yards away"
    assert timing.redact(text) == text


def test_clean_prompt_drops_harness_reminders_and_paste_wrappers():
    text = (
        "<system-reminder>userEmail is " + EMAIL + "</system-reminder>\n"
        "Make   the ball\nsmaller <pasted_content id=x>please</pasted_content>"
    )
    assert timing.clean_prompt(text) == "Make the ball smaller please"


# ---- reading a transcript -----------------------------------------------------------------


def entry(kind, ts, text=None, human=False, usage=None):
    e = {"type": kind, "timestamp": ts, "message": {}}
    if human:
        e["origin"] = {"kind": "human"}
    if text is not None:
        e["message"]["content"] = text
    if usage:
        e["message"]["usage"] = usage
    return e


def write_transcript(path: Path, entries: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return path


def sample(tmp_path: Path) -> Path:
    use = {"input_tokens": 10, "output_tokens": 20, "cache_read_input_tokens": 100}
    return write_transcript(
        tmp_path / "s.jsonl",
        [
            entry("user", "2026-11-21T10:00:00Z", "First request", human=True),
            entry("assistant", "2026-11-21T10:00:30Z", usage=use),
            entry("user", "2026-11-21T10:01:00Z"),  # a tool result: agent activity
            entry("assistant", "2026-11-21T10:01:30Z", usage=use),
            entry("attachment", "2026-11-21T10:05:00Z"),  # bookkeeping: not agent activity
            entry("user", "2026-11-21T10:03:00Z", f"Second {GITHUB_TOKEN}", human=True),
            entry("assistant", "2026-11-21T10:03:20Z", usage=use),
        ],
    )


def test_turns_timing_and_tokens(tmp_path):
    turns = timing.load_turns(sample(tmp_path))
    assert len(turns) == 2
    s = timing.summarize(turns)
    assert s["agent_seconds"] == 90 + 20  # 10:00:00 to 10:01:30, then 10:03:00 to 10:03:20
    assert s["think_seconds"] == 90  # 10:01:30 to 10:03:00
    assert s["usage"]["output"] == 60 and s["usage"]["cache_read"] == 300


def test_prompts_are_redacted_before_truncation(tmp_path):
    padding = "x " * 30  # the token would straddle the 70 character cut
    path = write_transcript(
        tmp_path / "t.jsonl",
        [entry("user", "2026-11-21T10:00:00Z", padding + GITHUB_TOKEN, human=True)],
    )
    report = timing.build_report(timing.load_turns(path))
    assert GITHUB_TOKEN not in report
    assert GITHUB_TOKEN[:10] not in report


def test_the_report_has_a_row_per_turn_and_no_transcript_path(tmp_path):
    report = timing.build_report(timing.load_turns(sample(tmp_path)), "# Title\n")
    assert report.startswith("# Title")
    assert report.count("\n| ") == 3  # the header row and two turns
    assert ".claude" not in report and "jsonl" not in report


def test_a_long_prompt_is_cut_to_seventy_characters(tmp_path):
    path = write_transcript(
        tmp_path / "u.jsonl",
        [entry("user", "2026-11-21T10:00:00Z", "word " * 40, human=True)],
    )
    row = timing.build_report(timing.load_turns(path)).split("\n")[4]
    assert "…" in row
    assert len(row.split("|")[2].strip()) <= timing.PROMPT_CHARS + 1


def test_log_files_are_named_by_session_start(tmp_path):
    turns = timing.load_turns(sample(tmp_path))
    assert timing.default_log_name(turns) == "2026-11-21T1000Z.md"


def test_the_newest_transcript_is_used(tmp_path, monkeypatch):
    project = tmp_path / ".claude" / "projects" / timing.project_slug(Path.cwd())
    project.mkdir(parents=True)
    old = write_transcript(project / "old.jsonl", [])
    new = write_transcript(project / "new.jsonl", [])
    # Set the times explicitly: two files written back to back can get the same timestamp.
    os.utime(old, (1_000_000, 1_000_000))
    os.utime(new, (2_000_000, 2_000_000))
    assert timing.find_transcript(home=tmp_path) == new
    os.utime(old, (3_000_000, 3_000_000))
    assert timing.find_transcript(home=tmp_path) == old
