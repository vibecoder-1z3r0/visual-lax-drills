import { SPEEDS, THEMES } from "./constants.js";
import { DRILLS } from "./drills.js";
import { createEngine } from "./engine.js";
import { buildActors, buildField, placeActors } from "./render.js";

export const app = { engine: null, drillIndex: 0, layer: null, actors: null };

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

export function loadDrill(index) {
  if (app.engine) app.engine.pause();
  app.drillIndex = index;
  const drill = DRILLS[index];
  const engine = createEngine(drill);
  engine.speed = Number($("speed").value);
  engine.onChange(refresh);
  app.engine = engine;
  app.layer.replaceChildren();
  app.actors = buildActors(app.layer, drill);
  $("title").textContent = drill.title;
  $("summary").textContent = drill.summary;
  $("scrub").max = String(Math.round(drill.duration * 100));
  refresh(engine);
}

export function setTheme(id) {
  document.documentElement.setAttribute("data-theme", id);
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
