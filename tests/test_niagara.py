from __future__ import annotations

from conftest import choose_drill, load_every_take

GOAL = (30, 15)
CONE = (30, 50)  # 35 yards back from the goal line extended (y = 15)
VERSIONS = (
    "standard",
    "defender-first",
    "goal-reset",
    "blue-offense",
    "no-goalie",
    "takeaway-goalie",
    "takeaway-carry",
    "takeaway-coach",
)
NO_GOALIE = ("no-goalie", "takeaway-carry", "takeaway-coach")


def drill_data(page, version=0, take=0):
    return page.evaluate(
        f"LAX.resolveDrill(LAX.DRILLS.find((d) => d.id === 'niagara'), {version}, {take})"
    )


def every_take(page):
    load_every_take(page)
    counts = page.evaluate(
        "LAX.DRILLS.find((d) => d.id === 'niagara').variants.map((v) => v.seeds.length)"
    )
    return [(i, k, drill_data(page, i, k)) for i, n in enumerate(counts) for k in range(n)]


def actor(drill, actor_id):
    return next(a for a in drill["actors"] if a["id"] == actor_id)


def at(page, drill, actor_id, t):
    return page.evaluate("([keys, t]) => LAX.trackAt(keys, t)", [actor(drill, actor_id)["keys"], t])


def players(drill):
    return [a for a in drill["actors"] if a["kind"] == "player"]


def counts_at(page, drill, times):
    """Players past the 35 yard line (y < 49.5), i.e. out of the lines, by team, at each time."""
    return page.evaluate(
        """([players, times]) => times.map((t) => {
          const c = { a: 0, b: 0 };
          for (const p of players) if (LAX.trackAt(p.keys, t).y < 49.5) c[p.team] += 1;
          return c;
        })""",
        [players(drill), times],
    )


def on_field(page, drill, t):
    return counts_at(page, drill, [t])[0]


def shot_times(drill):
    return [c["t"] for c in drill["captions"] if "has a shot" in c["text"]]


def test_it_is_listed_with_eight_versions(page):
    ids = page.evaluate("LAX.DRILLS.map((d) => d.id)")
    assert ids[:4] == ["ground-ball-mania", "keep-away", "odd-man", "niagara"]
    drill = page.evaluate("LAX.DRILLS.find((d) => d.id === 'niagara')")
    assert [v["id"] for v in drill["variants"]] == list(VERSIONS)
    assert drill["title"] == "Niagara"
    assert "one player up" in drill["notes"]


def test_the_generated_data_is_current():
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parent.parent / "scripts" / "choreography.py"
    result = subprocess.run(
        [sys.executable, str(script), "--check"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_coach_and_cone_are_35_yards_back_and_the_lines_wait_behind_the_35(page):
    choose_drill(page, "niagara")
    drill = drill_data(page)
    cone = actor(drill, "cone")["keys"][0]
    coach = actor(drill, "coach")["keys"][0]
    assert (cone["x"], cone["y"]) == CONE  # in the middle of the field, on the 35 yard line
    assert coach["x"] == CONE[0] and coach["y"] > CONE[1]  # just behind the cone
    assert coach["y"] - cone["y"] < 3
    assert [a["id"] for a in drill["actors"] if a["kind"] == "coach"] == ["coach"]
    for p in players(drill):
        start = p["keys"][0]
        assert start["y"] > CONE[1], p["id"]  # behind the 35
        assert (start["x"] < CONE[0]) == (p["team"] == "a"), p["id"]  # red west, blue east


ALL_TAKES_JS = """(body) => {
  const drill = LAX.DRILLS.find((d) => d.id === 'niagara');
  const problems = [];
  const onField = (d, t) => {
    const c = { a: 0, b: 0 };
    for (const p of d.actors.filter((a) => a.kind === 'player'))
      if (LAX.trackAt(p.keys, t).y < 49.5) c[p.team] += 1;
    return c;
  };
  const check = new Function('d', 'onField', 'problems', 'name', body);
  drill.variants.forEach((variant, i) => variant.seeds.forEach((_, k) =>
    check(LAX.resolveDrill(drill, i, k), onField, problems, `${variant.id}/${k}`)));
  return problems;
}"""


def check_every_take(page, body):
    load_every_take(page)
    return page.evaluate(ALL_TAKES_JS, body)


def test_two_from_each_team_start_then_the_winners_next_player_takes_a_free_pass(page):
    bad = check_every_take(
        page,
        """
        const wins = d.captions.find((c) => c.text.includes('wins the ground ball')).text;
        const w = wins.startsWith('Red') ? 'a' : 'b';
        const early = onField(d, 3.2), later = onField(d, 5.4);
        if (early.a !== 2 || early.b !== 2) problems.push([name, 'start', early]);
        if (later[w] !== 3 || later[w === 'a' ? 'b' : 'a'] !== 2) problems.push([name, 'free pass', later]);
        if (!d.captions.slice(0, 8).some((c) => c.text.includes('free pass'))) problems.push([name, 'no caption']);
        """,
    )
    assert bad == [], bad[:5]


def test_the_offense_is_never_more_than_one_up_and_the_defense_only_gets_to_even(page):
    bad = check_every_take(
        page,
        """
        const text = d.captions.map((c) => c.text).join(' ');
        const w = text.includes('Red wins the ground ball') ? 'a' : 'b';
        for (const c of d.captions.filter((c) => c.text.includes('has a shot'))) {
          const counts = onField(d, c.t);
          const off = counts[w], dfn = counts[w === 'a' ? 'b' : 'a'];
          if (!(off - 1 <= dfn && dfn <= off)) problems.push([name, c.t, counts]);
        }
        for (const m of text.matchAll(/now (\\d) on (\\d)/g)) {
          const off = Number(m[1]), dfn = Number(m[2]);
          if (!(dfn <= off && off <= dfn + 1)) problems.push([name, 'caption', m[0]]);
        }
        """,
    )
    assert bad == [], bad[:5]


def test_possession_is_called_when_the_ground_ball_is_won_and_the_free_pass_comes_right_away(page):
    bad = check_every_take(
        page,
        """
        const call = d.speech.find((s) => s.text === 'Possession!');
        if (!call) { problems.push([name, 'no possession call']); return; }
        const wins = d.captions.find((c) => c.text.includes('wins the ground ball'));
        if (Math.abs(wins.t - call.t) > 0.01) problems.push([name, 'call is not at the win']);
        const w = wins.text.startsWith('Red') ? 'a' : 'b';
        const players = d.actors.filter((a) => a.kind === 'player' && a.team === w);
        // the third player of the winning team has left the line by the time of the call + 1 s
        const out = (t) => players.filter((p) => LAX.trackAt(p.keys, t).y < 49.5).length;
        if (out(call.t) !== 2) problems.push([name, 'two out at the call', out(call.t)]);
        if (out(call.t + 1.0) !== 3) problems.push([name, 'third pops out at once', out(call.t + 1.0)]);
        // and the ball is in his stick no later than two seconds after the call
        const ball = d.actors.find((a) => a.id === 'ball').keys;
        const landed = LAX.trackAt(ball, call.t + 2.0);
        const near = players.some((p) => {
          const at = LAX.trackAt(p.keys, call.t + 2.0);
          return Math.hypot(landed.x - at.x, landed.y - at.y) < 1.6 && at.y > 42;
        });
        if (!near) problems.push([name, 'free pass not there yet']);
        """,
    )
    assert bad == [], bad[:5]


def test_nobody_goes_back_to_the_lines_until_a_reset_is_called(page):
    bad = check_every_take(
        page,
        """
        const reset = d.speech.find((s) => s.text === 'Reset!');
        const until = reset ? reset.t : d.duration;
        for (const p of d.actors.filter((a) => a.kind === 'player')) {
          let played = false;
          for (let t = 0; t < until; t += 0.25) {
            const y = LAX.trackAt(p.keys, t).y;
            if (y < 49) played = true;
            if (played && y > 51) problems.push([name, p.id, 'went back to the line', t]);
          }
        }
        """,
    )
    assert bad == [], bad[:5]


def test_the_player_nearest_the_coach_goes_to_him_for_the_next_ball(page):
    bad = check_every_take(
        page,
        """
        const fed = d.speech.filter((s) => s.text === 'New ball!' || s.text === 'Ball in!');
        const ball = d.actors.find((a) => a.id === 'ball').keys;
        const players = d.actors.filter((a) => a.kind === 'player');
        for (const item of fed) {
          const landed = ball.filter((k) => k.t > item.t + 0.3)[0];
          const near = players
            .map((p) => ({ p, at: LAX.trackAt(p.keys, landed.t) }))
            .sort((a, b) => Math.hypot(a.at.x - landed.x, a.at.y - landed.y) - Math.hypot(b.at.x - landed.x, b.at.y - landed.y))[0];
          // he came toward the coach: the ball is given close to the 35, not up by the goal
          if (landed.y < 42) problems.push([name, 'the ball went up to him', landed.y]);
          // and he is the offensive player nearest the 35 yard line
          const w = d.captions.find((c) => c.text.includes('wins the ground ball')).text.startsWith('Red') ? 'a' : 'b';
          const off = players.filter((p) => p.team === w).map((p) => LAX.trackAt(p.keys, landed.t).y).filter((y) => y < 50);
          if (near.at.y < Math.max(...off) - 0.5) problems.push([name, 'not the nearest to the 35']);
        }
        """,
    )
    assert bad == [], bad[:5]


def test_the_player_who_goes_for_the_next_ball_runs_he_does_not_walk(page):
    bad = check_every_take(
        page,
        """
        const calls = d.captions.filter((c) => c.text.includes('goes toward the coach'));
        const players = d.actors.filter((a) => a.kind === 'player');
        for (const c of calls) {
          let fastest = 0;
          for (const p of players) {
            for (let i = 1; i < p.keys.length; i++) {
              const a = p.keys[i - 1], b = p.keys[i];
              if (a.t < c.t - 0.5 || a.t > c.t + 6 || b.t - a.t < 0.5) continue;
              const dist = Math.hypot(b.x - a.x, b.y - a.y);
              if (dist > 4) fastest = Math.max(fastest, dist / (b.t - a.t));
            }
          }
          if (fastest < 5.0) problems.push([name, c.t, 'too slow', fastest]);
        }
        """,
    )
    assert bad == [], bad[:5]


def test_the_standard_round_releases_until_all_five_are_out(page):
    drill = drill_data(page, 0)
    text = " ".join(c["text"] for c in drill["captions"])
    assert "now 4 on 3" in text and "now 5 on 4" in text and "now 5 on 5" in text
    assert "Release a defender!" in text
    last = on_field(page, drill, shot_times(drill)[-1])
    assert last == {"a": 5, "b": 5}
    says = [s["text"] for s in drill["speech"]]
    assert says.count("Release!") == 2 and says.count("Release a defender!") == 1
    assert says[-1] == "Reset!"


def test_a_defender_can_be_released_first_to_make_it_even(page):
    drill = drill_data(page, 1)
    text = " ".join(c["text"] for c in drill["captions"])
    assert "now 3 on 3" in text and "now 4 on 4" in text and "now 5 on 5" in text


def test_a_new_ball_is_fed_free_to_the_offensive_player_nearest_the_35(page):
    load_every_take(page)
    bad = page.evaluate(
        """() => {
      const drill = LAX.DRILLS.find((d) => d.id === 'niagara');
      const problems = [];
      drill.variants.forEach((variant, i) => variant.seeds.forEach((_, k) => {
        const d = LAX.resolveDrill(drill, i, k);
        const wins = d.captions.find((c) => c.text.includes('wins the ground ball')).text;
        const team = wins.startsWith('Red') ? 'a' : 'b';
        const players = d.actors.filter((a) => a.kind === 'player');
        const ball = d.actors.find((a) => a.id === 'ball').keys;
        const fed = d.speech.filter((s) => s.text === 'New ball!' || s.text === 'Ball in!');
        if (!fed.length && variant.id !== 'goal-reset') problems.push([variant.id, k, 'nothing is fed']);
        for (const item of fed) {
          const start = LAX.trackAt(ball, item.t + 0.05);
          if (Math.abs(start.x - 30) > 1.5 || start.y < 48.8) problems.push([variant.id, k, 'not from the coach', start]);
          const landed = ball.filter((key) => key.t > item.t + 0.5)[0];
          const nearest = players
            .map((p) => ({ p, at: LAX.trackAt(p.keys, landed.t) }))
            .sort((a, b) => Math.hypot(a.at.x - landed.x, a.at.y - landed.y) - Math.hypot(b.at.x - landed.x, b.at.y - landed.y))[0];
          if (nearest.p.team !== team) problems.push([variant.id, k, 'fed to the wrong team']);
          if (Math.hypot(nearest.at.x - landed.x, nearest.at.y - landed.y) > 1.6) problems.push([variant.id, k, 'not in a stick']);
        }
      }));
      return problems;
    }"""
    )
    assert bad == [], bad[:5]


def test_the_team_that_won_the_ground_ball_does_all_the_shooting(page):
    bad = check_every_take(
        page,
        """
        const shots = d.captions.filter((c) => c.text.includes('has a shot')).map((c) => c.text);
        if (new Set(shots.map((t) => t.split(' ')[0])).size > 1) problems.push([name, 'two teams shoot']);
        const blue = name.startsWith('blue-offense');
        if (shots.length && shots[0].startsWith('Blue') !== blue) problems.push([name, shots[0]]);
        """,
    )
    assert bad == [], bad[:5]


def test_the_goalie_is_optional(page):
    for index, version in enumerate(VERSIONS):
        drill = drill_data(page, index)
        kinds = [a["kind"] for a in drill["actors"]]
        assert kinds.count("goalie") == (0 if version in NO_GOALIE else 1), version
        text = " ".join(c["text"] for c in drill["captions"]).lower()
        if version in NO_GOALIE:
            assert "save" not in text and "goalie" not in text.replace("no goalie", ""), version


def test_everyone_stays_out_of_the_crease_and_nobody_runs_too_fast_or_stacks_up(page):
    bad = check_every_take(
        page,
        """
        const players = d.actors.filter((a) => a.kind === 'player');
        for (const p of players) {
          for (const key of p.keys)
            if (Math.hypot(key.x - 30, key.y - 15) < 3.2) problems.push([name, p.id, 'crease', key]);
          for (let i = 1; i < p.keys.length; i++) {
            const a = p.keys[i - 1], b = p.keys[i];
            const speed = Math.hypot(b.x - a.x, b.y - a.y) / (b.t - a.t);
            if (speed > 8.4) problems.push([name, p.id, 'speed', speed]);
          }
        }
        let worst = 99;
        for (let t = 0; t <= d.duration; t += 0.25) {
          const pts = players.map((p) => LAX.trackAt(p.keys, t));
          for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++)
            worst = Math.min(worst, Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y));
        }
        if (worst < 0.8) problems.push([name, 'stacked', worst]);
        """,
    )
    assert bad == [], bad[:5]


def test_the_round_ends_with_a_reset_and_everyone_back_in_the_lines(page):
    bad = check_every_take(
        page,
        """
        if (d.speech[d.speech.length - 1].text !== 'Reset!') problems.push([name, 'no reset']);
        for (const p of d.actors.filter((a) => a.kind === 'player')) {
          const last = p.keys[p.keys.length - 1];
          if (last.y <= 50 || (last.x < 30) !== (p.team === 'a')) problems.push([name, p.id, last]);
        }
        """,
    )
    assert bad == [], bad[:5]


def test_with_a_goalie_a_takeaway_goes_back_to_the_goalie_who_throws_it_to_the_coach(page):
    load_every_take(page)
    for take in range(5):
        drill = drill_data(page, VERSIONS.index("takeaway-goalie"), take)
        text = " ".join(c["text"] for c in drill["captions"])
        assert "takes the ball away and passes it back to the goalie" in text, take
        assert "throws it back to the coach at the cone" in text, take
        # the ball really goes to the goalie, then to the coach, then out to the offense
        ball = actor(drill, "ball")["keys"]
        goalie = actor(drill, "goalie")["keys"]
        said = [s for s in drill["speech"] if s["text"] == "Ball in!"]
        assert said, take
        assert any(
            ((k["x"] - 30) ** 2 + (k["y"] - 17) ** 2) ** 0.5 < 3.0 and k["t"] < said[0]["t"]
            for k in ball
        ), take
        first = said[0]["t"]
        held = at(page, drill, "ball", first)
        assert abs(held["x"] - CONE[0]) < 1.5 and held["y"] > CONE[1] - 1.5, take
        assert goalie  # he is there the whole time


def test_without_a_goalie_the_defense_carries_it_to_the_35_or_passes_it_to_the_coach(page):
    load_every_take(page)
    for take in range(5):
        carry = drill_data(page, VERSIONS.index("takeaway-carry"), take)
        text = " ".join(c["text"] for c in carry["captions"])
        assert "carries it out to the 35 yard line" in text and "the coach takes it" in text, take
        at_the_line = [k for k in actor(carry, "ball")["keys"] if k["y"] >= CONE[1] - 1.2]
        assert at_the_line, take
        coach = drill_data(page, VERSIONS.index("takeaway-coach"), take)
        text = " ".join(c["text"] for c in coach["captions"])
        assert "passes it to the coach instead" in text, take
        assert [s["text"] for s in coach["speech"]].count("Ball in!") >= 1, take
        for drill in (carry, coach):
            assert "goalie" not in [a["kind"] for a in drill["actors"]]


def test_a_save_also_goes_back_to_the_coach(page):
    drill = drill_data(page, 0)
    text = " ".join(c["text"] for c in drill["captions"])
    assert "makes the save" in text and "throws it back to the coach at the cone" in text
    assert "Ball in!" in [s["text"] for s in drill["speech"]]


def test_the_seed_menu_works_for_niagara(page):
    choose_drill(page, "niagara")
    assert page.locator("#take option").count() == 5
    first = page.evaluate("LAX.app.engine.drill.seed")
    page.select_option("#take", "1")
    page.wait_for_function("(first) => LAX.app.engine.drill.seed !== first", arg=first)
