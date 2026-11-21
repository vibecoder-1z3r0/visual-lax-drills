#!/usr/bin/env python3
"""Lint dist/index.html without Node: strict HTML5 parse, unique ids, and resolvable references."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import html5lib

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "dist" / "index.html"


def main() -> int:
    if not PAGE.is_file():
        print("dist/index.html is missing; run `make build`", file=sys.stderr)
        return 1
    text = PAGE.read_text(encoding="utf-8")
    problems: list[str] = []

    parser = html5lib.HTMLParser(strict=True)
    try:
        parser.parse(text)
    except html5lib.html5parser.ParseError as exc:
        problems.append(f"HTML parse error: {exc}")

    ids = re.findall(r'\bid="([^"]+)"', text)
    for name, count in Counter(ids).items():
        if count > 1:
            problems.append(f"duplicate id '{name}' ({count} times)")

    known = set(ids)
    for ref in re.findall(r'\bhref="#([\w-]+)"', text):
        if ref not in known:
            problems.append(f'href="#{ref}" points to a missing id')

    for ref in re.findall(r'\bfor="([\w-]+)"', text):
        if ref not in known:
            problems.append(f'label for="{ref}" points to a missing id')

    for problem in problems:
        print(f"lint_html: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"lint_html: ok ({len(ids)} ids)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
