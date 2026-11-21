#!/usr/bin/env python3
"""Choreographs the keep-away and the odd man, offense/defense drills.

It writes src/js/keepaway_data.js and src/js/oddman_data.js.

    python3 scripts/choreography.py          # rewrite the data module
    python3 scripts/choreography.py --check  # exit 1 if the committed file is out of date

Keep-away is not scripted by hand: it is played out by a small simulation, one step a second.
The team with the ball spreads out and moves to get open, passes to whoever is open with a clear
lane, and the other team, always a player down, has one defender on the ball and the rest cover the
most dangerous players. The generator then checks the result: players stay clear of each other and
the coaches, nobody runs faster than a player really can, everyone stays in bounds, and passes only
go through a defender where the round says so (a turnover). The output is plain data, like every
other drill, and a test checks it matches what this script produces.

Rounds ("variants") are listed in ROUNDS at the bottom. The first is the default. Each round lists
several random seeds; every seed is a different take (who gets open, who passes to whom), and the
page has a Seed menu to play them. The first seed of a round is its default. A new drill can
reuse the pieces here: the version menu and the field markings are generic features of the drills.

The field here is a small one (yards): the west sideline is x = 15 and the east boundary x = 45
(30 wide, with the goal in the middle at x = 30), and it runs from y = 5 (10 yards north of the goal
line extended) to y = 55 (40 yards south). The 20-yard line is y = 35.
"""

from __future__ import annotations

import itertools
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "js" / "keepaway_data.js"
OUT_ODD = ROOT / "src" / "js" / "oddman_data.js"
TAKES_DIR = ROOT / "src" / "takes"

# ---- the field and the people --------------------------------------------------------------
WEST, EAST, NORTH, SOUTH = 15.0, 45.0, 5.0, 55.0
LINE_Y = 35.0
CONE = (15.2, LINE_Y)
COACH = (13.3, LINE_Y)
COACH2 = (37.5, 40.0)  # where the coach in the field starts
COACH_HOME = (46.5, 41.0)  # out of bounds, east of the boundary: where the coach drifts to
V_COACH = 3.0  # the field coach steps aside at a brisk walk, yards a second
BALL_START = (14.5, 35.5)
BALL_SPOT = (24.0, 36.2)  # where the coach's roll stops, about 9 yards from the cone

ICON_SCALE = 1.35
ICON = 1.8 * ICON_SCALE  # the width of a player icon, in yards
POCKET = (0.375 * ICON, -0.25 * ICON)  # where the stick's pocket is, from the player's centre
QUEUE_X = 14.0  # the lines wait just outside the sideline (x = 15); players run in from there
SLOT = 2.5  # spacing of players waiting in line
FIRST = 2.8  # the front player's distance from the cone
KEEP_ZONE = (17.8, 43.2, 24.0, 48.0)  # x0, x1, y0, y1: where keep-away happens
ODD_ZONE = (17.8, 43.2, 18.0, 48.0)  # odd man, offense/defense reaches toward the goal
ZONE = KEEP_ZONE
KEEP_OUT = False  # True: players stay out of the crease
GOAL = (30.0, 15.0)
GOAL_KEEP = 4.2  # players stay this far from the middle of the goal
SHOT_MIN, SHOT_MAX = 5.0, 11.5  # a player shoots from this far from the goal
GOALIE_HOME = 1.9  # the goalie stands this far from the middle of the goal, toward the ball
CENTRE = (30.5, 36.5)

DT = 1.0  # one simulation step
V_RUN = 5.4  # yards a second when running in play
V_WALK = 3.0
V_CAP = 6.4  # nobody is ever faster than this
SAME_MIN, OPP_MIN, COACH_MIN = 2.7, 1.5, 2.6  # clearances between players (centres)
ENDS_FACTOR = 0.8  # between steps a pair may be this much closer than the step limits
MAX_FLIGHT = 15.0  # longest pass, yards
MIN_FLIGHT = 2.6  # shortest pass, yards


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def unit(v):
    n = math.hypot(v[0], v[1])
    return (v[0] / n, v[1] / n) if n > 1e-9 else (0.0, 0.0)


def add(a, b, k=1.0):
    return (a[0] + b[0] * k, a[1] + b[1] * k)


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def lerp(a, b, u):
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


def use_zone(zone, keep_out):
    global ZONE, KEEP_OUT
    ZONE, KEEP_OUT = zone, keep_out


def clamp_zone(p, margin=0.0):
    c = (
        min(max(p[0], ZONE[0] + margin), ZONE[1] - margin),
        min(max(p[1], ZONE[2] + margin), ZONE[3] - margin),
    )
    if KEEP_OUT and dist(c, GOAL) < GOAL_KEEP + margin:
        away = unit(sub(c, GOAL)) if dist(c, GOAL) > 1e-6 else (0.0, 1.0)
        c = add(GOAL, away, GOAL_KEEP + margin)
    return c


def seg_dist(p, a, b):
    """Distance from point p to the segment a-b."""
    ab = sub(b, a)
    n2 = ab[0] ** 2 + ab[1] ** 2
    if n2 < 1e-9:
        return dist(p, a)
    u = min(max(((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / n2, 0.0), 1.0)
    return dist(p, lerp(a, b, u))


def min_gap(a0, a1, b0, b1):
    """Closest two people get while each walks a straight line from 0 to 1."""
    d0, d1 = sub(a0, b0), sub(a1, b1)
    rel = sub(d1, d0)
    n2 = rel[0] ** 2 + rel[1] ** 2
    u = 0.0 if n2 < 1e-9 else min(max(-(d0[0] * rel[0] + d0[1] * rel[1]) / n2, 0.0), 1.0)
    return dist(lerp(d0, d1, u), (0.0, 0.0))


class Player:
    def __init__(self, pid, team, slot):
        self.id = pid
        self.team = team  # "a" is red (south), "b" is blue (north)
        self.slot = slot  # place in line
        self.pos = slot_pos(team, slot)
        self.keys: list[tuple[float, float, float]] = []
        self.playing = False
        self.heading = (1.0, 0.0)


def slot_pos(team, slot):
    if team == "a":
        return (QUEUE_X, LINE_Y + FIRST + SLOT * slot)
    return (QUEUE_X, LINE_Y - FIRST - SLOT * slot)


def pocket_of(pos):
    return (pos[0] + POCKET[0], pos[1] + POCKET[1])


def r2(v):
    return round(v + 0.0, 2)


class Round:
    """One choreographed round of keep-away."""

    def __init__(self, spec):
        self.spec = spec
        self.offense = spec.get("mode") == "offense"
        use_zone(ODD_ZONE if self.offense else KEEP_ZONE, self.offense)
        self.rng = random.Random(spec["seed"])
        self.players = {}
        for i in range(5):
            self.players[f"s{i + 1}"] = Player(f"s{i + 1}", "a", i)
            self.players[f"n{i + 1}"] = Player(f"n{i + 1}", "b", i)
        self.ball: list[tuple] = []
        self.captions: list[tuple[float, str]] = []
        self.speech: list[tuple[float, float, str, str]] = []  # time, seconds shown, who, text
        self.carrier: Player | None = None
        self.on_ball: Player | None = None
        self.t = 0.0
        self.hold = 0
        self.pass_times = []
        self.g_pos = (GOAL[0], GOAL[1] + GOALIE_HOME)  # the goalie (odd man, offense/defense)
        self.g_keys = [(0.0, self.g_pos[0], self.g_pos[1])]
        self.g_next = self.g_pos
        self.g_dive: list[tuple] = []
        self.shot_i = 0
        self.shot_ready = spec.get("shot_after", 6.0)
        self.finished = False
        self.loose_spot = None
        self.reset_t = 0.0
        self.reset_targets: dict[str, tuple[float, float]] = {}
        self.reset_in: set[str] = set()
        self.nb_release = False
        self.nb_phase = None  # new ball: None, 'out' (play stopped), 'rolling', 'done'
        self.nb_roll_t = 0.0
        self.nb_land = 0.0
        self.nb_out = (0.0, 0.0)
        self.pending: list[tuple] = []
        self.c_cur = COACH2
        self.c_nxt = COACH2
        self.coach_keys = [(0.0, COACH2[0], COACH2[1])]
        self.arrives = 0.0  # when the ball in flight reaches its receiver
        self.last_passer: Player | None = None
        self.queues = {"a": [], "b": []}

    # ---- helpers -----------------------------------------------------------------------
    def team_of(self, p):
        return [q for q in self.players.values() if q.playing and q.team == p.team]

    def playing(self, team=None):
        return [q for q in self.players.values() if q.playing and (team is None or q.team == team)]

    def caption(self, t, text):
        self.captions.append((r2(t), text))

    def say(self, t, seconds, who, text):
        self.speech.append((r2(t), seconds, who, text))

    def key(self, p, t):
        p.keys.append((t, p.pos[0], p.pos[1]))

    # ---- the opening: the coach's roll and the fight for the ground ball ---------------
    def opening(self):
        win = self.spec["gb_winner"]
        spot_win = (BALL_SPOT[0] - POCKET[0], BALL_SPOT[1] - POCKET[1])
        slots = {pid: p.pos for pid, p in self.players.items()}
        scripts = {}
        if win == "S":
            lead = ("s1", spot_win)
            support = ("s2", add(spot_win, (-2.4, 2.4)))
            fighter = ("n1", add(spot_win, (0.5, -2.1)))
        else:
            lead = ("n1", spot_win)
            support = None
            fighter = ("s1", add(spot_win, (0.5, 2.0)))
        runners = {lead[0]: lead[1], fighter[0]: fighter[1]}
        if win == "S":
            runners[support[0]] = support[1]
        else:
            runners["s2"] = add(spot_win, (-2.5, 4.2))
        for pid, end in runners.items():
            scripts[pid] = [(0.0, slots[pid]), (0.7, slots[pid]), (2.9, end)]
        # the rest of each line steps up as the front players go
        gone_s = [i for i in ("s1", "s2")]
        gone_n = ["n1"]
        for team, gone in (("a", gone_s), ("b", gone_n)):
            queue = [pid for pid in (f"{'s' if team == 'a' else 'n'}{i + 1}" for i in range(5))]
            queue = [pid for pid in queue if pid not in gone]
            for new_slot, pid in enumerate(queue):
                end = slot_pos(team, new_slot)
                scripts[pid] = [(0.0, slots[pid]), (1.6, slots[pid]), (2.9, end)]
        for pid, keys in scripts.items():
            p = self.players[pid]
            p.keys = [(t, x, y) for t, (x, y) in keys]
            p.pos = keys[-1][1]
            p.playing = pid in runners
        self.queues["a"] = [f"s{i}" for i in range(3, 6)]
        self.queues["b"] = [f"n{i}" for i in range(2, 6)]
        for queue in self.queues.values():
            for slot, pid in enumerate(queue):
                self.players[pid].slot = slot
        self.ball = [
            (0.0, BALL_START[0], BALL_START[1], 0),
            (0.5, BALL_START[0], BALL_START[1], 0),
            (1.9, BALL_SPOT[0], BALL_SPOT[1], 1),
            (2.9, BALL_SPOT[0], BALL_SPOT[1], 0),
        ]
        self.carrier = self.players[lead[0]]
        self.t = 2.9
        self.caption(
            0,
            "Two teams line up on the west sideline: blue north of the cone, red south of it. "
            "The coach stands just behind the cone.",
        )
        self.say(0.6, 1.8, "coach", "Ground ball!")
        self.caption(0.6, "The coach rolls a ball out, about 9 yards along the 20-yard line.")
        self.caption(
            1.0, "Two red players and one blue player, the ones closest to the cone, go for it."
        )
        self.caption(2.3, "They fight for the ground ball.")
        color = "Red" if win == "S" else "Blue"
        if self.offense:
            extra = (
                " Blue is the team a player down, and now it is on offense: no take back."
                if win == "N"
                else " Whoever has the ball is on offense now, and shoots when there is a shot."
            )
            self.caption(2.9, f"{color} scoops it. {self.odds_text()}.{extra}")
        else:
            self.caption(2.9, f"{color} scoops it. Keep-away starts: {self.odds_text()}.")

    def odds_text(self):
        s, n = len(self.playing("a")), len(self.playing("b"))
        return f"{s} red against {n} blue, so blue is a player down"

    # ---- one simulation step --------------------------------------------------------------
    def step(self):
        t = self.t
        self.handle_events(t)
        in_play = self.playing()
        self.move_coach(in_play)
        carrier = self.carrier
        loose = carrier is None
        nxt: dict[str, tuple[float, float]] = {}

        # waiting players step up in line
        for team in ("a", "b"):
            for slot, pid in enumerate(self.queues[team]):
                p = self.players[pid]
                p.slot = slot
                goal = slot_pos(team, slot)
                # wait until the player who just left that spot has cleared it
                if any(q.playing and dist(q.pos, goal) < 3.6 for q in in_play):
                    goal = p.pos
                nxt[pid] = self.steer(p, goal, V_WALK)
                # nobody in line closes up on the player ahead of them
                if slot > 0:
                    ahead = nxt[self.queues[team][slot - 1]]
                    if dist(nxt[pid], ahead) < SLOT - 0.15:
                        nxt[pid] = p.pos

        if self.nb_phase == "reset" and t + 1e-9 >= self.reset_t:
            self.start_reset()
        if loose and self.nb_phase == "out" and t + 1e-9 >= self.nb_roll_t:
            self.roll_new_ball(t)
        if loose and self.nb_phase in ("out", "reset"):
            for p in in_play:  # play is stopped while the coach gets a new ball
                nxt[p.id] = p.pos
        elif self.nb_phase == "resetting":
            for p in in_play:  # everyone walks back to the end of their line
                goal = self.reset_targets[p.id]
                # come in from the field side so nobody has to cut through the line
                if p.id not in self.reset_in and dist(p.pos, (17.5, goal[1])) < 0.6:
                    self.reset_in.add(p.id)
                if p.id not in self.reset_in:
                    goal = (17.5, goal[1])
                nxt[p.id] = self.steer(p, goal, V_RUN * 0.8)
        elif loose:
            self.chase_loose(t, nxt)
        else:
            offence = [p for p in in_play if p.team == carrier.team]
            defence = [p for p in in_play if p.team != carrier.team]
            for p in offence:
                target = (
                    self.carry_target(p, defence)
                    if p is carrier
                    else self.open_target(p, carrier, offence, defence, nxt)
                )
                nxt[p.id] = self.steer(p, target, V_RUN)
            self.defence_targets(t, carrier, offence, defence, nxt)

        self.separate(nxt)
        self.check_between(nxt)

        # a new ball has been scooped up
        if loose and self.nb_phase == "rolling" and t + DT + 1e-9 >= self.nb_land:
            near = min(in_play, key=lambda q: dist(pocket_of(nxt[q.id]), self.loose_spot))
            if dist(pocket_of(nxt[near.id]), self.loose_spot) < 0.3:
                self.scoop(near, t, nxt)

        # what happens to the ball during this step
        ball_keys = [(t,) + self.ball_xy(carrier) + (0,)] if carrier else []
        if carrier and not loose:
            ball_keys += self.ball_events(t, carrier, nxt)
        ball_keys += self.pending
        self.pending = []
        for pid, pos in nxt.items():
            p = self.players[pid]
            p.pos = pos
            self.key(p, t + DT)
        self.move_goalie(t)
        if self.nb_phase == "resetting" and all(
            dist(self.players[pid].pos, goal) < 0.3 for pid, goal in self.reset_targets.items()
        ):
            self.finish_reset()
        self.c_cur = self.c_nxt
        self.t = t + DT
        self.finish_step(ball_keys)

    def move_goalie(self, t):
        if self.g_dive:  # a dive for a shot: the keys were worked out with the shot
            self.g_keys += self.g_dive
            self.g_pos = (self.g_dive[-1][1], self.g_dive[-1][2])
            self.g_dive = []
            return
        target = self.goalie_target()
        gap = dist(self.g_pos, target)
        step = min(gap, 4.2 * DT)
        if gap > 1e-9:
            self.g_pos = add(self.g_pos, unit(sub(target, self.g_pos)), step)
        self.g_keys.append((t + DT, self.g_pos[0], self.g_pos[1]))

    def finish_reset(self):
        for team in ("a", "b"):
            for p in sorted(
                (q for q in self.playing(team)),
                key=lambda q: dist(self.reset_targets[q.id], slot_pos(team, 0)),
            ):
                p.playing = False
                self.queues[team].append(p.id)
        self.finished = True
        self.nb_phase = "done"

    def move_coach(self, in_play):
        """The coach in the field steps out of the players' way, then drifts back out of bounds."""
        cur = self.c_cur
        ahead = [(q.pos, add(q.pos, q.heading, V_RUN * 0.8)) for q in in_play]

        def clearance(c):
            return min((min(dist(c, a), dist(c, b)) for a, b in ahead), default=9.0)

        best, best_score = cur, -1e9
        candidates = [cur]
        for radius in (V_COACH * 0.5, V_COACH):
            for k in range(16):
                ang = k * math.pi / 8
                candidates.append(
                    (cur[0] + radius * math.cos(ang), cur[1] + radius * math.sin(ang))
                )
        for c in candidates:
            if not (19.0 <= c[0] <= 47.5 and 13.5 <= c[1] <= 48.5):
                continue
            score = min(clearance(c), 7.0) - 0.2 * dist(c, COACH_HOME) - 0.25 * dist(c, cur)
            if score > best_score:
                best, best_score = c, score
        self.c_nxt = best
        self.coach_keys.append((self.t + DT, best[0], best[1]))

    def ball_xy(self, p):
        q = pocket_of(p.pos)
        return (q[0], q[1])

    def pos_at(self, p, nxt, u):
        return lerp(p.pos, nxt.get(p.id, p.pos), u)

    # ---- who moves where ---------------------------------------------------------------
    def steer(self, p, target, vmax):
        delta = sub(target, p.pos)
        d = math.hypot(*delta)
        step = min(d, vmax * DT)
        if d > 1e-9:
            p.heading = unit(delta)
            return add(p.pos, unit(delta), step)
        return p.pos

    def carry_target(self, p, defence):
        near = min(defence, key=lambda d: dist(d.pos, p.pos)) if defence else None
        away = unit(sub(p.pos, near.pos)) if near else p.heading
        to_centre = unit(sub(CENTRE, p.pos))
        v = unit(
            (
                away[0] + 0.45 * to_centre[0] + 0.3 * p.heading[0],
                away[1] + 0.45 * to_centre[1] + 0.3 * p.heading[1],
            )
        )
        if self.offense and dist(p.pos, GOAL) > SHOT_MAX - 1.5:
            v = unit(add(v, unit(sub(GOAL, p.pos)), 1.1))  # drive at the goal
        angle = self.rng.uniform(-0.5, 0.5)
        v = (
            v[0] * math.cos(angle) - v[1] * math.sin(angle),
            v[0] * math.sin(angle) + v[1] * math.cos(angle),
        )
        return clamp_zone(add(p.pos, v, 3.6), 1.0)

    def open_target(self, p, carrier, offence, defence, nxt):
        c_next = nxt.get(carrier.id) or carrier.pos
        best, best_score = None, -1e9
        taken = [nxt[q.id] for q in offence if q is not p and q.id in nxt]
        others = [q.pos for q in offence if q is not p and q.id not in nxt]
        waiting = [q.pos for q in self.players.values() if not q.playing]
        others += waiting
        for radius, k in itertools.product((2.2, 3.6, 5.2), range(12)):
            ang = k * math.pi / 6 + self.rng.uniform(-0.15, 0.15)
            c = clamp_zone((p.pos[0] + radius * math.cos(ang), p.pos[1] + radius * math.sin(ang)))
            if dist(c, p.pos) < 1.5:
                continue
            open_d = min((dist(c, d.pos) for d in defence), default=9.0)
            lane = min((seg_dist(d.pos, c, c_next) for d in defence), default=9.0)
            d_c = dist(c, c_next)
            score = 1.4 * min(open_d, 6.5) + 1.0 * min(lane, 3.5)
            score -= 0.5 * max(0.0, 6.0 - d_c) + 0.35 * max(0.0, d_c - 11.0)
            for q in taken + others:
                score -= 2.0 * max(0.0, 3.6 - dist(c, q))
                score -= 4.0 * max(0.0, 3.0 - seg_dist(q, p.pos, c))  # do not run through anyone
            score += 0.5 * (
                unit(sub(c, p.pos))[0] * p.heading[0] + unit(sub(c, p.pos))[1] * p.heading[1]
            )
            edge = min(c[0] - ZONE[0], ZONE[1] - c[0], c[1] - ZONE[2], ZONE[3] - c[1])
            score -= 1.5 * max(0.0, 2.0 - edge)
            score -= 1.2 * max(0.0, 3.0 - dist(c, self.c_nxt))
            if self.offense:  # get open near the goal, but never in the crease
                score -= 0.3 * max(0.0, dist(c, GOAL) - 9.0)
            score += self.rng.uniform(0.0, 0.6)
            if score > best_score:
                best, best_score = c, score
        return best or clamp_zone(add(p.pos, p.heading, 2.0))

    def defence_targets(self, t, carrier, offence, defence, nxt):
        c_next = nxt[carrier.id]
        if not defence:
            return
        # the defender on the ball: keep the same one unless another is clearly closer
        near = min(defence, key=lambda d: dist(d.pos, c_next))
        if (
            self.on_ball in defence
            and dist(self.on_ball.pos, c_next) < dist(near.pos, c_next) + 1.5
        ):
            near = self.on_ball
        self.on_ball = near
        mates = [q for q in offence if q is not carrier]
        deny = unit(sub(nxt.get(mates[0].id, mates[0].pos), c_next)) if mates else (0.0, 0.0)
        mates.sort(key=lambda q: dist(nxt.get(q.id, q.pos), c_next))
        if mates:
            deny = unit(sub(nxt.get(mates[0].id, mates[0].pos), c_next))
        side = unit(add(unit(sub(near.pos, c_next)), deny, 0.35))
        if self.offense:  # stay between the ball and the goal
            side = unit(add(unit(sub(GOAL, c_next)), side, 0.5))
        nxt[near.id] = self.steer(near, add(c_next, side, 1.5), V_RUN)
        rest = [d for d in defence if d is not near]
        k = min(len(rest), len(mates))
        marks = mates[:k]  # the most dangerous players get covered; the rest are left open
        spots = []
        for m in marks:
            m_next = nxt.get(m.id, m.pos)
            d_m = dist(m_next, c_next)
            if self.offense:  # goal side of the player they cover
                spots.append(add(m_next, unit(sub(GOAL, m_next)), 2.2))
            else:
                spots.append(add(m_next, unit(sub(c_next, m_next)), min(max(0.35 * d_m, 2.2), 3.6)))
        assigned: dict[str, tuple[float, float]] = {}
        if k:
            best = min(
                itertools.permutations(range(len(rest)), k),
                key=lambda perm: sum(dist(rest[i].pos, spots[j]) for j, i in enumerate(perm)),
            )
            for j, i in enumerate(best):
                sway = 0.5 * math.sin(1.3 * t + j)
                toward = unit(sub(c_next, spots[j]))
                perp = (-toward[1], toward[0])
                assigned[rest[i].id] = clamp_zone(add(spots[j], perp, sway))
        # a defender with nobody to cover helps the one on the ball
        for n, d in enumerate(x for x in rest if x.id not in assigned):
            ang = (1 if n % 2 == 0 else -1) * math.pi / 2
            v = unit(sub(near.pos, c_next))
            v = (
                v[0] * math.cos(ang) - v[1] * math.sin(ang),
                v[0] * math.sin(ang) + v[1] * math.cos(ang),
            )
            if self.offense:
                v = add(unit(sub(GOAL, c_next)), v, 0.8)
                v = unit(v)
            assigned[d.id] = clamp_zone(add(c_next, v, 3.6))
        for d in rest:
            nxt[d.id] = self.steer(d, assigned[d.id], V_RUN)

    def chase_loose(self, t, nxt):
        spot = self.loose_spot
        in_play = self.playing()
        for i, p in enumerate(sorted(in_play, key=lambda q: dist(q.pos, spot))):
            ang = i * 2.1
            target = add(spot, (math.cos(ang), math.sin(ang)), 1.6 + 0.4 * i)
            if i == 0 and self.nb_phase == "rolling":  # the closest player scoops it up
                target = (spot[0] - POCKET[0], spot[1] - POCKET[1])
            nxt[p.id] = self.steer(p, clamp_zone(target), V_RUN)

    def goalie_target(self):
        """The goalie steps out along the line from the goal to the ball."""
        if self.carrier is not None:
            ball = pocket_of(self.carrier.pos)
        elif self.loose_spot is not None:
            ball = self.loose_spot
        else:
            ball = (GOAL[0], GOAL[1] + 8.0)
        v = unit(sub(ball, GOAL))
        v = (v[0], max(v[1], 0.55))
        return add(GOAL, unit(v), GOALIE_HOME)

    def try_shot(self, t, carrier, defence):
        """A player with a shot on net takes it. The round says how it ends."""
        shots = self.spec.get("shots", [])
        if self.shot_i >= len(shots) or t < self.shot_ready:
            return None
        d = dist(carrier.pos, GOAL)
        if not SHOT_MIN <= d <= SHOT_MAX:
            return None
        outcome, after = shots[self.shot_i]
        start = pocket_of(carrier.pos)
        side = 1 if carrier.pos[0] >= GOAL[0] else -1  # the side the shooter is on
        if outcome == "goal":
            aim = (GOAL[0] - side * 0.8, GOAL[1] - 0.7)  # far corner, into the net
        elif outcome == "save":
            aim = add(self.g_pos, (side * 0.3, -0.2), 1.0)
        else:  # wide: the ball skips past the post and rolls behind the net
            aim = (GOAL[0] + side * 7.0, 7.8)
        lane = min((seg_dist(q.pos, start, aim) for q in defence), default=9.0)
        if lane < 1.0:
            return None
        tau = max(0.4, dist(start, aim) / 22.0)
        self.shot_i += 1
        self.last_passer = carrier
        self.carrier = None
        who = "Red" if carrier.team == "a" else "Blue"
        keys = []
        if outcome == "goal":
            rest = (aim[0], aim[1] - 0.5)
            keys = [(t + tau, aim[0], aim[1], 0), (t + tau + 0.3, rest[0], rest[1], 1)]
            dive = add(GOAL, (side * 1.5, GOALIE_HOME - 0.2))
            self.caption(t, f"{who} has a shot and takes it: goal! The goalie went the other way.")
        elif outcome == "save":
            rest = (self.g_pos[0] + side * 0.4, self.g_pos[1] + 1.0)
            keys = [(t + tau, aim[0], aim[1], 0), (t + tau + 0.4, rest[0], rest[1], 1)]
            dive = add(GOAL, (side * 0.9, GOALIE_HOME))
            self.caption(t, f"{who} has a shot and takes it: the goalie makes the save.")
        else:
            rest = (aim[0] + side * 0.6, aim[1] - 0.4)
            keys = [(t + tau, aim[0], aim[1], 1), (t + tau + 0.5, rest[0], rest[1], 1)]
            dive = add(GOAL, (side * 0.8, GOALIE_HOME))
            self.caption(t, f"{who} has a shot and takes it, but it goes wide and rolls behind.")
        self.g_dive = [(t + tau, dive[0], dive[1]), (t + DT, dive[0], dive[1])]
        end = keys[-1][0]
        self.stop_play(t, end, rest, after)
        return keys

    def stop_play(self, t, end, rest, after):
        """After a shot play stops: a new ball, a new ball and a release, or a reset."""
        self.nb_out = rest
        if after == "reset":
            self.nb_phase = "reset"
            self.reset_t = end + 1.6
            self.say(self.reset_t, 1.6, "coach", "Reset!")
            self.caption(
                self.reset_t, 'The coach calls "Reset!" and everyone goes back to the lines.'
            )
        else:
            self.nb_phase = "out"
            self.nb_roll_t = end + 2.0
            self.nb_release = after == "new_ball_release"

    def start_reset(self):
        """Everyone playing walks back to the end of their line."""
        for team in ("a", "b"):
            back = [p for p in self.playing(team)]
            back.sort(key=lambda q: q.pos[1], reverse=(team == "b"))
            for k, p in enumerate(back):
                self.reset_targets[p.id] = slot_pos(team, len(self.queues[team]) + k)
        self.nb_phase = "resetting"

    def send_out_of_bounds(self, t, carrier, defence):
        """A pass sails out of bounds on the east side, near the coach in the field."""
        start = pocket_of(carrier.pos)
        y = min(max(carrier.pos[1], 22.0), 48.0)
        if abs(y - self.c_nxt[1]) < 2.5:
            y += 3.0 if y < 40 else -3.0
        out = (EAST + 1.0, y)
        length = dist(start, out)
        lane = min((seg_dist(d.pos, start, out) for d in defence), default=9.0)
        if length > 14.0 or lane < 1.8:
            return None
        tau = max(0.5, length / 15.0)
        self.nb_phase = "out"
        self.nb_out = out
        self.nb_roll_t = t + 3.0
        self.carrier = None
        self.last_passer = carrier
        self.caption(t, "The pass sails out of bounds. Play stops while a coach gets a new ball.")
        return [(t + tau, out[0], out[1], 1)]

    def roll_new_ball(self, t):
        """The coach in the field rolls a new ball in, about 9 yards along the field."""
        coach = self.c_nxt
        players = self.playing()
        best, best_score = None, -1e9
        for k in range(9):
            y = coach[1] + (k - 4) * 1.5
            spot = clamp_zone((coach[0] - 9.0, y), 0.5)
            score = min((dist(spot, q.pos) for q in players), default=9.0)
            if score > best_score:
                best, best_score = spot, score
        self.loose_spot = best
        self.nb_phase = "rolling"
        self.nb_land = t + 1.6
        start = (coach[0] - 0.9, coach[1] + 0.2)
        self.pending += [
            (t - 0.05, self.nb_out[0], self.nb_out[1], 1),
            (t, start[0], start[1], 0),
            (self.nb_land, best[0], best[1], 1),
        ]
        self.say(t, 1.6, "coach2", "New ball!")
        if self.nb_release:
            self.do_release(t)
            self.nb_release = False
            self.caption(
                t,
                'A coach throws in a new ball ("New ball!") and the coach at the cone calls '
                f'"Release!": the next player from each team joins. Now {self.odds_text()}. '
                "Everyone goes for the ball.",
            )
        else:
            self.caption(
                t, 'A coach in the field throws in a new ball: "New ball!" Everyone goes for it.'
            )

    def scoop(self, player, t, nxt):
        self.carrier = player
        self.nb_phase = None if self.offense else "done"
        self.hold = 0
        self.last_passer = None
        self.shot_ready = t + 3.0
        self.pending.append((t + DT,) + self.ball_xy_at(nxt[player.id]) + (0,))
        who = "Red" if player.team == "a" else "Blue"
        if self.offense:
            self.caption(t + 1.0, f"{who} scoops it up and is on offense.")
        else:
            self.caption(t + 1.0, f"{who} scoops it up and keep-away goes on.")

    # ---- the ball: passes, the turnover, the drop ---------------------------------------
    def ball_events(self, t, carrier, nxt):
        spec = self.spec
        keys = []
        in_play = self.playing()
        defence = [p for p in in_play if p.team != carrier.team]
        offence = [p for p in in_play if p.team == carrier.team and p is not carrier]
        self.hold += 1
        turn = spec.get("turnover")
        if turn and not self.turned and t >= turn and self.on_ball is not None:
            d = self.on_ball
            if dist(self.pos_at(d, nxt, 0.6), self.pos_at(carrier, nxt, 0.6)) < 2.6:
                tau = 0.6
                at = self.pos_at(d, nxt, tau)
                keys.append((t + tau,) + self.ball_xy_at(at) + (0,))
                self.turned = True
                self.last_passer = carrier
                self.carrier = d
                self.hold = 0
                loser = "Red" if carrier.team == "a" else "Blue"
                winner = "Blue" if carrier.team == "a" else "Red"
                self.caption(
                    t,
                    f"{winner} pokes the ball away and takes it. {winner} now keeps it away "
                    f"from {loser}.",
                )
                return keys
        if self.offense:
            shot = self.try_shot(t, carrier, defence)
            if shot:
                return shot
        out_at = spec.get("new_ball_at")
        if out_at is not None and t >= out_at and self.nb_phase is None and offence:
            keys_out = self.send_out_of_bounds(t, carrier, defence)
            if keys_out:
                return keys_out
        drop = spec.get("drop_at")
        if drop is not None and t >= drop and not self.dropped and offence:
            self.dropped = True
            receiver = max(
                offence, key=lambda q: min((dist(q.pos, d.pos) for d in defence), default=9)
            )
            tau = min(1.0, max(0.5, dist(carrier.pos, receiver.pos) / 15.0))
            at = self.pos_at(receiver, nxt, tau)
            far = self.loose_target(at, defence + offence)
            keys.append(
                (t + tau * 0.6,) + self.ball_xy_at(self.pos_at(receiver, nxt, tau * 0.6)) + (0,)
            )
            keys.append((t + tau + 0.5, far[0], far[1], 1))
            self.loose_spot = far
            self.carrier = None
            self.caption(t, "The pass is dropped. The ball is loose.")
            return keys
        want = 2 if len(in_play) <= 4 else spec.get("hold", 3)
        if self.hold >= want and offence and t >= self.arrives - 1e-9:
            choice = self.pick_receiver(t, carrier, offence, defence, nxt)
            if choice and t + choice[1] <= self.spec.get("count_start", 1e9) + 5.0 - 0.05:
                receiver, tau = choice
                at = self.pos_at(receiver, nxt, tau)
                keys.append((t + tau,) + self.ball_xy_at(at) + (0,))
                self.last_passer = carrier
                self.carrier = receiver
                self.pass_times.append(round(t, 1))
                self.arrives = t + tau
                self.hold = 0
        return keys

    def ball_xy_at(self, pos):
        q = pocket_of(pos)
        return (q[0], q[1])

    def loose_target(self, near, people):
        best, best_score = near, -1e9
        for k in range(16):
            ang = k * math.pi / 8
            c = clamp_zone((near[0] + 4.8 * math.cos(ang), near[1] + 4.8 * math.sin(ang)), 0.5)
            score = min(dist(c, q.pos) for q in people)
            if score > best_score:
                best, best_score = c, score
        return best

    def pick_receiver(self, t, carrier, offence, defence, nxt):
        # Prefer a clearly open teammate; if nobody is, settle for a smaller window (a real pass).
        for lane_min, open_min in ((1.9, 2.4), (1.5, 1.9), (1.2, 1.5)):
            choice = self.best_receiver(carrier, offence, defence, nxt, lane_min, open_min)
            if choice:
                return choice
        return None

    def best_receiver(self, carrier, offence, defence, nxt, lane_min, open_min):
        best, best_score = None, -1e9
        for r in offence:
            d0 = dist(carrier.pos, r.pos)
            tau = min(1.0, max(0.45, d0 / 15.0))
            at = self.pos_at(r, nxt, tau)
            start = self.pos_at(carrier, nxt, 0.0)
            length = dist(pocket_of(start), pocket_of(at))
            if not MIN_FLIGHT <= length <= MAX_FLIGHT:
                continue
            lane = min(
                (
                    seg_dist(self.pos_at(d, nxt, tau / 2), pocket_of(start), pocket_of(at))
                    for d in defence
                ),
                default=9.0,
            )
            open_d = min((dist(at, self.pos_at(d, nxt, tau)) for d in defence), default=9.0)
            if lane < lane_min or open_d < open_min:
                continue
            score = (
                lane + open_d - (1.5 if r is self.last_passer else 0.0) + self.rng.uniform(0, 0.8)
            )
            if self.offense:  # pass toward the goal
                score += 0.25 * (dist(carrier.pos, GOAL) - dist(at, GOAL))
            if score > best_score:
                best, best_score = (r, tau), score
        return best

    # ---- keeping people apart ----------------------------------------------------------
    def separate(self, nxt):
        everyone = [p for p in self.players.values() if p.id in nxt]
        for _ in range(12):
            moved = False
            for a, b in itertools.combinations(everyone, 2):
                need = self.same_min() if a.team == b.team else OPP_MIN
                d = dist(nxt[a.id], nxt[b.id])
                if d < need - 1e-6:
                    moved = True
                    v = unit(sub(nxt[a.id], nxt[b.id])) if d > 1e-6 else (1.0, 0.0)
                    push = (need - d) / 2
                    wa = 0.0 if self.is_waiting(a) else 1.0
                    wb = 0.0 if self.is_waiting(b) else 1.0
                    if wa + wb == 0:
                        continue
                    share = push * 2 / (wa + wb)
                    nxt[a.id] = add(nxt[a.id], v, share * wa)
                    nxt[b.id] = add(nxt[b.id], v, -share * wb)
            for p in everyone:
                if self.is_waiting(p):
                    continue
                d = dist(nxt[p.id], self.c_nxt)
                if d < COACH_MIN:
                    nxt[p.id] = add(self.c_nxt, unit(sub(nxt[p.id], self.c_nxt)), COACH_MIN)
                    moved = True
                nxt[p.id] = (
                    clamp_zone(nxt[p.id])
                    if p.playing and self.nb_phase != "resetting"
                    else nxt[p.id]
                )
                # nobody is faster than a player can be
                step = dist(p.pos, nxt[p.id])
                if step > V_CAP * DT:
                    nxt[p.id] = add(p.pos, unit(sub(nxt[p.id], p.pos)), V_CAP * DT)
            if not moved:
                break

    def same_min(self):
        # people walking back into line stand as close as the line spaces them
        return 2.3 if self.nb_phase == "resetting" else SAME_MIN

    def is_waiting(self, p):
        return not p.playing

    def check_between(self, nxt):
        """Make sure nobody's straight-line path passes too close to someone else's."""
        people = [p for p in self.players.values() if p.id in nxt]
        for attempt in range(14):
            bad = []
            for a, b in itertools.combinations(people, 2):
                need = (self.same_min() if a.team == b.team else OPP_MIN) * ENDS_FACTOR
                if min_gap(a.pos, nxt[a.id], b.pos, nxt[b.id]) < need:
                    bad.append((a, b))
            for q in people:
                if self.is_waiting(q):
                    continue
                gap = min_gap(self.c_cur, self.c_nxt, q.pos, nxt[q.id])
                if gap < COACH_MIN * ENDS_FACTOR:
                    # swing the end of the path to the side of the coach the player started on
                    run = sub(nxt[q.id], q.pos)
                    side = unit((-run[1], run[0]))
                    to_coach = sub(self.c_nxt, q.pos)
                    if side[0] * to_coach[0] + side[1] * to_coach[1] > 0:
                        side = (-side[0], -side[1])
                    nxt[q.id] = add(nxt[q.id], side, COACH_MIN * ENDS_FACTOR - gap + 0.5)
                    bad.append((q, q))
            if not bad:
                return
            for a, b in bad:
                if a is b:
                    continue
                rel = sub(nxt[a.id], nxt[b.id])
                side = unit((-rel[1], rel[0]))
                if attempt < 8:
                    # slide them apart sideways
                    if not self.is_waiting(a):
                        nxt[a.id] = add(nxt[a.id], side, 0.6)
                    if not self.is_waiting(b):
                        nxt[b.id] = add(nxt[b.id], side, -0.6)
                else:
                    # still crossing: both take a shorter step
                    for q in (a, b):
                        if not self.is_waiting(q):
                            nxt[q.id] = lerp(q.pos, nxt[q.id], 0.6)
            self.separate(nxt)

    # ---- the clock -----------------------------------------------------------------------
    def do_release(self, t, with_whistle=True):
        """The next player from each line joins; the coach at the cone calls it."""
        for team in ("a", "b"):
            if self.queues[team]:
                pid = self.queues[team].pop(0)
                self.players[pid].playing = True
        if with_whistle:
            self.say(t, 1.6, "coach", "Release!")

    def handle_events(self, t):
        spec = self.spec
        for i, when in enumerate(spec.get("releases", [])):
            if self.released > i or t + 1e-9 < when:
                continue
            self.released = i + 1
            self.do_release(t)
            self.caption(
                t,
                "The coach blows the whistle once: release! The next player from each team joins.",
            )
            self.caption(
                t + 1.2,
                f"Now {self.odds_text()}. Same job: one defender on the ball, the others "
                "cover the open players.",
            )
        count = spec.get("count_start")
        if count is not None and not self.counting and t + 1e-9 >= count:
            self.counting = True
            for i, n in enumerate(range(5, 0, -1)):
                self.caption(count + i, f"The coach counts down: {n}")
                self.say(count + i, 0.9, "coach", f"{n}")

    def finish_step(self, ball_keys):
        # a pass still in the air when this step starts supersedes the carry key for this step
        for key in ball_keys:
            if not self.ball or key[0] > self.ball[-1][0] + 1e-9:
                self.ball.append(key)

    def run(self):
        self.released = 0
        self.counting = False
        self.turned = False
        self.dropped = False
        self.loose_spot = None
        self.opening()
        if self.offense:
            return self.run_offense()
        end = self.spec["count_start"] + 5.0
        while self.t < end - 1e-9:
            self.step()
        # time: everyone holds
        end_t = self.t
        carrier = self.carrier
        if carrier:
            self.ball.append((end_t,) + self.ball_xy(carrier) + (0,))
            who = "Red" if carrier.team == "a" else "Blue"
            self.caption(
                end_t,
                f"Time! {who} has the ball, so {who.lower()} wins the round. "
                "The coach calls reset.",
            )
        else:
            self.ball.append((end_t, self.loose_spot[0], self.loose_spot[1], 1))
            self.caption(
                end_t, "Time! Nobody has the ball, so nobody wins the round. The coach calls reset."
            )
        self.say(end_t, 1.6, "coach", "Reset!")
        hold_t = end_t + 1.5
        for p in self.players.values():
            if p.playing:
                p.keys.append((hold_t, p.pos[0], p.pos[1]))
        self.ball.append((hold_t,) + tuple(self.ball[-1][1:]))
        self.duration = hold_t
        self.validate()
        return self.export()

    def run_offense(self):
        name = self.spec["id"]
        while not self.finished and self.t < 160:
            self.step()
        if not self.finished:
            raise SystemExit(f"{name}: the round never reached the reset")
        hold_t = self.t + 1.5
        for pid, goal in self.reset_targets.items():
            self.players[pid].keys.append((hold_t, goal[0], goal[1]))
        for p in self.players.values():
            if not p.keys or p.keys[-1][0] < hold_t:
                p.keys.append((hold_t, p.pos[0], p.pos[1]))
        self.ball.append((hold_t,) + tuple(self.ball[-1][1:]))
        self.g_keys.append((hold_t, self.g_pos[0], self.g_pos[1]))
        self.coach_keys.append((hold_t, self.c_nxt[0], self.c_nxt[1]))
        self.duration = hold_t
        self.validate()
        return self.export()

    # ---- checks and output -------------------------------------------------------------
    def interp(self, p, t):
        return self.interp_keys(p.keys, t)

    @staticmethod
    def interp_keys(keys, t):
        if t <= keys[0][0]:
            return (keys[0][1], keys[0][2])
        for a, b in zip(keys, keys[1:], strict=False):
            if a[0] <= t <= b[0]:
                u = 0 if b[0] == a[0] else (t - a[0]) / (b[0] - a[0])
                return lerp((a[1], a[2]), (b[1], b[2]), u)
        return (keys[-1][1], keys[-1][2])

    def validate(self):
        name = self.spec["id"]
        steps = int(self.duration / 0.1)
        for n in range(steps + 1):
            t = n * 0.1
            pos = {pid: self.interp(p, t) for pid, p in self.players.items()}
            for a, b in itertools.combinations(self.players.values(), 2):
                need = (SAME_MIN if a.team == b.team else OPP_MIN) * 0.72
                if dist(pos[a.id], pos[b.id]) < need:
                    raise SystemExit(
                        f"{name}: {a.id} and {b.id} too close at {t:.1f}s "
                        f"({dist(pos[a.id], pos[b.id]):.2f})"
                    )
            coach_now = self.interp_keys(self.coach_keys, t)
            if self.offense:
                for pid, q in pos.items():
                    if dist(q, GOAL) < GOAL_KEEP * 0.8:
                        raise SystemExit(f"{name}: {pid} is in the crease at {t:.1f}s")
            for pid, q in pos.items():
                if self.players[pid].playing and dist(q, coach_now) < COACH_MIN * 0.7:
                    raise SystemExit(f"{name}: {pid} too close to the coach at {t:.1f}s")
        for p in self.players.values():
            for a, b in zip(p.keys, p.keys[1:], strict=False):
                dt = b[0] - a[0]
                if dt > 0 and math.hypot(b[1] - a[1], b[2] - a[2]) / dt > V_CAP + 0.4:
                    raise SystemExit(f"{name}: {p.id} too fast near {a[0]:.1f}s")

    def export(self):
        def keys(seq):
            out: list[list] = []
            for item in seq:
                row = [r2(item[0]), r2(item[1]), r2(item[2])]
                if len(item) > 3 and item[3]:
                    row.append(1)
                if out and out[-1][0] == row[0]:
                    out[-1] = row  # two keys at the same time: keep the later one
                elif len(out) >= 2 and out[-1][1:] == row[1:] and out[-2][1:] == row[1:]:
                    out[-1] = row  # standing still: keep only the first and last key
                else:
                    out.append(row)
            return out

        actors = [
            {"id": "coach", "kind": "coach", "team": "none", "keys": [[0, COACH[0], COACH[1]]]},
            {"id": "coach2", "kind": "coach", "team": "none", "keys": keys(self.coach_keys)},
            {
                "id": "cone",
                "kind": "cone",
                "team": "none",
                "color": "orange",
                "keys": [[0, CONE[0], CONE[1]]],
            },
        ]
        for pid in [f"s{i}" for i in range(1, 6)] + [f"n{i}" for i in range(1, 6)]:
            p = self.players[pid]
            actors.append({"id": pid, "kind": "player", "team": p.team, "keys": keys(p.keys)})
        if self.offense:
            actors.append(
                {"id": "goalie", "kind": "goalie", "team": "none", "keys": keys(self.g_keys)}
            )
        actors.append({"id": "ball", "kind": "ball", "team": "none", "keys": keys(self.ball)})
        caps = sorted(self.captions, key=lambda c: c[0])
        return {
            "id": self.spec["id"],
            "name": self.spec["name"],
            "summary": self.spec["summary"],
            "duration": r2(self.duration),
            "actors": actors,
            "captions": [[t, text] for t, text in caps],
            "speech": [list(item) for item in sorted(self.speech)],
        }


ROUNDS = [
    {
        "id": "standard",
        "name": "Standard round: red keeps the ball",
        "summary": (
            "Red wins the ground ball and keeps it away through three releases, up to 5 on 4. "
            "Blue defends a player down. The coach counts down and the team with the ball wins."
        ),
        "seeds": [3, 5, 11, 15, 19],
        "hold": 2,
        "gb_winner": "S",
        "releases": [12.9, 22.9, 31.9],
        "count_start": 40.9,
    },
    {
        "id": "blue-wins-ground-ball",
        "hold": 2,
        "name": "Blue wins the ground ball",
        "summary": (
            "Blue, the team with fewer players, wins the ground ball and has to keep it away from "
            "two, then three, then four red defenders."
        ),
        "seeds": [8, 42, 93, 125, 98],
        "gb_winner": "N",
        "releases": [12.9, 23.9, 32.9],
        "count_start": 41.9,
    },
    {
        "id": "blue-takes-it-away",
        "hold": 2,
        "name": "Blue takes the ball away",
        "summary": (
            "Red wins the ground ball, but blue pokes it away and takes it. Now blue keeps it "
            "away and wins the round."
        ),
        "seeds": [23, 20, 41, 21, 32],
        "gb_winner": "S",
        "turnover": 16.9,
        "releases": [11.9, 24.9, 33.9],
        "count_start": 41.9,
    },
    {
        "id": "loose-at-the-count",
        "name": "Loose ball at the count: no winner",
        "summary": (
            "Red keeps the ball until a pass is dropped during the countdown. Nobody has the ball "
            "at the end, so nobody wins."
        ),
        "seeds": [21, 22, 7, 8, 19],
        "gb_winner": "S",
        "releases": [12.9, 22.9, 31.9],
        "drop_at": 43.9,
        "count_start": 40.9,
    },
    {
        "id": "new-ball",
        "name": "Out of bounds: a new ball",
        "summary": (
            "A pass sails out of bounds. Play stops, a coach throws in a new ball, everyone fights "
            "for it, and keep-away goes on through the releases."
        ),
        "seeds": [1, 26, 48, 15, 8],
        "hold": 2,
        "gb_winner": "S",
        "releases": [12.9, 29.9, 37.9],
        "new_ball_at": 18.9,
        "count_start": 44.9,
    },
]


# Odd man, offense/defense. Like keep-away, but whoever has the ball is on offense and shoots when
# there is a shot. `shots` lists what happens to each shot ("goal", "save" or "wide") and what the
# coaches do next ("new_ball", "new_ball_release" or "reset").
ODD_ROUNDS = [
    {
        "id": "standard",
        "name": "Standard round: a goal, a new ball, then a save and a reset",
        "summary": (
            "Red wins the ground ball and attacks the net two on one. The shooter scores, a coach "
            "throws in a new ball, they go again, the goalie makes a save and the coach resets."
        ),
        "mode": "offense",
        "seeds": [7, 4, 12, 17, 9],
        "gb_winner": "S",
        "shot_after": 5.0,
        "shots": [("goal", "new_ball"), ("save", "reset")],
    },
    {
        "id": "goal-reset",
        "name": "A goal, then reset",
        "summary": (
            "Red wins the ground ball and scores. The coach calls reset and everyone goes back to "
            "the lines."
        ),
        "mode": "offense",
        "seeds": [2, 5, 6, 7, 8],
        "gb_winner": "S",
        "shot_after": 5.0,
        "shots": [("goal", "reset")],
    },
    {
        "id": "goal-new-ball-release",
        "name": "A goal, then a new ball and a release",
        "summary": (
            "After the goal a coach throws in a new ball and the coach at the cone releases the "
            "next player from each line, so it is three on two. Next shot goes wide, then reset."
        ),
        "mode": "offense",
        "seeds": [2, 15, 17, 13, 9],
        "gb_winner": "S",
        "shot_after": 5.0,
        "shots": [("goal", "new_ball_release"), ("wide", "reset")],
    },
    {
        "id": "man-down-offense",
        "name": "The man down team gets the ball",
        "summary": (
            "Blue, a player down, wins the ground ball. Blue is on offense now, with no take "
            "back. The shot is saved, a new ball goes in, and the next one scores."
        ),
        "mode": "offense",
        "seeds": [8, 10, 6, 12, 9],
        "gb_winner": "N",
        "shot_after": 5.0,
        "shots": [("save", "new_ball"), ("goal", "reset")],
    },
]


def format_take(seed, r, pad):
    """One take as JavaScript object text. Used inline and in the take files."""
    lines = [f"{pad}{{", f"{pad}  seed: {seed},", f"{pad}  duration: {r['duration']},"]
    lines.append(f"{pad}  actors: [")
    for a in r["actors"]:
        meta = {k: v for k, v in a.items() if k != "keys"}
        lines.append(
            f"{pad}    {{ ..."
            + json.dumps(meta)
            + ", keys: "
            + json.dumps(a["keys"], separators=(",", ":"))
            + " },"
        )
    lines.append(f"{pad}  ],")
    lines.append(f"{pad}  captions: " + json.dumps(r["captions"], ensure_ascii=False) + ",")
    lines.append(f"{pad}  speech: " + json.dumps(r["speech"], ensure_ascii=False) + ",")
    lines.append(f"{pad}}}")
    return lines


def render_file(const, rounds, intro, drill_id):
    """The data module (the first take of every version, plus the list of seeds) and the take
    files (every other seed), which the page loads only when someone picks that seed."""
    lines = [
        "// Generated by scripts/choreography.py. Do not edit by hand: change that script",
        "// and run `make choreography`. Each round (version) has several takes, one per seed",
        "// (the first is the default and is here; the others are loaded from takes/ when picked).",
        "// Each key is [time, x, y]; a ball key ending in 1 means the ball is on the ground.",
        f"// {intro}",
        f"export const {const} = [",
    ]
    files: dict[Path, str] = {}
    for spec in rounds:
        takes = [Round(dict(spec, seed=seed)).run() for seed in spec["seeds"]]
        lines.append("  {")
        for key in ("id", "name", "summary"):
            lines.append(f"    {key}: {json.dumps(takes[0][key])},")
        lines.append(f"    seeds: {json.dumps(spec['seeds'])},")
        lines.append("    takes: [")
        first = format_take(spec["seeds"][0], takes[0], "      ")
        first[-1] += ","
        lines += first
        lines.append("    ],")
        lines.append("  },")
        for seed, r in list(zip(spec["seeds"], takes, strict=True))[1:]:
            body = format_take(seed, r, "")
            key = json.dumps(f"{drill_id}/{spec['id']}/{seed}")
            text = (
                "// Generated by scripts/choreography.py. Do not edit by hand.\n"
                f"(window.LAX_TAKES = window.LAX_TAKES || {{}})[{key}] =\n"
                + "\n".join(body)
                + ";\n"
            )
            files[TAKES_DIR / drill_id / f"{spec['id']}-{seed}.js"] = text
    lines.append("];")
    return "\n".join(lines) + "\n", files


OUTPUTS = [
    (OUT, "KEEP_AWAY_VARIANTS", ROUNDS, "Keep away.", "keep-away"),
    (OUT_ODD, "ODD_MAN_VARIANTS", ODD_ROUNDS, "Odd man, offense/defense.", "odd-man"),
]


def main() -> int:
    modules: dict[Path, str] = {}
    files: dict[Path, str] = {}
    for path, const, rounds, intro, drill_id in OUTPUTS:
        text, takes = render_file(const, rounds, intro, drill_id)
        modules[path] = text
        files.update(takes)
    expected = {**modules, **files}
    existing = {p for p in TAKES_DIR.rglob("*.js")} if TAKES_DIR.is_dir() else set()
    if "--check" in sys.argv[1:]:
        stale = [p for p, text in expected.items() if not p.is_file() or p.read_text() != text]
        stale += sorted(existing - set(files))  # take files nothing generates any more
        if stale:
            names = ", ".join(str(p.relative_to(ROOT)) for p in stale[:6])
            print(f"out of date: {names}; run `make choreography` and commit the result")
            return 1
        print("keepaway_data.js, oddman_data.js and src/takes/ are up to date")
        return 0
    for path in existing - set(files):
        path.unlink()
    for path, text in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    for path in modules:
        print(f"wrote {path.relative_to(ROOT)} ({len(modules[path]) // 1024} KiB)")
    size = sum(len(t) for t in files.values()) // 1024
    print(f"wrote {len(files)} take files to src/takes/ ({size} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
