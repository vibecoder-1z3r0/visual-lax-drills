from __future__ import annotations

import os
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
ARTIFACTS = ROOT / "test-artifacts"


@pytest.fixture(scope="session")
def site() -> str:
    """The built page as a file:// URL. It is one static file, so no server is needed."""
    page = DIST / "index.html"
    if not page.is_file():
        pytest.fail("dist/index.html is missing; run `make build` (or `make test`)")
    return page.as_uri()


@pytest.fixture(scope="session")
def browser():
    # PLAYWRIGHT_CHROMIUM_EXECUTABLE lets a machine with its own Chromium skip the download.
    exe = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or None
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=exe)
        yield b
        b.close()


@pytest.fixture
def context(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    yield ctx
    ctx.close()


@pytest.fixture
def page(context, site) -> Page:
    pg = context.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.goto(site)
    pg.wait_for_function("window.LAX !== undefined")
    yield pg
    assert pg.errors == [], pg.errors


def choose_drill(page: Page, drill_id: str) -> None:
    """Switch the page to a drill by id, so tests do not depend on the order of the list."""
    index = page.evaluate(f"LAX.DRILLS.findIndex((d) => d.id === '{drill_id}')")
    assert index >= 0, drill_id
    page.select_option("#drill", str(index))
