from __future__ import annotations

ICONS = ["player", "goalie", "coach", "net", "ball", "ballbag", "cone"]


def test_title_and_heading(page):
    assert page.title() == "Visual Lax Drills"
    assert "Visual Lax Drills" in page.locator("h1").inner_text()


def test_every_icon_is_in_the_sprite(page):
    for name in ICONS:
        assert page.locator(f"symbol#icon-{name}").count() == 1, name


def test_field_has_crease_and_net(page):
    assert page.locator("#field circle.crease").count() == 1
    assert page.locator("#field use[href='#icon-net']").count() == 1


def test_one_group_per_actor(page):
    expected = page.evaluate("LAX.DRILLS[0].actors.length")
    assert page.locator("#field g.actor").count() == expected


def test_drill_selector_switches_drills(page):
    page.select_option("#drill", "1")
    assert page.locator("#title").inner_text() == "Cone weave and finish"
    expected = page.evaluate("LAX.DRILLS[1].actors.length")
    assert page.locator("#field g.actor").count() == expected
    assert page.locator("#field g.cone-orange").count() == 1


def test_every_theme_restyles_the_page(page):
    options = page.locator("#theme option").evaluate_all("els => els.map(e => e.value)")
    assert options == ["day", "night", "stadium", "field"]
    seen = {page.evaluate("getComputedStyle(document.body).backgroundColor")}
    for theme in options[1:]:
        page.select_option("#theme", theme)
        assert page.evaluate("document.documentElement.dataset.theme") == theme
        seen.add(page.evaluate("getComputedStyle(document.body).backgroundColor"))
        grass = page.evaluate("getComputedStyle(document.querySelector('.field-grass-a')).fill")
        assert grass.startswith("rgb"), theme
    assert len(seen) == len(options)


def test_theme_is_remembered_after_a_reload(page):
    page.select_option("#theme", "field")
    page.reload()
    page.wait_for_function("window.LAX !== undefined")
    assert page.evaluate("document.documentElement.dataset.theme") == "field"
    assert page.locator("#theme").input_value() == "field"
