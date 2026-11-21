#!/usr/bin/env python3
"""Combine src/ into a single dist/index.html.

Inlines the CSS, the JS modules and the icons (as an SVG sprite). Icons come from icons-custom/
when present, else src/icons/. A missing or malformed icon fails the build. Prints a table of
which file is used for every icon.
"""

from __future__ import annotations

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
CUSTOM = ROOT / "icons-custom"
DIST = ROOT / "dist"
VIEW_BOX = "-32 -32 64 64"
SVG_NS = "http://www.w3.org/2000/svg"

# Dependency order. Modules share one flat scope after bundling, so top-level names must be unique.
JS_ORDER = ["constants", "engine", "keepaway_data", "drills", "render", "ui", "main"]

# Every icon the page needs. Add a name here and a file in src/icons/ to add a new one.
ICONS = ["player", "goalie", "coach", "net", "ball", "ballbag", "cone"]

FORBIDDEN_TAGS = {"script", "foreignObject", "iframe", "object", "embed", "image"}


class BuildError(Exception):
    pass


def local(tag: str) -> str:
    return tag.split("}", 1)[-1]


def validate_svg(path: Path) -> ET.Element:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise BuildError(f"{path}: not well-formed XML ({exc})") from exc
    if local(root.tag) != "svg":
        raise BuildError(f"{path}: root element must be <svg>")
    vb = " ".join(root.get("viewBox", "").split())
    if vb != VIEW_BOX:
        raise BuildError(f"{path}: viewBox must be '{VIEW_BOX}', found '{vb}'")
    for el in root.iter():
        if local(el.tag) in FORBIDDEN_TAGS:
            raise BuildError(f"{path}: <{local(el.tag)}> is not allowed")
        for name, value in el.attrib.items():
            n = local(name)
            if n.lower().startswith("on"):
                raise BuildError(f"{path}: event handler attribute '{n}' is not allowed")
            if n == "href" and not value.startswith("#"):
                raise BuildError(f"{path}: external reference '{value}' is not allowed")
            if "url(" in value and not re.fullmatch(r".*url\(#[\w-]+\).*", value):
                raise BuildError(f"{path}: external url() reference in '{value}'")
    return root


def inner_xml(root: ET.Element) -> str:
    ET.register_namespace("", SVG_NS)
    parts = []
    if root.text and root.text.strip():
        parts.append(root.text)
    for child in root:
        parts.append(ET.tostring(child, encoding="unicode"))
    xml = "".join(parts)
    return xml.replace(f' xmlns="{SVG_NS}"', "").replace("ns0:", "")


def find_icon(name: str) -> tuple[Path, str]:
    custom = CUSTOM / f"{name}.svg"
    if custom.is_file():
        return custom, "custom"
    default = SRC / "icons" / f"{name}.svg"
    if default.is_file():
        return default, "default"
    raise BuildError(f"missing icon '{name}': expected {default.relative_to(ROOT)}")


def build_sprites() -> str:
    symbols = []
    print(f"{'icon':<10} {'source':<8} file")
    for name in ICONS:
        path, origin = find_icon(name)
        root = validate_svg(path)
        symbols.append(
            f'<symbol id="icon-{name}" viewBox="{VIEW_BOX}" overflow="visible">'
            f"{inner_xml(root)}</symbol>"
        )
        print(f"{name:<10} {origin:<8} {path.relative_to(ROOT)}")
    return "\n".join(symbols)


def bundle_js() -> str:
    seen: dict[str, str] = {}
    out = []
    decl = re.compile(
        r"^(?:export\s+)?(?:async\s+)?(?:function\*?|const|let|class)\s+([A-Za-z_$][\w$]*)", re.M
    )
    for name in JS_ORDER:
        path = SRC / "js" / f"{name}.js"
        if not path.is_file():
            raise BuildError(f"missing module {path.relative_to(ROOT)}")
        code = path.read_text(encoding="utf-8")
        for ident in decl.findall(code):
            if ident in seen:
                raise BuildError(f"top-level name '{ident}' declared in {seen[ident]} and {name}")
            seen[ident] = name
        code = re.sub(r"^import\b[^;]*;[ \t]*\n?", "", code, flags=re.M)
        code = re.sub(
            r"^export\s+(?=(?:async\s+)?(?:function|const|let|class)\b)", "", code, flags=re.M
        )
        if re.search(r"^export\b", code, flags=re.M):
            raise BuildError(f"{name}.js: unsupported export form")
        out.append(f"// ---- {name}.js ----\n{code.strip()}\n")
    return "\n".join(out)


def git_output(*args: str, default: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return default


def version_string() -> str:
    sha = git_output("rev-parse", "--short", "HEAD", default="unknown")
    tag = git_output("describe", "--tags", "--abbrev=0", default="dev")
    return f"{tag} ({sha})"


def main() -> int:
    try:
        sprites = build_sprites()
        js = bundle_js()
        css = (SRC / "style.css").read_text(encoding="utf-8")
        html = (SRC / "index.html").read_text(encoding="utf-8")
        for marker in ("/*@CSS@*/", "/*@JS@*/", "<!--@SPRITES@-->"):
            if marker not in html:
                raise BuildError(f"index.html is missing {marker}")
        if "</script" in js.lower():
            raise BuildError("JS must not contain a closing script tag")
        html = (
            html.replace("/*@CSS@*/", css)
            .replace("<!--@SPRITES@-->", sprites)
            .replace("@VERSION@", version_string())
            .replace("/*@JS@*/", js)
        )
        DIST.mkdir(exist_ok=True)
        (DIST / "index.html").write_text(html, encoding="utf-8")
        print(f"\nwrote dist/index.html ({len(html) / 1024:.1f} KiB)")
        return 0
    except BuildError as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
