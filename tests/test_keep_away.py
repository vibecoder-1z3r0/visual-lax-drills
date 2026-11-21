from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from conftest import choose_drill

ROOT = Path(__file__).resolve().parent.parent

# The playing area: 30 yards from the west sideline, 10 north to 40 south of the goal line.
BOX = {"x0": 15, "x1": 45, "y0": 5, "y1": 55}
SIDELINE = 15  # the lines wait just outside it
VERSIONS = (
    "keep-away",
    "blue-wins-ground-ball",
    "blue-takes-it-away",
    "loose-at-the-count",
)


def keep_away(page, index=0, take=0):
    return page.evaluate(
        f"LAX.resolveDrill(LAX.DRILLS.find((d) => d.id === 'keep-away'), {index}, {take})"
    )


def every_take(page):
    """(version index, seed index, drill) for every version of every seed."""
    counts = page.evaluate(
        "LAX.DRILLS.find((d) => d.id === 'keep-away').variants.map((v) => v.takes.length)"
    )
    return [(i, k, keep_away(page, i, k)) for i, n in enumerate(counts) for k in range(n)]


def track(page, actor, t):
    return page.evaluate("([keys, t]) => LAX.trackAt(keys, t)", [actor["keys"], t])


def test_the_generated_data_is_what_the_generator_makes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "keepaway_choreography.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_there_are_four_versions_and_the_standard_one_is_first(page):
    drill = page.evaluate("LAX.DRILLS.find((d) => d.id === 'keep-away')")
    ids = [v["id"] for v in drill["variants"]]
    assert ids[0] == "standard" or ids[0].startswith("standard")
    assert len(ids) == 4


def test_the_version_picker_is_only_shown_for_drills_with_versions(page):
    choose_drill(page, "keep-away")
    assert page.locator("#variant-pick").is_visible()
    assert page.locator("#variant option").count() == 4
    choose_drill(page, "catch-and-throw")
    assert not page.locator("#variant-pick").is_visible()


def test_choosing_a_version_changes_the_drill_and_resets_the_clock(page):
    choose_drill(page, "keep-away")
    first = page.evaluate("LAX.app.engine.drill.variantId")
    page.evaluate("LAX.app.engine.seek(10)")
    page.select_option("#variant", "1")
    assert page.evaluate("LAX.app.engine.drill.variantId") != first
    assert page.evaluate("LAX.app.engine.t") == 0


def test_the_setup_is_five_a_side_with_the_goal_and_no_goalie(page):
    choose_drill(page, "keep-away")
    drill = keep_away(page)
    kinds = [a["kind"] for a in drill["actors"]]
    assert kinds.count("goalie") == 0
    assert kinds.count("coach") == 2
    assert kinds.count("cone") == 1
    ids = [a["id"] for a in drill["actors"]]
    assert [i for i in ids if i.startswith("n")] == [f"n{i}" for i in range(1, 6)]
    assert [i for i in ids if i.startswith("s")] == [f"s{i}" for i in range(1, 6)]
    assert drill.get("goal") is not False
    cone = next(a for a in drill["actors"] if a["kind"] == "cone")["keys"][0]
    assert cone["y"] == 35  # the 20-yard line, 20 yards from the goal
    coach = next(a for a in drill["actors"] if a["id"] == "coach")["keys"][0]
    assert coach["x"] < cone["x"] and abs(coach["y"] - cone["y"]) < 0.5  # right behind the cone
    for name, sign in (("n", -1), ("s", 1)):  # blue north, red south
        for i in range(1, 6):
            key = next(a for a in drill["actors"] if a["id"] == f"{name}{i}")["keys"][0]
            assert key["y"] * sign > cone["y"] * sign


def test_two_south_players_and_one_north_player_go_out_first(page):
    choose_drill(page, "keep-away")
    drill = keep_away(page)
    moved = []
    for actor in drill["actors"]:
        if actor["id"][0] in "ns" and actor["id"][1:].isdigit():
            at = track(page, actor, 3.0)
            if at["x"] > 18:  # off the sideline; the others only step up the line
                moved.append(actor["id"])
    assert sorted(moved) == ["n1", "s1", "s2"]


def test_every_version_stays_in_bounds_and_nobody_runs_faster_than_a_sprint(page):
    for index, take, drill in every_take(page):
        players = [a for a in drill["actors"] if a["kind"] == "player"]
        assert len(players) == 10
        for actor in players:
            keys = actor["keys"]
            # Waiting in line is out of bounds (west of the sideline); once playing, in bounds.
            assert keys[0]["x"] < SIDELINE, ((index, take), actor["id"])
            playing = [k for k in keys if k["x"] >= SIDELINE]
            # (the last player in a line never gets released: 5 against 4 is the most)
            if playing:
                assert all(k["x"] >= SIDELINE for k in keys[keys.index(playing[0]) :]), (
                    index,
                    actor["id"],
                )
            for key in keys:
                assert BOX["x0"] - 2 <= key["x"] <= BOX["x1"] + 1e-6, (
                    (index, take),
                    actor["id"],
                    key,
                )
                assert BOX["y0"] <= key["y"] <= BOX["y1"] + 1e-6, ((index, take), actor["id"], key)
            for a, b in zip(keys, keys[1:], strict=False):
                speed = ((b["x"] - a["x"]) ** 2 + (b["y"] - a["y"]) ** 2) ** 0.5 / (b["t"] - a["t"])
                assert speed <= 8.4, ((index, take), actor["id"], a, b, speed)


def test_players_never_stack_on_top_of_each_other(page):
    for index, take, drill in every_take(page):
        players = [a for a in drill["actors"] if a["kind"] == "player"]
        result = page.evaluate(
            """([players, duration]) => {
          let worst = 99, where = null;
          for (let t = 0; t <= duration; t += 0.25) {
            const pts = players.map((p) => ({ id: p.id, ...LAX.trackAt(p.keys, t) }));
            for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) {
              const d = Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y);
              if (d < worst) { worst = d; where = [t, pts[i].id, pts[j].id]; }
            }
          }
          return { worst, where };
        }""",
            [players, drill["duration"]],
        )
        # An on-ball defender stands close to the carrier, but never inside them.
        assert result["worst"] >= 0.8, (index, take, result)


def test_every_version_has_a_start_a_release_a_countdown_and_an_end(page):
    for index, take, drill in every_take(page):
        text = " ".join(c["text"].lower() for c in drill["captions"])
        assert "release" in text or "whistle" in text, (index, take)
        assert "5" in text and "1" in text, (index, take)  # the countdown
        assert drill["captions"][0]["t"] == 0
        assert drill["duration"] >= 40


def test_the_coach_says_release_with_a_speech_bubble(page):
    choose_drill(page, "keep-away")
    drill = keep_away(page)
    says = [(s["t"], s["text"]) for s in drill["speech"]]
    releases = [t for t, text in says if text == "Release!"]
    assert len(releases) == 3
    assert [text for _, text in says if text.isdigit()] == ["5", "4", "3", "2", "1"]
    assert says[-1][1] == "Reset!"
    page.evaluate(f"LAX.app.engine.seek({releases[0] + 0.3})")
    bubble = page.locator('.speech[data-speaker="coach"]')
    assert bubble.get_attribute("visibility") == "visible"
    assert "Release!" in bubble.text_content()
    page.evaluate("LAX.app.engine.seek(3.5)")  # nobody is talking
    assert bubble.get_attribute("visibility") == "hidden"


def test_a_speech_bubble_stays_inside_the_view(page):
    choose_drill(page, "keep-away")
    drill = keep_away(page)
    view = drill["view"]
    for item in drill["speech"]:
        page.evaluate(f"LAX.app.engine.seek({item['t'] + 0.2})")
        box = page.locator('.speech[data-speaker="coach"] .speech-box').bounding_box()
        svg = page.locator("#field").bounding_box()
        assert box["x"] >= svg["x"] - 1 and box["x"] + box["width"] <= svg["x"] + svg["width"] + 1
        assert box["y"] >= svg["y"] - 1, (item, view)


def test_each_version_has_several_seeds_and_the_default_comes_first(page):
    drill = page.evaluate("LAX.DRILLS.find((d) => d.id === 'keep-away')")
    for variant in drill["variants"]:
        seeds = [take["seed"] for take in variant["takes"]]
        assert len(seeds) >= 4 and len(set(seeds)) == len(seeds), variant["id"]
    # different seeds really play out differently
    a, b = keep_away(page, 0, 0), keep_away(page, 0, 1)
    ball_a = next(x for x in a["actors"] if x["id"] == "ball")["keys"]
    ball_b = next(x for x in b["actors"] if x["id"] == "ball")["keys"]
    assert ball_a != ball_b


def test_the_seed_menu_plays_another_take_and_resets_on_a_new_version(page):
    choose_drill(page, "keep-away")
    assert page.locator("#take-pick").is_visible()
    assert page.locator("#take option").count() >= 4
    assert "default" in page.locator("#take option").first.inner_text()
    first_seed = page.evaluate("LAX.app.engine.drill.seed")
    page.select_option("#take", "2")
    assert page.evaluate("LAX.app.engine.drill.seed") != first_seed
    assert page.evaluate("LAX.app.engine.t") == 0
    page.select_option("#variant", "1")  # a new version starts on its default seed
    assert page.locator("#take").input_value() == "0"
    choose_drill(page, "catch-and-throw")
    assert not page.locator("#take-pick").is_visible()


def test_the_coach_in_the_field_drifts_out_of_bounds(page):
    drill = keep_away(page)
    coach = next(a for a in drill["actors"] if a["id"] == "coach2")["keys"]
    assert coach[0]["x"] < 45  # starts in the field
    assert coach[-1]["x"] > 45  # and ends up out of bounds, out of the players' way
