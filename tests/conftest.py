from __future__ import annotations

import functools
import http.server
import os
import threading
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
ARTIFACTS = ROOT / "test-artifacts"


def _built_page() -> Path:
    page = DIST / "index.html"
    if not page.is_file():
        pytest.fail("dist/index.html is missing; run `make build` (or `make test`)")
    return page


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep the test output clean
        pass


@pytest.fixture(scope="session")
def site():
    """The built page served over HTTP by a throwaway local server, like GitHub Pages serves it.

    Most tests use this. Over file:// Chromium sometimes drops a localStorage write when the page is
    reloaded straight away (about 6 reloads in 100 under load), which made the theme test flaky.
    `file_site` below covers opening the page straight from disk.
    """
    _built_page()
    handler = functools.partial(_QuietHandler, directory=str(DIST))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="session")
def file_site() -> str:
    """The built page as a file:// URL, the way a person opens the single file from disk."""
    return _built_page().as_uri()


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
