#!/usr/bin/env python3
"""Choreographs the keep-away drill and writes src/js/keepaway_data.js.

    python3 scripts/keepaway_choreography.py          # rewrite the data module
    python3 scripts/keepaway_choreography.py --check  # exit 1 if the committed file is out of date

Keep-away is not scripted by hand: it is played out by a small simulation, one step a second.
The team with the ball spreads out and moves to get open, passes to whoever is open with a clear
lane, and the other team, always a player down, has one defender on the ball and the rest cover the
most dangerous players. The generator then checks the result: players stay clear of each other and
the coaches, nobody runs faster than a player really can, everyone stays in bounds, and passes only
go through a defender where the round says so (a turnover). The output is plain data, like every
other drill, and a test checks it matches what this script produces.

Rounds ("variants") are listed in ROUNDS at the bottom. The first is the default. A new drill can
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

# ---- the field and the people --------------------------------------------------------------
WEST, EAST, NORTH, SOUTH = 15.0, 45.0, 5.0, 55.0
LINE_Y = 35.0
CONE = (15.2, LINE_Y)
COACH = (13.3, LINE_Y)
COACH2 = (37.5, 40.0)
BALL_START = (14.5, 35.5)
BALL_SPOT = (24.0, 36.2)  # where the coach's roll stops, about 9 yards from the cone

ICON_SCALE = 1.35
ICON = 1.8 * ICON_SCALE  # the width of a player icon, in yards
POCKET = (0.375 * ICON, -0.25 * ICON)  # where the stick's pocket is, from the player's centre
QUEUE_X = 15.9
SLOT = 2.5  # spacing of players waiting in line
FIRST = 2.8  # the front player's distance from the cone
ZONE = (17.8, 43.2, 24.0, 48.0)  # x0, x1, y0, y1: where the play happens
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


def clamp_zone(p, margin=0.0):
    return (
        min(max(p[0], ZONE[0] + margin), ZONE[1] - margin),
        min(max(p[1], ZONE[2] + margin), ZONE[3] - margin),
    )


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
        self.rng = random.Random(spec["seed"])
        self.players = {}
        for i in range(5):
            self.players[f"s{i + 1}"] = Player(f"s{i + 1}", "a", i)
            self.players[f"n{i + 1}"] = Player(f"n{i + 1}", "b", i)
        self.ball: list[tuple] = []
        self.captions: list[tuple[float, str]] = []
        self.carrier: Player | None = None
        self.on_ball: Player | None = None
        self.t = 0.0
        self.hold = 0
        self.pass_times = []
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
        self.caption(0.6, "The coach rolls a ball out, about 9 yards along the 20-yard line.")
        self.caption(
            1.0, "Two red players and one blue player, the ones closest to the cone, go for it."
        )
        self.caption(2.3, "They fight for the ground ball.")
        color = "Red" if win == "S" else "Blue"
        self.caption(2.9, f"{color} scoops it. Keep-away starts: {self.odds_text()}.")

    def odds_text(self):
        s, n = len(self.playing("a")), len(self.playing("b"))
        return f"{s} red against {n} blue, so blue is a player down"

    # ---- one simulation step --------------------------------------------------------------
    def step(self):
        t = self.t
        self.handle_events(t)
        in_play = self.playing()
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

        if loose:
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

        # what happens to the ball during this step
        ball_keys = [(t,) + self.ball_xy(carrier) + (0,)] if carrier else []
        if carrier and not loose:
            ball_keys += self.ball_events(t, carrier, nxt)
        for pid, pos in nxt.items():
            p = self.players[pid]
            p.pos = pos
            self.key(p, t + DT)
        self.t = t + DT
        self.finish_step(ball_keys)

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
            score -= 1.2 * max(0.0, 3.0 - dist(c, COACH2))
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
        nxt[near.id] = self.steer(near, add(c_next, side, 1.5), V_RUN)
        rest = [d for d in defence if d is not near]
        k = min(len(rest), len(mates))
        marks = mates[:k]  # the most dangerous players get covered; the rest are left open
        spots = []
        for m in marks:
            m_next = nxt.get(m.id, m.pos)
            d_m = dist(m_next, c_next)
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
            assigned[d.id] = clamp_zone(add(c_next, v, 3.6))
        for d in rest:
            nxt[d.id] = self.steer(d, assigned[d.id], V_RUN)

    def chase_loose(self, t, nxt):
        spot = self.loose_spot
        in_play = self.playing()
        for i, p in enumerate(sorted(in_play, key=lambda q: dist(q.pos, spot))):
            ang = i * 2.1
            target = add(spot, (math.cos(ang), math.sin(ang)), 1.6 + 0.4 * i)
            nxt[p.id] = self.steer(p, clamp_zone(target), V_RUN)

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
            if choice and t + choice[1] <= self.spec["count_start"] + 5.0 - 0.05:
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
            if score > best_score:
                best, best_score = (r, tau), score
        return best

    # ---- keeping people apart ----------------------------------------------------------
    def separate(self, nxt):
        everyone = [p for p in self.players.values() if p.id in nxt]
        for _ in range(12):
            moved = False
            for a, b in itertools.combinations(everyone, 2):
                need = SAME_MIN if a.team == b.team else OPP_MIN
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
                d = dist(nxt[p.id], COACH2)
                if d < COACH_MIN:
                    nxt[p.id] = add(COACH2, unit(sub(nxt[p.id], COACH2)), COACH_MIN)
                    moved = True
                nxt[p.id] = clamp_zone(nxt[p.id]) if p.playing else nxt[p.id]
                # nobody is faster than a player can be
                step = dist(p.pos, nxt[p.id])
                if step > V_CAP * DT:
                    nxt[p.id] = add(p.pos, unit(sub(nxt[p.id], p.pos)), V_CAP * DT)
            if not moved:
                break

    def is_waiting(self, p):
        return not p.playing

    def check_between(self, nxt):
        """Make sure nobody's straight-line path passes too close to someone else's."""
        people = [p for p in self.players.values() if p.id in nxt]
        for attempt in range(14):
            bad = []
            for a, b in itertools.combinations(people, 2):
                need = (SAME_MIN if a.team == b.team else OPP_MIN) * ENDS_FACTOR
                if min_gap(a.pos, nxt[a.id], b.pos, nxt[b.id]) < need:
                    bad.append((a, b))
            for q in people:
                if self.is_waiting(q):
                    continue
                gap = seg_dist(COACH2, q.pos, nxt[q.id])
                if gap < COACH_MIN * ENDS_FACTOR:
                    # swing the end of the path to the side of the coach the player started on
                    run = sub(nxt[q.id], q.pos)
                    side = unit((-run[1], run[0]))
                    to_coach = sub(COACH2, q.pos)
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
    def handle_events(self, t):
        spec = self.spec
        for i, when in enumerate(spec["releases"]):
            if self.released > i or t + 1e-9 < when:
                continue
            self.released = i + 1
            joiners = []
            for team in ("a", "b"):
                if self.queues[team]:
                    pid = self.queues[team].pop(0)
                    self.players[pid].playing = True
                    joiners.append(pid)
            self.caption(
                t,
                "The coach blows the whistle once: release! The next player from each team joins.",
            )
            self.caption(
                t + 1.2,
                f"Now {self.odds_text()}. Same job: one defender on the ball, the others "
                "cover the open players.",
            )
        count = spec["count_start"]
        if not self.counting and t + 1e-9 >= count:
            self.counting = True
            for i, n in enumerate(range(5, 0, -1)):
                self.caption(count + i, f"The coach counts down: {n}")

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
        hold_t = end_t + 1.5
        for p in self.players.values():
            if p.playing:
                p.keys.append((hold_t, p.pos[0], p.pos[1]))
        self.ball.append((hold_t,) + tuple(self.ball[-1][1:]))
        self.duration = hold_t
        self.validate()
        return self.export()

    # ---- checks and output -------------------------------------------------------------
    def interp(self, p, t):
        keys = p.keys
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
            for pid, q in pos.items():
                if self.players[pid].playing and dist(q, COACH2) < COACH_MIN * 0.7:
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
            {"id": "coach2", "kind": "coach", "team": "none", "keys": [[0, COACH2[0], COACH2[1]]]},
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
        actors.append({"id": "ball", "kind": "ball", "team": "none", "keys": keys(self.ball)})
        caps = sorted(self.captions, key=lambda c: c[0])
        return {
            "id": self.spec["id"],
            "name": self.spec["name"],
            "summary": self.spec["summary"],
            "duration": r2(self.duration),
            "actors": actors,
            "captions": [[t, text] for t, text in caps],
        }


ROUNDS = [
    {
        "id": "standard",
        "name": "Standard round: red keeps the ball",
        "summary": (
            "Red wins the ground ball and keeps it away through three releases, up to 5 on 4. "
            "Blue defends a player down. The coach counts down and the team with the ball wins."
        ),
        "seed": 7,
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
        "seed": 1,
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
        "seed": 37,
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
        "seed": 51,
        "gb_winner": "S",
        "releases": [12.9, 22.9, 31.9],
        "drop_at": 43.9,
        "count_start": 40.9,
    },
]


def render() -> str:
    rounds = [Round(spec).run() for spec in ROUNDS]
    lines = [
        "// Generated by scripts/keepaway_choreography.py. Do not edit by hand: change that script",
        "// and run `make choreography`. Each key is [time, x, y]; a ball key ending in 1 means",
        "// the ball is on the ground.",
        "export const KEEP_AWAY_VARIANTS = [",
    ]
    for r in rounds:
        lines.append("  {")
        for key in ("id", "name", "summary"):
            lines.append(f"    {key}: {json.dumps(r[key])},")
        lines.append(f"    duration: {r['duration']},")
        lines.append("    actors: [")
        for a in r["actors"]:
            meta = {k: v for k, v in a.items() if k != "keys"}
            lines.append(
                "      { ..."
                + json.dumps(meta)
                + ", keys: "
                + json.dumps(a["keys"], separators=(",", ":"))
                + " },"
            )
        lines.append("    ],")
        lines.append("    captions: " + json.dumps(r["captions"], ensure_ascii=False) + ",")
        lines.append("  },")
    lines.append("];")
    return "\n".join(lines) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv[1:]:
        if not OUT.is_file() or OUT.read_text() != text:
            print("src/js/keepaway_data.js is out of date; run `make choreography` and commit it")
            return 1
        print("keepaway_data.js is up to date")
        return 0
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(text) // 1024} KiB, {len(ROUNDS)} rounds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
