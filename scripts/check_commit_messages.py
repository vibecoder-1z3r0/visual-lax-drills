#!/usr/bin/env python3
"""Fail if any commit message contains a Claude session link.

Usage: check_commit_messages.py [REV_RANGE]   (default: all of HEAD's history)

AGENTS.md forbids session links in commits. This is the CI side of that rule: it looks for a
claude.ai link whose path mentions a session, and for a `Claude-Session:` trailer.
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
    """Return (sha, matched text) for every message that contains a session link."""
    found = []
    for sha, body in messages:
        match = PATTERN.search(body)
        if match:
            found.append((sha, match.group(0)))
    return found


def main() -> int:
    rev_range = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    try:
        messages = list(commit_messages(rev_range))
    except subprocess.CalledProcessError:
        # A force-push can leave the old range unknown; fall back to the whole history.
        print(f"check_commit_messages: range '{rev_range}' not found, checking all of HEAD")
        messages = list(commit_messages("HEAD"))
    bad = find_violations(messages)
    for sha, text in bad:
        print(f"check_commit_messages: {sha[:10]} contains a Claude session link ({text!r})")
    if bad:
        print("Remove it from the commit message (see AGENTS.md).", file=sys.stderr)
        return 1
    print(f"check_commit_messages: ok ({len(messages)} commits checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
