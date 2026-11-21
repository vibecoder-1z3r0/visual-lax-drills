from __future__ import annotations

from conftest import ARTIFACTS
from PIL import Image, ImageChops


def shot(page, name: str) -> Image.Image:
    ARTIFACTS.mkdir(exist_ok=True)
    path = ARTIFACTS / f"{name}.png"
    page.locator("#stage").screenshot(path=str(path))
    return Image.open(path).convert("RGB")


def test_frames_are_captured_and_change_over_time(page):
    """Saves frames to test-artifacts/ for a human to look at, and checks the drill really moves."""
    frames = {}
    for t in (0, 2, 5):
        page.evaluate(f"LAX.app.engine.seek({t})")
        frames[t] = shot(page, f"two-man-shoot-t{t}")
    assert ImageChops.difference(frames[0], frames[2]).getbbox() is not None
    assert ImageChops.difference(frames[2], frames[5]).getbbox() is not None


def test_night_theme_frame(page):
    page.select_option("#theme", "night")
    day_like = shot(page, "night-t0")
    assert day_like.getpixel((5, 5)) != (244, 241, 234)
