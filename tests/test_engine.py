from __future__ import annotations

import pytest

FIELD_W, FIELD_H = 60, 55


def test_track_interpolates_and_clamps(page):
    keys = "[{t:0,x:0,y:0},{t:2,x:10,y:20}]"
    assert page.evaluate(f"LAX.trackAt({keys}, 1)") == {"x": 5, "y": 10}
    assert page.evaluate(f"LAX.trackAt({keys}, -3)") == {"x": 0, "y": 0}
    assert page.evaluate(f"LAX.trackAt({keys}, 9)") == {"x": 10, "y": 20}


def test_every_drill_is_well_formed(page):
    drills = page.evaluate("LAX.DRILLS")
    assert drills
    ids = [d["id"] for d in drills]
    assert len(ids) == len(set(ids))
    for drill in drills:
        names = [a["id"] for a in drill["actors"]]
        assert len(names) == len(set(names)), drill["id"]
        assert "ball" in names, drill["id"]
        for actor in drill["actors"]:
            times = [key["t"] for key in actor["keys"]]
            assert times == sorted(times), (drill["id"], actor["id"])
            assert times[-1] <= drill["duration"], (drill["id"], actor["id"])
            for key in actor["keys"]:
                assert 0 <= key["x"] <= FIELD_W, (drill["id"], actor["id"], key)
                assert 0 <= key["y"] <= FIELD_H, (drill["id"], actor["id"], key)
        stamps = [c["t"] for c in drill["captions"]]
        assert stamps == sorted(stamps) and stamps[0] == 0, drill["id"]


def test_advance_respects_speed(page):
    page.evaluate("LAX.app.engine.advance(1000)")
    assert page.evaluate("LAX.app.engine.t") == pytest.approx(1.0)
    page.evaluate("LAX.app.engine.setSpeed(2)")
    page.evaluate("LAX.app.engine.advance(1000)")
    assert page.evaluate("LAX.app.engine.t") == pytest.approx(3.0)


def test_advance_stops_at_the_end(page):
    page.evaluate("LAX.app.engine.advance(100000)")
    state = page.evaluate(
        "({t: LAX.app.engine.t, d: LAX.app.engine.drill.duration, p: LAX.app.engine.playing})"
    )
    assert state == {"t": state["d"], "d": state["d"], "p": False}


def test_ball_travels_with_the_pass(page):
    # In the first drill A1 passes to A2, so at t=2 the ball is on A2 and the page shows it there.
    page.evaluate("LAX.app.engine.seek(2)")
    pos = page.evaluate("LAX.app.engine.positions()")
    assert pos["ball"] == pos["a2"] == {"x": 46, "y": 38}
    assert (
        page.locator("g[data-actor='ball']").get_attribute("transform")
        == "translate(46.000 38.000)"
    )


def test_scrubbing_moves_time_and_pauses(page):
    page.locator("#play").click()
    page.locator("#scrub").fill("300")
    state = page.evaluate("({t: LAX.app.engine.t, p: LAX.app.engine.playing})")
    assert state["t"] == pytest.approx(3.0)
    assert state["p"] is False
    assert page.locator("#time").inner_text() == "3.0 / 6.0 s"


def test_play_pause_and_reset_buttons(page):
    play = page.locator("#play")
    play.click()
    assert play.inner_text() == "Pause"
    page.wait_for_function("LAX.app.engine.t > 0.2", timeout=5000)
    play.click()
    assert play.inner_text() == "Play"
    page.evaluate("LAX.app.engine.seek(3)")
    page.locator("#reset").click()
    assert page.evaluate("LAX.app.engine.t") == 0


def test_captions_follow_time(page):
    first = page.locator("#caption").inner_text()
    page.evaluate("LAX.app.engine.seek(2.5)")
    assert page.locator("#caption").inner_text() == "A1 cuts hard toward the crease."
    assert first != page.locator("#caption").inner_text()
