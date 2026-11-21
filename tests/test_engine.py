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


def test_catch_and_throw_ball_travels_between_the_players(page):
    drill = page.evaluate("LAX.DRILLS.find((d) => d.id === 'catch-and-throw')")
    ball = next(a for a in drill["actors"] if a["id"] == "ball")["keys"]
    track = page.evaluate
    at = lambda t: track(f"LAX.trackAt({ball}, {t})")  # noqa: E731
    start, mid, end = at(0), at(1.5), at(2.5)
    assert start["x"] < mid["x"] < end["x"]  # thrown from A1 to A2
    assert at(3.5)["x"] > at(4.5)["x"]  # and back again


def test_ground_ball_mania_rolls_stay_within_ten_yards_of_the_coach(page):
    """Wherever a ball comes to rest (where it was rolled to, or where a player holds it) it is
    within ten yards of the coach."""
    drill = page.evaluate("LAX.DRILLS.find((d) => d.id === 'ground-ball-mania')")
    coach = next(a for a in drill["actors"] if a["id"] == "coach")["keys"][0]
    balls = [a for a in drill["actors"] if a["kind"] == "ball"]
    assert len(balls) == 4
    for ball in balls:
        keys = ball["keys"]
        for key, after in zip(keys, keys[1:], strict=False):
            if (key["x"], key["y"]) == (after["x"], after["y"]):
                dist = ((key["x"] - coach["x"]) ** 2 + (key["y"] - coach["y"]) ** 2) ** 0.5
                assert dist <= 10, (ball["id"], key)


def test_ground_ball_mania_nobody_collides(page):
    """Kids keep clear of each other, the coach and the bag (the cone is only a marker, so players may run through it), and a rolled ball never
    passes close to a kid other than the one it is rolled for."""
    drill = page.evaluate("LAX.DRILLS.find((d) => d.id === 'ground-ball-mania')")
    actors = {a["id"]: a["keys"] for a in drill["actors"]}
    kids = [i for i in actors if i.startswith("p")]
    steps = int(drill["duration"] / 0.05)

    def at(ident, t):
        return page.evaluate("([keys, t]) => LAX.trackAt(keys, t)", [actors[ident], t])

    def dist(a, b):
        return ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5

    for n in range(steps + 1):
        t = n * 0.05
        pos = {i: at(i, t) for i in kids}
        for i, a in enumerate(kids):
            for b in kids[i + 1 :]:
                assert dist(pos[a], pos[b]) >= 3.2, (t, a, b)
            assert dist(pos[a], at("coach", t)) >= 3.2, (t, a, "coach")
            assert dist(pos[a], at("bag", t)) >= 2.7, (t, a, "bag")


def test_ground_ball_mania_rolled_balls_never_pass_close_to_a_player(page):
    """A ball that is moving must stay clear of every player. A carried ball sits about 1.8 yards
    from its player, so anything closer than 1.2 means a ball was rolled into someone."""
    drill = page.evaluate("LAX.DRILLS.find((d) => d.id === 'ground-ball-mania')")
    actors = {a["id"]: a["keys"] for a in drill["actors"]}
    kids = [i for i in actors if i.startswith("p")]
    balls = [i for i in actors if i.startswith("ball") and i != "bag"]
    steps = int(drill["duration"] / 0.05)

    def at(ident, t):
        return page.evaluate("([keys, t]) => LAX.trackAt(keys, t)", [actors[ident], t])

    def dist(a, b):
        return ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5

    for ball in balls:
        previous = at(ball, 0)
        for n in range(1, steps + 1):
            t = n * 0.05
            now = at(ball, t)
            if dist(now, previous) > 0.05:
                for kid in kids:
                    assert dist(now, at(kid, t)) >= 1.2, (t, ball, kid)
            previous = now


def test_ground_ball_mania_rolls_head_toward_the_goal(page):
    """Each ball is rolled toward the goal (within 30 degrees of straight at it) and about 9 to 10
    yards out, to the same spot each time: the last player has left before the next ball lands."""
    import math

    drill = page.evaluate("LAX.DRILLS.find((d) => d.id === 'ground-ball-mania')")
    goal = (30, 15)  # GOAL_X, GOAL_Y in constants.js
    coach = next(a for a in drill["actors"] if a["id"] == "coach")["keys"][0]
    names = ["ball", "ball2", "ball3", "ball4"]
    toward = math.atan2(goal[1] - coach["y"], goal[0] - coach["x"])
    lengths = []
    for name in names:
        keys = next(a for a in drill["actors"] if a["id"] == name)["keys"]
        # the first position after the ball is rolled out is the first key that is not the rest spot
        rest, spot = keys[0], keys[2]
        dx, dy = spot["x"] - rest["x"], spot["y"] - rest["y"]
        length = math.hypot(dx, dy)
        lengths.append(length)
        off = abs(math.degrees(math.atan2(dy, dx) - toward))
        assert off < 30 or off > 330, (name, off)
    assert max(lengths) - min(lengths) < 0.5, lengths
    assert all(9 <= n <= 10.5 for n in lengths), lengths
