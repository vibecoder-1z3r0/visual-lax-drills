#!/usr/bin/env python3
"""Fail if a commit message or pull request text contains a Claude session link.

Usage:
    check_no_session_links.py [REV_RANGE]   check commit messages (default: all of HEAD's history)
    check_no_session_links.py --stdin       check the text on standard input (a PR title and body)

AGENTS.md forbids session links in commits and PRs. This is the CI side of that rule: it looks for
a claude.ai link whose path mentions a session, and for a `Claude-Session:` trailer.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable, Iterator

PATTERN = re.compile(r"claude\.ai/\S*session|^Claude-Session:", re.IGNORECASE | re.MULTILINE)


def commit_messages(rev_range: str) -> Iterator[tuple[str, str]]:
    out = subprocess.run(
        ["git", "log", "--format=%H%x00%B%x01", rev_range],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    for chunk in out.split("\x01"):
        sha, _, body = chunk.strip("\n").partition("\x00")
        if sha.strip():
            yield sha.strip(), body


def find_violations(messages: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """Return (label, matched text) for every message that contains a session link."""
    found = []
    for label, body in messages:
        match = PATTERN.search(body)
        if match:
            found.append((label, match.group(0)))
    return found


def check_commits(rev_range: str) -> int:
    try:
        messages = list(commit_messages(rev_range))
    except subprocess.CalledProcessError:
        # A force-push can leave the old range unknown; fall back to the whole history.
        print(f"check_no_session_links: range '{rev_range}' not found, checking all of HEAD")
        messages = list(commit_messages("HEAD"))
    bad = find_violations(messages)
    for sha, text in bad:
        print(f"check_no_session_links: commit {sha[:10]} contains a session link ({text!r})")
    if bad:
        print("Remove it from the commit message (see AGENTS.md).", file=sys.stderr)
        return 1
    print(f"check_no_session_links: ok ({len(messages)} commits checked)")
    return 0


def check_text(text: str) -> int:
    bad = find_violations([("pull request", text)])
    for _, matched in bad:
        print(f"check_no_session_links: the pull request contains a session link ({matched!r})")
    if bad:
        print("Remove it from the PR title or description (see AGENTS.md).", file=sys.stderr)
        return 1
    print("check_no_session_links: ok (pull request text checked)")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args == ["--stdin"]:
        return check_text(sys.stdin.read())
    return check_commits(args[0] if args else "HEAD")


if __name__ == "__main__":
    sys.exit(main())
