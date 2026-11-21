from __future__ import annotations

ICONS = ["player", "goalie", "coach", "net", "ball", "ballbag", "cone"]


def drill_index(page, drill_id: str) -> int:
    """Where a drill is in the list, so tests do not break when the order changes."""
    return page.evaluate(f"LAX.DRILLS.findIndex((d) => d.id === '{drill_id}')")


def test_title_and_heading(page):
    assert page.title() == "Visual Lax Drills"
    assert "Visual Lax Drills" in page.locator("h1").inner_text()


def test_every_icon_is_in_the_sprite(page):
    for name in ICONS:
        assert page.locator(f"symbol#icon-{name}").count() == 1, name


def test_field_has_crease_and_net(page):
    # ground ball mania (the default drill) hides the goal, so look at one that shows it
    page.select_option("#drill", str(drill_index(page, "two-man-shoot")))
    assert page.locator("#field circle.crease").count() == 1
    assert page.locator("#field use[href='#icon-net']").count() == 1


def test_one_group_per_actor(page):
    expected = page.evaluate("LAX.DRILLS[0].actors.length")
    assert page.locator("#field g.actor").count() == expected


def test_drill_selector_switches_drills(page):
    index = drill_index(page, "cone-weave")
    page.select_option("#drill", str(index))
    assert page.locator("#title").inner_text() == "Cone weave and finish"
    expected = page.evaluate(f"LAX.DRILLS[{index}].actors.length")
    assert page.locator("#field g.actor").count() == expected
    assert page.locator("#field g.cone-orange").count() == 1


def test_every_theme_restyles_the_page(page):
    options = page.locator("#theme option").evaluate_all("els => els.map(e => e.value)")
    assert options == ["day", "night", "stadium", "stage", "bright", "navy", "gold", "field"]
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


def test_ground_ball_mania_hides_the_goal_and_crease(page):
    page.select_option("#drill", str(drill_index(page, "ground-ball-mania")))
    assert page.locator("#goal").evaluate("el => getComputedStyle(el).display") == "none"
    page.select_option("#drill", str(drill_index(page, "two-man-shoot")))
    assert page.locator("#goal").evaluate("el => getComputedStyle(el).display") != "none"


def test_ground_ball_mania_hides_the_midfield_label(page):
    def shown() -> str:
        return page.locator("#midfield-label").evaluate("el => getComputedStyle(el).display")

    page.select_option("#drill", str(drill_index(page, "ground-ball-mania")))
    assert shown() == "none"
    page.select_option("#drill", str(drill_index(page, "two-man-shoot")))
    assert shown() != "none"


def test_choosing_a_drill_zooms_to_its_view(page):
    for index in range(page.evaluate("LAX.DRILLS.length")):
        page.select_option("#drill", str(index))
        view = page.evaluate(f"LAX.DRILLS[{index}].view")
        expected = f"{view['x']} {view['y']} {view['w']} {view['h']}"
        assert page.locator("#field").get_attribute("viewBox") == expected


def test_ground_ball_mania_is_the_default_drill(page):
    assert page.evaluate("LAX.DRILLS[0].id") == "ground-ball-mania"
    assert page.locator("#title").inner_text() == "Ground ball mania"
    assert page.locator("#drill").input_value() == "0"
