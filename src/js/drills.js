import { KEEP_AWAY_VARIANTS } from "./keepaway_data.js";

// Drills are plain data. Coordinates are field yards (see constants.js). Every actor has a list of
// keyframes {t, x, y}; an actor with a single key stands still. `team` picks the ring color
// (a, b, or none), `color` picks a cone color. `goal: false` hides the goal and crease, and
// `midfieldLabel: false` hides the "toward midfield" label under the field, and `view: {x, y, w, h}`
// (yards) zooms in on part of the field. `iconScale` makes the actors bigger or smaller (the goal
// stays real size); a drill that can only zoom a little uses a larger one so its icons stay readable.
const k = (t, x, y) => ({ t, x, y });

// Keep-away's rounds are generated (scripts/keepaway_choreography.py) as [time, x, y] rows, and a
// ball row ending in 1 means the ball is on the ground. Turn them into keyframes.
const toKeys = (rows) =>
  rows.map(([t, x, y, loose]) => (loose ? { t, x, y, loose: true } : { t, x, y }));

export const DRILLS = [
  {
    id: "ground-ball-mania",
    title: "Ground ball mania",
    view: { x: 20.5, y: 19.4, w: 28, h: 26 },
    goal: false,
    midfieldLabel: false,
    summary: "The coach stands beside the cone and rolls balls out one at a time. Each player runs out from the line, scoops one, rolls it back to the coach and rejoins the line.",
    duration: 21.2,
    actors: [
      { id: "coach", kind: "coach", team: "none", keys: [k(0, 32.3, 35.4)] },
      { id: "bag", kind: "ballbag", team: "none", keys: [k(0, 34.3, 36.2)] },
      { id: "cone", kind: "cone", team: "none", color: "orange", keys: [k(0, 30, 35.4)] },
      { id: "p1", kind: "player", team: "a", keys: [k(0, 30, 38), k(1.0, 30, 38), k(1.8, 30, 33.5), k(3.4, 31.0, 26.5), k(4.8, 37.5, 30.5), k(5.7, 37.5, 35.9), k(6.39, 37.5, 39.9), k(8.19, 30, 39.9), k(8.6, 30, 39.9), k(9.3, 30, 38), k(10.6, 30, 38), k(11.4, 30, 33.5), k(13.0, 31.0, 26.5), k(14.4, 37.5, 30.5), k(15.3, 37.5, 35.9), k(16.32, 37.5, 41.8), k(18.12, 30, 41.8)] },
      { id: "p2", kind: "player", team: "a", keys: [k(0, 30, 39.9), k(1.4, 30, 39.9), k(2.1, 30, 38), k(3.4, 30, 38), k(4.2, 30, 33.5), k(5.8, 31.7, 26.4), k(7.2, 37.5, 30.4), k(8.1, 37.5, 35.9), k(8.79, 37.5, 39.9), k(10.59, 30, 39.9), k(11.0, 30, 39.9), k(11.7, 30, 38), k(13.0, 30, 38), k(13.8, 30, 33.5), k(15.4, 31.7, 26.4), k(16.8, 37.5, 30.4), k(17.7, 37.5, 35.9), k(19.04, 37.5, 43.7), k(20.84, 30, 43.7)] },
      { id: "p3", kind: "player", team: "a", keys: [k(0, 30, 41.8), k(1.4, 30, 41.8), k(2.1, 30, 39.9), k(3.8, 30, 39.9), k(4.5, 30, 38), k(5.8, 30, 38), k(6.6, 30, 33.5), k(8.2, 30.6, 26.6), k(9.6, 37.5, 30.6), k(10.5, 37.5, 35.9), k(11.19, 37.5, 39.9), k(12.99, 30, 39.9), k(13.4, 30, 39.9), k(14.1, 30, 38)] },
      { id: "p4", kind: "player", team: "a", keys: [k(0, 30, 43.7), k(1.4, 30, 43.7), k(2.1, 30, 41.8), k(3.8, 30, 41.8), k(4.5, 30, 39.9), k(6.2, 30, 39.9), k(6.9, 30, 38), k(8.2, 30, 38), k(9.0, 30, 33.5), k(10.6, 31.4, 26.4), k(12.0, 37.5, 30.4), k(12.9, 37.5, 35.9), k(13.59, 37.5, 39.9), k(15.39, 30, 39.9)] },
      { id: "ball", kind: "ball", team: "none", keys: [k(0, 33.3, 36.4), k(0.9, 33.3, 36.4), k(2.1, 31.68, 26.05), k(3.4, 31.68, 26.05), k(4.8, 38.17, 30.05), k(5.7, 38.17, 35.45), k(6.2, 33.3, 36.4), k(10.5, 33.3, 36.4), k(11.7, 31.68, 26.05), k(13.0, 31.68, 26.05), k(14.4, 38.17, 30.05), k(15.3, 38.17, 35.45), k(15.8, 33.3, 36.4)] },
      { id: "ball2", kind: "ball", team: "none", keys: [k(0, 33.3, 36.4), k(3.3, 33.3, 36.4), k(4.5, 32.38, 25.95), k(5.8, 32.38, 25.95), k(7.2, 38.17, 29.95), k(8.1, 38.17, 35.45), k(8.6, 33.3, 36.4), k(12.9, 33.3, 36.4), k(14.1, 32.38, 25.95), k(15.4, 32.38, 25.95), k(16.8, 38.17, 29.95), k(17.7, 38.17, 35.45), k(18.2, 33.3, 36.4)] },
      { id: "ball3", kind: "ball", team: "none", keys: [k(0, 33.3, 36.4), k(5.7, 33.3, 36.4), k(6.9, 31.28, 26.15), k(8.2, 31.28, 26.15), k(9.6, 38.17, 30.15), k(10.5, 38.17, 35.45), k(11.0, 33.3, 36.4)] },
      { id: "ball4", kind: "ball", team: "none", keys: [k(0, 33.3, 36.4), k(8.1, 33.3, 36.4), k(9.3, 32.07, 25.95), k(10.6, 32.07, 25.95), k(12.0, 38.17, 29.95), k(12.9, 38.17, 35.45), k(13.4, 33.3, 36.4)] },
    ],
    captions: [
      { t: 0, text: "Four players line up behind the cone. The coach stands right next to the cone with the balls." },
      { t: 0.6, text: "Coach rolls a ball up the field, about 9 yards out." },
      { t: 1.6, text: "The first player runs through the cone and attacks the ball." },
      { t: 3.4, text: "Scoop it on the move: get low, stick down, and don't stop." },
      { t: 3.9, text: "As the player scoops, the coach is already rolling the next ball out." },
      { t: 4.4, text: "Cradle the ball and swing around the outside of the coach." },
      { t: 5.6, text: "Roll it in when you are about level with the coach, still running." },
      { t: 6.8, text: "Keep going, down and around to the back of the line." },
      { t: 13, text: "Around again, everyone circling the same way. Field as many ground balls as you can." },
      { t: 19.5, text: "Six ground balls in about 21 seconds. Beat that next round." },
    ],
  },
  {
    id: "keep-away",
    title: "Keep away",
    summary:
      "Two teams start on the west sideline. A few players from each go for a rolled ball, then " +
      "play keep-away, with red always a player up on blue. The coach calls 'release' to add the " +
      "next player from each team, up to 5 on 4, then counts down. The team with the ball wins.",
    // A small field: the west sideline is 15 yards from the goal, the east boundary 15 yards on the
    // other side, and the 20-yard line is 20 yards out from the goal line.
    view: { x: 8, y: 12, w: 40, h: 38 },
    iconScale: 1.35,
    midfieldLabel: false,
    markings: [
      { type: "rect", x: 15, y: 5, w: 30, h: 50 },
      { type: "line", x1: 15, y1: 35, x2: 45, y2: 35, dash: true },
      { type: "text", x: 41.5, y: 34.1, text: "20-yard line" },
    ],
    variants: KEEP_AWAY_VARIANTS.map((v) => ({
      id: v.id,
      name: v.name,
      summary: v.summary,
      takes: v.takes.map((take) => ({
        seed: take.seed,
        duration: take.duration,
        actors: take.actors.map((a) => ({ ...a, keys: toKeys(a.keys) })),
        captions: take.captions.map(([t, text]) => ({ t, text })),
        speech: take.speech.map(([t, dur, who, text]) => ({ t, dur, who, text })),
      })),
    })),
  },
  {
    id: "two-man-shoot",
    title: "Two-man pass and shoot",
    view: { x: 9, y: 9, w: 44, h: 41 },
    iconScale: 1.45,
    summary: "Attackers swing the ball across the top, one cuts to the crease and finishes.",
    duration: 6,
    actors: [
      { id: "goalie", kind: "goalie", team: "b", keys: [k(0, 30, 17.5), k(4.5, 30, 17.5), k(5, 28.6, 17.5)] },
      { id: "coach", kind: "coach", team: "none", keys: [k(0, 52, 46)] },
      { id: "a1", kind: "player", team: "a", keys: [k(0, 14, 38), k(2, 14, 38), k(3.5, 22, 26)] },
      { id: "a2", kind: "player", team: "a", keys: [k(0, 46, 38)] },
      {
        id: "ball",
        kind: "ball",
        team: "none",
        keys: [k(0, 14.98, 37.35), k(1, 14.98, 37.35), k(2, 46.98, 37.35), k(3, 46.98, 37.35), k(3.8, 22.98, 25.35), k(4.5, 22.98, 25.35), k(5.2, 30, 15)],
      },
    ],
    captions: [
      { t: 0, text: "Attackers set up wide at the top of the box." },
      { t: 1, text: "A1 passes across to A2." },
      { t: 2, text: "A1 cuts hard toward the crease." },
      { t: 3, text: "A2 hits the cutter in stride." },
      { t: 4.5, text: "Catch and shoot before the goalie sets." },
      { t: 5.2, text: "Goal! Reset and rotate." },
    ],
  },
  {
    id: "cone-weave",
    title: "Cone weave and finish",
    view: { x: 8, y: 12, w: 44, h: 41 },
    iconScale: 1.45,
    summary: "Carry the ball through four cones, then shoot from the top of the crease.",
    duration: 7,
    actors: [
      { id: "goalie", kind: "goalie", team: "b", keys: [k(0, 30, 17.5), k(5.5, 30, 17.5), k(6, 28.6, 17.5)] },
      { id: "coach", kind: "coach", team: "none", keys: [k(0, 14, 44)] },
      { id: "c1", kind: "cone", team: "none", color: "orange", keys: [k(0, 30, 46)] },
      { id: "c2", kind: "cone", team: "none", color: "yellow", keys: [k(0, 30, 40)] },
      { id: "c3", kind: "cone", team: "none", color: "blue", keys: [k(0, 30, 34)] },
      { id: "c4", kind: "cone", team: "none", color: "pink", keys: [k(0, 30, 28)] },
      { id: "bag", kind: "ballbag", team: "none", keys: [k(0, 22, 52)] },
      {
        id: "p1",
        kind: "player",
        team: "a",
        keys: [k(0, 30, 52), k(1, 36, 46), k(2, 24, 40), k(3, 36, 34), k(4, 24, 28), k(5, 30, 22)],
      },
      {
        id: "ball",
        kind: "ball",
        team: "none",
        keys: [k(0, 30.98, 51.35), k(1, 36.98, 45.35), k(2, 24.98, 39.35), k(3, 36.98, 33.35), k(4, 24.98, 27.35), k(5, 30.98, 21.35), k(5.5, 30.98, 21.35), k(6.2, 30, 15)],
      },
    ],
    captions: [
      { t: 0, text: "Start behind the cones with the ball in your stick." },
      { t: 1, text: "Push past the first cone on the right." },
      { t: 2, text: "Cut left around the second cone." },
      { t: 3, text: "Back to the right for the third." },
      { t: 4, text: "Left around the fourth and head for the crease." },
      { t: 5.4, text: "Shoot!" },
      { t: 6.4, text: "Goal. Reset and go again." },
    ],
  },
  {
    id: "catch-and-throw",
    title: "Catch and throw",
    view: { x: 16, y: 28, w: 28, h: 26 },
    iconScale: 0.9,
    summary: "Two players stand twelve yards apart and pass the ball back and forth.",
    duration: 8,
    actors: [
      { id: "coach", kind: "coach", team: "none", keys: [k(0, 30, 46)] },
      { id: "a1", kind: "player", team: "a", keys: [k(0, 24, 38)] },
      { id: "a2", kind: "player", team: "a", keys: [k(0, 36, 38)] },
      {
        id: "ball",
        kind: "ball",
        team: "none",
        keys: [k(0, 24.61, 37.59), k(1, 24.61, 37.59), k(2, 36.61, 37.59), k(3, 36.61, 37.59), k(4, 24.61, 37.59), k(5, 24.61, 37.59), k(6, 36.61, 37.59), k(7, 36.61, 37.59), k(8, 36.61, 37.59)],
      },
    ],
    captions: [
      { t: 0, text: "Face your partner, stick up and ready, with the ball in A1's stick." },
      { t: 1, text: "A1 steps and throws to A2's stick." },
      { t: 2, text: "A2 catches and cradles." },
      { t: 3, text: "A2 throws it back." },
      { t: 4, text: "A1 catches. Soft hands: give with the ball." },
      { t: 5, text: "A1 throws again." },
      { t: 6, text: "A2 catches. Keep the stick up and the target out." },
      { t: 7, text: "Repeat, then switch to the other hand." },
    ],
  },
];
