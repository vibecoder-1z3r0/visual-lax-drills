from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "screenshots.py"
spec = importlib.util.spec_from_file_location("screenshots", SCRIPT)
shots = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shots)


def test_readme_screenshots_match_the_current_source():
    """Fails when src/ changed but the screenshots in docs/screenshots/ were not remade.
    Fix: `make screenshots`, then commit docs/screenshots/."""
    ok, why = shots.is_current()
    assert ok, (
        f"screenshots are out of date ({why}); run `make screenshots` and commit docs/screenshots/"
    )


def test_a_source_change_is_noticed(tmp_path, monkeypatch):
    before = shots.source_hash()
    extra = shots.ROOT / "src" / "_hash_probe.txt"
    extra.write_text("x")
    try:
        assert shots.source_hash() != before
    finally:
        extra.unlink()
    assert shots.source_hash() == before
