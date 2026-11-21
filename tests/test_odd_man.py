from __future__ import annotations

from conftest import choose_drill, load_every_take

GOAL = (30, 15)
VERSIONS = ("standard", "goal-reset", "goal-new-ball", "man-down-offense", "with-goalie")


def drill_data(page, version=0, take=0):
    return page.evaluate(
        f"LAX.resolveDrill(LAX.DRILLS.find((d) => d.id === 'odd-man'), {version}, {take})"
    )


def every_take(page):
    load_every_take(page)
    counts = page.evaluate(
        "LAX.DRILLS.find((d) => d.id === 'odd-man').variants.map((v) => v.seeds.length)"
    )
    return [(i, k, drill_data(page, i, k)) for i, n in enumerate(counts) for k in range(n)]


def keys_of(drill, actor_id):
    return next(a for a in drill["actors"] if a["id"] == actor_id)["keys"]


def text_of(drill):
    return " ".join(c["text"] for c in drill["captions"])


def test_it_is_listed_after_keep_away_with_five_versions(page):
    ids = page.evaluate("LAX.DRILLS.map((d) => d.id)")
    assert ids[:3] == ["ground-ball-mania", "keep-away", "odd-man"]
    drill = page.evaluate("LAX.DRILLS.find((d) => d.id === 'odd-man')")
    assert [v["id"] for v in drill["variants"]] == list(VERSIONS)
    assert drill["title"] == "Syracuse (odd man, offense/defense)"


def test_the_generated_data_is_current():
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parent.parent / "scripts" / "choreography.py"
    result = subprocess.run(
        [sys.executable, str(script), "--check"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_goalie_is_optional_and_the_goal_always_shows(page):
    choose_drill(page, "odd-man")
    for index, version in enumerate(VERSIONS):
        drill = drill_data(page, index)
        kinds = [a["kind"] for a in drill["actors"]]
        assert kinds.count("player") == 10, version
        assert kinds.count("goalie") == (1 if version == "with-goalie" else 0), version
        assert "save" not in text_of(drill).lower() or version == "with-goalie"
    assert drill.get("goal") is not False
    assert page.locator("#goal").is_visible()


def test_everyone_stays_out_of_the_crease_and_the_goalie_stays_in_front_of_the_goal(page):
    for version, take, drill in every_take(page):
        for actor in drill["actors"]:
            if actor["kind"] == "player":
                for key in actor["keys"]:
                    d = ((key["x"] - GOAL[0]) ** 2 + (key["y"] - GOAL[1]) ** 2) ** 0.5
                    assert d >= 3.2, (version, take, actor["id"], key)
        goalie = [a for a in drill["actors"] if a["id"] == "goalie"]
        for key in goalie[0]["keys"] if goalie else []:
            d = ((key["x"] - GOAL[0]) ** 2 + (key["y"] - GOAL[1]) ** 2) ** 0.5
            assert d <= 3.0, (version, take, key)


def test_nobody_runs_faster_than_a_sprint_or_stacks_up(page):
    for version, take, drill in every_take(page):
        players = [a for a in drill["actors"] if a["kind"] == "player"]
        for actor in players:
            keys = actor["keys"]
            for a, b in zip(keys, keys[1:], strict=False):
                speed = ((b["x"] - a["x"]) ** 2 + (b["y"] - a["y"]) ** 2) ** 0.5 / (b["t"] - a["t"])
                assert speed <= 8.4, (version, take, actor["id"], a, b, speed)
        worst = page.evaluate(
            """([players, duration]) => {
          let worst = 99;
          for (let t = 0; t <= duration; t += 0.25) {
            const pts = players.map((p) => LAX.trackAt(p.keys, t));
            for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++)
              worst = Math.min(worst, Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y));
          }
          return worst;
        }""",
            [players, drill["duration"]],
        )
        assert worst >= 0.8, (version, take, worst)


def test_a_player_with_a_shot_takes_it_and_the_round_ends_with_a_reset(page):
    for version, take, drill in every_take(page):
        text = text_of(drill)
        assert "has a shot and takes it" in text, (version, take)
        says = [s["text"] for s in drill["speech"]]
        assert says[-1] == "Reset!", (version, take)
        # after the reset everyone is back in line, out of bounds
        for actor in drill["actors"]:
            if actor["kind"] == "player":
                assert actor["keys"][-1]["x"] < 15, (version, take, actor["id"])


def test_what_happens_after_a_goal_depends_on_the_version(page):
    reset = drill_data(page, 1)
    assert "goal" in text_of(reset) and [s["text"] for s in reset["speech"]].count("New ball!") == 0
    new_ball = drill_data(page, 2)
    assert [s["text"] for s in new_ball["speech"]].count("New ball!") == 1
    assert [s["text"] for s in new_ball["speech"]].count("Release!") == 0
    # the standard round releases a player from each line with every new ball, up to 5 on 4
    standard = drill_data(page, 0)
    releases = [s for s in standard["speech"] if s["text"] == "Release!"]
    balls = [s for s in standard["speech"] if s["text"] == "New ball!"]
    assert len(releases) == 3 and len(balls) == 3
    assert {r["t"] for r in releases} == {b["t"] for b in balls}, (
        "each release comes with a new ball"
    )
    text = text_of(standard)
    assert "Now 3 red against 2 blue" in text and "Now 5 red against 4 blue" in text


def test_the_team_a_player_down_goes_on_offense_when_it_gets_the_ball(page):
    drill = drill_data(page, 3)
    assert "no take back" in text_of(drill)
    first_shot = next(c["text"] for c in drill["captions"] if "has a shot" in c["text"])
    assert first_shot.startswith("Blue")


def test_the_seed_menu_works_for_odd_man(page):
    choose_drill(page, "odd-man")
    assert page.locator("#take option").count() == 5
    first = page.evaluate("LAX.app.engine.drill.seed")
    page.select_option("#take", "1")
    page.wait_for_function("(first) => LAX.app.engine.drill.seed !== first", arg=first)
