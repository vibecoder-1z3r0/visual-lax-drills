"""Makes the screenshots shown in README.md, and checks they are not out of date.

    python scripts/screenshots.py           # rebuild docs/screenshots/*.png (needs dist/index.html)
    python scripts/screenshots.py --check   # exit 1 if src/ changed since they were made

The check compares a hash of everything that can change how the page looks (src/ and the build
script) with the one saved next to the images. It does not compare pixels, so it does not depend on
fonts or the machine. `make screenshots` rebuilds the page first, then runs this. A test runs the
check, so CI fails until the screenshots are regenerated and committed.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "index.html"
OUT = ROOT / "docs" / "screenshots"
HASH_FILE = OUT / "SOURCE_HASH"

# drill id (also the file name), time in seconds (a moment with something happening)
DRILL_SHOTS = [
    ("ground-ball-mania", 6.4),
    ("two-man-shoot", 2.6),
    ("cone-weave", 3.2),
    ("catch-and-throw", 1.6),
]
THEMES = ["day", "night", "stadium", "stage", "bright", "navy", "gold", "field"]
THEME_SHOT_DRILL = ("ground-ball-mania", 6.4)
DESKTOP = {"width": 1100, "height": 700}
PHONE = {"width": 390, "height": 760}


def is_generated(path: Path) -> bool:
    """Files that can appear under src/ on one machine and not another (installs, caches)."""
    return any(part == "__pycache__" or part.endswith(".egg-info") for part in path.parts)


def source_hash() -> str:
    """Hash of every file that can change what the page looks like."""
    files = sorted(p for p in (ROOT / "src").rglob("*") if p.is_file() and not is_generated(p))
    files.append(ROOT / "scripts" / "build.py")
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def expected_files() -> list[Path]:
    names = [f"{name}.png" for name, _ in DRILL_SHOTS] + ["themes.png", "phone.png"]
    return [OUT / n for n in names]


def is_current() -> tuple[bool, str]:
    """(True, "") when the screenshots match src/, else (False, why)."""
    missing = [p.name for p in expected_files() if not p.is_file()]
    if missing:
        return False, f"missing: {', '.join(missing)}"
    if not HASH_FILE.is_file():
        return False, "docs/screenshots/SOURCE_HASH is missing"
    if HASH_FILE.read_text().strip() != source_hash():
        return False, "src/ has changed since the screenshots were made"
    return True, ""


def prepare(page, drill_id: str, t: float, theme: str = "day") -> None:
    page.select_option("#theme", theme)
    index = page.evaluate(f"LAX.DRILLS.findIndex((d) => d.id === '{drill_id}')")
    page.select_option("#drill", str(index))
    page.evaluate(f"LAX.app.engine.seek({t})")
    # The version label shows the commit, which would make every screenshot differ.
    page.add_style_tag(content=".ver { visibility: hidden; }")
    page.wait_for_timeout(100)


def make() -> None:
    from PIL import Image, ImageDraw
    from playwright.sync_api import sync_playwright

    if not DIST.is_file():
        sys.exit("dist/index.html is missing; run `make build` first")
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport=DESKTOP)
        page = context.new_page()
        page.goto(DIST.as_uri())
        page.wait_for_function("window.LAX !== undefined")
        for name, t in DRILL_SHOTS:
            prepare(page, name, t)
            page.screenshot(path=str(OUT / f"{name}.png"))

        # All six themes on the same frame, in one picture.
        tiles = []
        for theme in THEMES:
            prepare(page, *THEME_SHOT_DRILL, theme=theme)
            path = OUT / f"_theme_{theme}.png"
            page.locator("#stage").screenshot(path=str(path))
            tiles.append((theme, Image.open(path).convert("RGB")))
        w, h = tiles[0][1].size
        scale = 0.32
        tw, th = int(w * scale), int(h * scale)
        cols, rows, pad, label_h = 4, 2, 12, 22
        sheet = Image.new(
            "RGB", (cols * tw + (cols + 1) * pad, rows * (th + label_h) + (rows + 1) * pad), "white"
        )
        draw = ImageDraw.Draw(sheet)
        for i, (theme, img) in enumerate(tiles):
            x = pad + (i % cols) * (tw + pad)
            y = pad + (i // cols) * (th + label_h + pad)
            draw.text((x, y + 4), theme, fill=(40, 40, 40))
            sheet.paste(img.resize((tw, th), Image.LANCZOS), (x, y + label_h))
            (OUT / f"_theme_{theme}.png").unlink()
        sheet.save(OUT / "themes.png", optimize=True)

        # The same drill at phone width.
        phone = browser.new_context(viewport=PHONE, device_scale_factor=2).new_page()
        phone.goto(DIST.as_uri())
        phone.wait_for_function("window.LAX !== undefined")
        prepare(phone, "ground-ball-mania", 6.4)
        phone.screenshot(path=str(OUT / "phone.png"), full_page=True)
        browser.close()
    HASH_FILE.write_text(source_hash() + "\n")
    print("wrote", ", ".join(p.name for p in expected_files()))


def main() -> int:
    if "--check" in sys.argv[1:]:
        ok, why = is_current()
        if not ok:
            print(f"screenshots are out of date ({why});")
            print("run `make screenshots` and commit docs/screenshots/")
            return 1
        print("screenshots are up to date")
        return 0
    make()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
