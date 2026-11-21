import { SPEEDS, THEME_KEY, THEMES } from "./constants.js";
import { DRILLS } from "./drills.js";
import { createEngine, resolveDrill } from "./engine.js";
import { buildActors, buildField, placeActors, renderMarkings, viewBoxFor } from "./render.js";

export const app = { engine: null, drillIndex: 0, variantIndex: 0, layer: null, actors: null };

function $(id) {
  return document.getElementById(id);
}

function refresh(engine) {
  placeActors(app.actors, engine.positions());
  $("time").textContent = `${engine.t.toFixed(1)} / ${engine.drill.duration.toFixed(1)} s`;
  $("scrub").value = String(Math.round(engine.t * 100));
  $("caption").textContent = engine.caption();
  const atEnd = engine.t >= engine.drill.duration;
  $("play").textContent = engine.playing ? "Pause" : atEnd ? "Replay" : "Play";
  $("play").setAttribute("aria-pressed", String(engine.playing));
}

// Shows the "Version" menu only for a drill that has more than one choreographed version.
function showVersions(base, variantIndex) {
  const pick = $("variant-pick");
  const select = $("variant");
  select.replaceChildren();
  const variants = base.variants || [];
  pick.hidden = variants.length < 2;
  fillSelect(
    select,
    variants.map((v, i) => ({ value: String(i), label: v.name })),
    String(variantIndex),
  );
}

export function loadDrill(index, variantIndex = 0) {
  if (app.engine) app.engine.pause();
  app.drillIndex = index;
  app.variantIndex = variantIndex;
  const base = DRILLS[index];
  const drill = resolveDrill(base, variantIndex);
  showVersions(base, variantIndex);
  renderMarkings($("markings"), drill.markings);
  const engine = createEngine(drill);
  engine.speed = Number($("speed").value);
  engine.onChange(refresh);
  app.engine = engine;
  app.layer.replaceChildren();
  $("field").setAttribute("viewBox", viewBoxFor(drill));
  // A drill can hide the goal and crease (`goal: false`), e.g. when the field is just open space.
  const goal = document.getElementById("goal");
  if (goal) goal.style.display = drill.goal === false ? "none" : "";
  // Likewise the "toward midfield" label under the field (`midfieldLabel: false`).
  const label = document.getElementById("midfield-label");
  if (label) label.style.display = drill.midfieldLabel === false ? "none" : "";
  app.actors = buildActors(app.layer, drill);
  $("title").textContent = drill.title;
  $("summary").textContent = drill.summary;
  $("scrub").max = String(Math.round(drill.duration * 100));
  refresh(engine);
}

export function setTheme(id) {
  document.documentElement.setAttribute("data-theme", id);
  try {
    localStorage.setItem(THEME_KEY, id);
  } catch {
    // Storage can be blocked (private window, cleared site data); the theme still applies.
  }
}

function savedTheme() {
  try {
    const id = localStorage.getItem(THEME_KEY);
    return THEMES.some((t) => t.id === id) ? id : null;
  } catch {
    return null;
  }
}

function fillSelect(select, items, selected) {
  for (const item of items) {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    option.selected = item.value === selected;
    select.appendChild(option);
  }
}

export function initUi() {
  const svg = $("field");
  if (!svg) return false;
  app.layer = buildField(svg);

  const saved = savedTheme();
  if (saved) setTheme(saved);

  fillSelect(
    $("drill"),
    DRILLS.map((d, i) => ({ value: String(i), label: d.title })),
    "0",
  );
  fillSelect(
    $("speed"),
    SPEEDS.map((s) => ({ value: String(s), label: `${s}x` })),
    "1",
  );
  fillSelect(
    $("theme"),
    THEMES.map((t) => ({ value: t.id, label: t.name })),
    document.documentElement.getAttribute("data-theme"),
  );

  $("drill").addEventListener("change", (e) => loadDrill(Number(e.target.value)));
  $("variant").addEventListener("change", (e) =>
    loadDrill(app.drillIndex, Number(e.target.value)),
  );
  $("speed").addEventListener("change", (e) => app.engine.setSpeed(Number(e.target.value)));
  $("theme").addEventListener("change", (e) => setTheme(e.target.value));
  $("play").addEventListener("click", () => app.engine.toggle());
  $("reset").addEventListener("click", () => app.engine.reset());
  $("scrub").addEventListener("input", (e) => {
    // Read the slider before pausing: pausing refreshes the slider back to the old time.
    const t = Number(e.target.value) / 100;
    app.engine.pause();
    app.engine.seek(t);
  });
  document.addEventListener("keydown", (e) => {
    if (["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(e.target.tagName)) return;
    if (e.key === " ") {
      e.preventDefault();
      app.engine.toggle();
    } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      app.engine.pause();
      app.engine.seek(app.engine.t + (e.key === "ArrowRight" ? 0.25 : -0.25));
    }
  });

  loadDrill(0);
  return true;
}
