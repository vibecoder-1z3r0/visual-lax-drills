from __future__ import annotations

import pytest
from conftest import choose_drill

FIELD_W, FIELD_H = 60, 55
# Every drill as it plays: a drill with versions counts once per version.
ALL_PLAYABLE = (
    "LAX.DRILLS.flatMap((d) => d.variants ? d.variants.map((_, i) => LAX.resolveDrill(d, i)) : [d])"
)


def test_track_interpolates_and_clamps(page):
    keys = "[{t:0,x:0,y:0},{t:2,x:10,y:20}]"
    assert page.evaluate(f"LAX.trackAt({keys}, 1)") == {"x": 5, "y": 10}
    assert page.evaluate(f"LAX.trackAt({keys}, -3)") == {"x": 0, "y": 0}
    assert page.evaluate(f"LAX.trackAt({keys}, 9)") == {"x": 10, "y": 20}


def test_every_drill_is_well_formed(page):
    drills = page.evaluate(ALL_PLAYABLE)
    assert drills
    ids = [d["id"] for d in page.evaluate("LAX.DRILLS")]
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
    # In two-man pass and shoot A1 passes to A2, so at t=2 the ball is in A2's stick and the page shows it there.
    choose_drill(page, "two-man-shoot")
    page.evaluate("LAX.app.engine.seek(2)")
    pos = page.evaluate("LAX.app.engine.positions()")
    size = page.evaluate("LAX.ICON_SIZE.player * LAX.app.engine.drill.iconScale")
    assert pos["ball"]["x"] == pytest.approx(pos["a2"]["x"] + 0.375 * size, abs=0.05)
    assert pos["ball"]["y"] == pytest.approx(pos["a2"]["y"] - 0.25 * size, abs=0.05)
    x, y = pos["ball"]["x"], pos["ball"]["y"]
    assert page.locator("g[data-actor='ball']").get_attribute("transform") == (
        f"translate({x:.3f} {y:.3f})"
    )


def test_scrubbing_moves_time_and_pauses(page):
    choose_drill(page, "two-man-shoot")
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
    choose_drill(page, "two-man-shoot")
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
                assert dist(pos[a], pos[b]) >= 1.8, (t, a, b)
            assert dist(pos[a], at("coach", t)) >= 2.0, (t, a, "coach")
            assert dist(pos[a], at("bag", t)) >= 1.6, (t, a, "bag")


def test_ground_ball_mania_rolled_balls_never_pass_close_to_a_player(page):
    """A ball that is moving must stay clear of every player. A carried ball sits about 0.8 yards
    from its player (in the stick's pocket); anything much closer than that means a ball was rolled
    through someone. (A player's own ball may dip a little inside as it leaves the stick.)"""
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
                    assert dist(now, at(kid, t)) >= 0.5, (t, ball, kid)
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
        spot = keys[2]
        dx, dy = spot["x"] - coach["x"], spot["y"] - coach["y"]
        length = math.hypot(dx, dy)
        lengths.append(length)
        off = abs(math.degrees(math.atan2(dy, dx) - toward))
        assert off < 30 or off > 330, (name, off)
    assert max(lengths) - min(lengths) < 0.5, lengths
    assert all(8.5 <= n <= 10 for n in lengths), lengths


def test_ground_ball_mania_players_keep_moving_and_stay_believable(page):
    """Once a player leaves the line they never stop (not at the scoop, not at the roll-in) until
    they are back in it, and nobody runs faster than about 8 yards a second."""
    result = page.evaluate(
        """() => {
      const drill = LAX.DRILLS.find((d) => d.id === 'ground-ball-mania');
      const kids = drill.actors.filter((a) => a.id.startsWith('p'));
      const slots = [38, 39.9, 41.8, 43.7].map((y) => ({ x: 30, y }));
      const inLine = (p) => slots.some((s) => Math.hypot(p.x - s.x, p.y - s.y) < 0.3);
      const dt = 0.05;
      let slowest = Infinity, fastest = 0, slowAt = null;
      for (const kid of kids) {
        for (let t = 0; t + dt <= drill.duration; t += dt) {
          const a = LAX.trackAt(kid.keys, t), b = LAX.trackAt(kid.keys, t + dt);
          if (inLine(a) && inLine(b)) continue;       // waiting or shuffling up in the line
          if (Math.hypot(a.x - 30, a.y - 38) < 0.3) continue;   // about to step out
          const v = Math.hypot(b.x - a.x, b.y - a.y) / dt;
          fastest = Math.max(fastest, v);
          if (v < slowest) { slowest = v; slowAt = [kid.id, +t.toFixed(2)]; }
        }
      }
      return { slowest, fastest, slowAt };
    }"""
    )
    assert result["fastest"] <= 8, result
    assert result["slowest"] > 0.5, result


def test_every_actor_stays_inside_its_drills_view(page):
    """A drill zooms in with `view`; nobody may leave the part of the field that is shown."""
    drills = page.evaluate(ALL_PLAYABLE)
    for drill in drills:
        view = drill.get("view")
        if not view:
            continue
        assert 1.0 <= view["w"] / view["h"] <= 1.2, (
            drill["id"],
            view,
        )  # close to the field's shape
        for actor in drill["actors"]:
            for key in actor["keys"]:
                assert view["x"] <= key["x"] <= view["x"] + view["w"], (
                    drill["id"],
                    actor["id"],
                    key,
                )
                assert view["y"] <= key["y"] <= view["y"] + view["h"], (
                    drill["id"],
                    actor["id"],
                    key,
                )


def test_a_held_ball_sits_in_the_sticks_pocket(page):
    """Whenever a ball is held by a player (a ball keyframe with a player right there), it is at the
    stick's pocket: about 0.375 of the icon width across and 0.25 up, scaled to the drill's icons."""
    result = page.evaluate(
        """() => {
      const ALL = __ALL__;
      const bad = [];
      for (const drill of ALL) {
        const size = LAX.ICON_SIZE.player * (drill.iconScale || 1);
        const players = drill.actors.filter((a) => a.kind === 'player');
        for (const ball of drill.actors.filter((a) => a.kind === 'ball')) {
          const near = (key, p) => {
            const at = LAX.trackAt(p.keys, key.t);
            return Math.hypot(key.x - at.x, key.y - at.y) <= 0.6 * size;  // a held ball is ~0.45 away
          };
          const atPocket = (key, p) => {
            const at = LAX.trackAt(p.keys, key.t);
            return Math.abs(key.x - at.x - 0.375 * size) <= 0.12 * size
              && Math.abs(key.y - at.y + 0.25 * size) <= 0.12 * size;
          };
          ball.keys.forEach((key, i) => {
            if (key.loose) return;                                   // lying on the ground
            if (players.some((p) => atPocket(key, p))) return;       // properly held (a defender
                                                                     // standing close is fine)
            for (const p of players) {
              // Held but misplaced: beside the same player at a neighbouring key too. A pass in
              // flight that is sampled beside a third player does not count.
              const next = ball.keys[i + 1], prev = ball.keys[i - 1];
              if (near(key, p) && ((next && near(next, p)) || (prev && near(prev, p)))) {
                const at = LAX.trackAt(p.keys, key.t);
                bad.push({ drill: drill.id, ball: ball.id, t: key.t, player: p.id, dx: key.x - at.x, dy: key.y - at.y });
              }
            }
          });
        }
      }
      return bad;
    }""".replace("__ALL__", ALL_PLAYABLE)
    )
    assert result == [], result
