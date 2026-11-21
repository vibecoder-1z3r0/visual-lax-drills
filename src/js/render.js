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

function iconUse(parent, kind) {
  const size = ICON_SIZE[kind];
  return svgEl(parent, "use", {
    href: `#icon-${kind}`,
    x: -size / 2,
    y: -size / 2,
    width: size,
    height: size,
  });
}

// Draws the static half field and returns the empty group the actors are drawn into.
export function buildField(svg) {
  svg.replaceChildren();
  svg.setAttribute(
    "viewBox",
    `${-MARGIN} ${-MARGIN} ${FIELD_W + 2 * MARGIN} ${FIELD_H + 2 * MARGIN}`,
  );
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
  return svgEl(svg, "g", { id: "actors" });
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
    iconUse(g, actor.kind);
    groups[actor.id] = g;
  }
  return groups;
}

export function placeActors(groups, positions) {
  for (const [id, pos] of Object.entries(positions)) {
    groups[id].setAttribute("transform", `translate(${pos.x.toFixed(3)} ${pos.y.toFixed(3)})`);
  }
}
