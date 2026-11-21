import {
  CREASE_R,
  DRAW_ORDER,
  FIELD_H,
  FIELD_W,
  GOAL_X,
  GOAL_Y,
  ICON_SIZE,
  MARGIN,
} from "./constants.js";

const SVG_NS = "http://www.w3.org/2000/svg";

function svgEl(parent, name, attrs) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, String(value));
  if (parent) parent.appendChild(node);
  return node;
}

function iconUse(parent, kind, scale = 1) {
  const size = ICON_SIZE[kind] * scale;
  return svgEl(parent, "use", {
    href: `#icon-${kind}`,
    x: -size / 2,
    y: -size / 2,
    width: size,
    height: size,
  });
}

// The part of the field a drill shows, as an SVG viewBox. A drill zooms in with
// `view: { x, y, w, h }` (yards); without one the whole field and its margin show.
export function viewBoxFor(drill) {
  const v = drill && drill.view;
  if (v) return `${v.x} ${v.y} ${v.w} ${v.h}`;
  return `${-MARGIN} ${-MARGIN} ${FIELD_W + 2 * MARGIN} ${FIELD_H + 2 * MARGIN}`;
}

// Draws the static half field and returns the empty group the actors are drawn into.
export function buildField(svg) {
  svg.replaceChildren();
  svg.setAttribute("viewBox", viewBoxFor(null));
  svgEl(svg, "rect", {
    class: "field-surround",
    x: -MARGIN,
    y: -MARGIN,
    width: FIELD_W + 2 * MARGIN,
    height: FIELD_H + 2 * MARGIN,
  });
  const stripes = 11;
  for (let i = 0; i < stripes; i++) {
    svgEl(svg, "rect", {
      class: i % 2 ? "field-grass-b" : "field-grass-a",
      x: 0,
      y: (i * FIELD_H) / stripes,
      width: FIELD_W,
      height: FIELD_H / stripes + 0.01,
    });
  }
  svgEl(svg, "rect", { class: "field-line", x: 0, y: 0, width: FIELD_W, height: FIELD_H });
  // The goal (crease and net) is one group so a drill can hide it with `goal: false`.
  const goal = svgEl(svg, "g", { id: "goal" });
  svgEl(goal, "circle", { class: "crease", cx: GOAL_X, cy: GOAL_Y, r: CREASE_R });
  // The net sits on the goal line with its open front facing the field.
  const netY = GOAL_Y - (18 / 64) * ICON_SIZE.net;
  const net = svgEl(goal, "g", { transform: `translate(${GOAL_X} ${netY})` });
  iconUse(net, "net");
  const label = svgEl(svg, "text", {
    id: "midfield-label",
    class: "field-label",
    x: FIELD_W / 2,
    y: FIELD_H + 2,
  });
  label.textContent = "toward midfield";
  svgEl(svg, "g", { id: "markings" });
  const actors = svgEl(svg, "g", { id: "actors" });
  svgEl(svg, "g", { id: "speech" }); // speech bubbles, drawn over the actors
  return actors;
}

// Extra lines and labels a drill draws on the field (yards): { type: "line", x1, y1, x2, y2, dash },
// { type: "rect", x, y, w, h } or { type: "text", x, y, text }.
export function renderMarkings(group, markings) {
  group.replaceChildren();
  for (const m of markings || []) {
    if (m.type === "line") {
      svgEl(group, "line", {
        class: m.dash ? "mark-line mark-dash" : "mark-line",
        x1: m.x1,
        y1: m.y1,
        x2: m.x2,
        y2: m.y2,
      });
    } else if (m.type === "rect") {
      svgEl(group, "rect", { class: "mark-line", x: m.x, y: m.y, width: m.w, height: m.h });
    } else if (m.type === "text") {
      svgEl(group, "text", { class: "mark-text", x: m.x, y: m.y }).textContent = m.text;
    }
  }
}

// Creates one group per actor and returns them keyed by actor id.
export function buildActors(layer, drill) {
  const order = (actor) => DRAW_ORDER.indexOf(actor.kind);
  const sorted = [...drill.actors].sort((a, b) => order(a) - order(b));
  const groups = {};
  for (const actor of sorted) {
    const classes = ["actor", `kind-${actor.kind}`, `team-${actor.team}`];
    if (actor.color) classes.push(`cone-${actor.color}`);
    const g = svgEl(layer, "g", { class: classes.join(" "), "data-actor": actor.id });
    iconUse(g, actor.kind, drill.iconScale || 1);
    groups[actor.id] = g;
  }
  return groups;
}

export function placeActors(groups, positions) {
  for (const [id, pos] of Object.entries(positions)) {
    groups[id].setAttribute("transform", `translate(${pos.x.toFixed(3)} ${pos.y.toFixed(3)})`);
  }
}

// Speech bubbles. One bubble per speaker (an actor id that has `speech` items); it is empty and
// hidden until `placeSpeech` finds something being said.
export function buildSpeech(layer, drill) {
  layer.replaceChildren();
  const bubbles = {};
  const speakers = new Set((drill.speech || []).map((s) => s.who));
  for (const who of speakers) {
    const g = svgEl(layer, "g", { class: "speech", "data-speaker": who, visibility: "hidden" });
    const box = svgEl(g, "path", { class: "speech-box" });
    const text = svgEl(g, "text", { class: "speech-text" });
    bubbles[who] = { g, box, text };
  }
  return bubbles;
}

const SPEECH_FONT = 1.5; // yards, like everything on the field
const SPEECH_PAD = 0.55;
const SPEECH_TAIL = 0.7;

// Puts each bubble above its speaker, keeps it inside the drill's view, and hides the quiet ones.
export function placeSpeech(bubbles, said, positions, drill) {
  const view = drill.view || { x: 0, y: 0, w: FIELD_W, h: FIELD_H };
  for (const [who, bubble] of Object.entries(bubbles)) {
    const item = said.find((s) => s.who === who);
    const at = positions[who];
    if (!item || !at) {
      bubble.g.setAttribute("visibility", "hidden");
      continue;
    }
    const actor = drill.actors.find((a) => a.id === who);
    const lift = ((ICON_SIZE[actor.kind] || 1.8) * (drill.iconScale || 1)) / 2 + 0.2;
    bubble.text.textContent = item.text;
    const w = item.text.length * SPEECH_FONT * 0.6 + 2 * SPEECH_PAD;
    const h = SPEECH_FONT + 2 * SPEECH_PAD;
    // Centre the bubble over the speaker, but nudge it back into view.
    const left = Math.min(Math.max(at.x - w / 2, view.x + 0.3), view.x + view.w - w - 0.3);
    const top = at.y - lift - SPEECH_TAIL - h;
    const tipX = Math.min(Math.max(at.x, left + 0.9), left + w - 0.9);
    const r = 0.7;
    bubble.box.setAttribute(
      "d",
      `M${left + r} ${top} H${left + w - r} Q${left + w} ${top} ${left + w} ${top + r} ` +
        `V${top + h - r} Q${left + w} ${top + h} ${left + w - r} ${top + h} ` +
        `H${tipX + 0.5} L${tipX} ${top + h + SPEECH_TAIL} L${tipX - 0.5} ${top + h} ` +
        `H${left + r} Q${left} ${top + h} ${left} ${top + h - r} V${top + r} ` +
        `Q${left} ${top} ${left + r} ${top} Z`,
    );
    bubble.text.setAttribute("x", String(left + w / 2));
    bubble.text.setAttribute("y", String(top + h / 2));
    bubble.g.setAttribute("visibility", "visible");
  }
}
