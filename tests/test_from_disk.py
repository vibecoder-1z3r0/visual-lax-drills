from __future__ import annotations


def test_the_single_file_opens_from_disk_and_plays(context, file_site):
    """The shipped page is one file that must work when opened straight from disk (file://)."""
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(file_site)
    page.wait_for_function("window.LAX !== undefined")
    assert page.locator("h1").inner_text().startswith("Visual Lax Drills")
    assert page.locator("#title").inner_text() == "Ground ball mania"
    page.locator("#play").click()
    page.evaluate("LAX.app.engine.advance(2000)")
    assert page.evaluate("LAX.app.engine.t") > 1.5
    assert page.locator("#field g.actor").count() > 5
    assert errors == []


def test_another_seed_loads_from_disk_too(context, file_site):
    """Take files are script tags, so picking a seed works over file:// where fetch would not."""
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(file_site)
    page.wait_for_function("window.LAX !== undefined")
    index = page.evaluate("LAX.DRILLS.findIndex((d) => d.id === 'keep-away')")
    page.select_option("#drill", str(index))
    first = page.evaluate("LAX.app.engine.drill.seed")
    page.select_option("#take", "2")
    page.wait_for_function("(first) => LAX.app.engine.drill.seed !== first", arg=first)
    assert not page.locator("#take-error").is_visible()
    assert errors == []
