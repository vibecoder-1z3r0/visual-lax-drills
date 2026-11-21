// The drill playback engine. It never touches the DOM. Time is in seconds and only moves when
// `advance` is called (by the animation loop while playing, or directly by tests).

// Position of one actor at time t. `keys` is sorted by t: [{t, x, y, ease?}]. Between two keys the
// actor moves in a straight line; `ease: true` on the later key smooths that leg.
export function trackAt(keys, t) {
  const first = keys[0];
  const last = keys[keys.length - 1];
  if (t <= first.t) return { x: first.x, y: first.y };
  if (t >= last.t) return { x: last.x, y: last.y };
  let i = 1;
  while (keys[i].t < t) i++;
  const a = keys[i - 1];
  const b = keys[i];
  let u = (t - a.t) / (b.t - a.t);
  if (b.ease) u = u * u * (3 - 2 * u);
  return { x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u };
}

// What the characters are saying at time t: the drill's `speech` items { t, dur, who, text } whose
// time span includes t. `who` is an actor id; the page draws a speech bubble above that actor.
export function speechAt(speech, t) {
  return (speech || []).filter((s) => s.t <= t && t < s.t + s.dur);
}

// A drill can have several choreographed versions ("variants"); the first is the default. Each
// variant gives its own actors, captions and duration (and optionally its own summary); everything
// else (title, view, flags, markings) comes from the drill. Returns a plain drill the engine can play.
export function resolveDrill(drill, variantIndex = 0) {
  if (!drill.variants) return drill;
  const variant = drill.variants[variantIndex] || drill.variants[0];
  return {
    ...drill,
    actors: variant.actors,
    captions: variant.captions,
    speech: variant.speech,
    duration: variant.duration,
    summary: variant.summary || drill.summary,
    variantId: variant.id,
    variantName: variant.name,
  };
}

// The caption text in effect at time t: the last caption whose start time has passed.
export function captionAt(captions, t) {
  let text = "";
  for (const c of captions) if (c.t <= t) text = c.text;
  return text;
}

export function createEngine(drill) {
  const listeners = [];
  let frame = 0;
  let lastStamp = 0;

  const engine = {
    drill,
    t: 0,
    speed: 1,
    playing: false,
    onChange(fn) {
      listeners.push(fn);
    },
    emit() {
      for (const fn of listeners) fn(engine);
    },
    positions() {
      const out = {};
      for (const actor of drill.actors) out[actor.id] = trackAt(actor.keys, engine.t);
      return out;
    },
    caption() {
      return captionAt(drill.captions, engine.t);
    },
    speech() {
      return speechAt(drill.speech, engine.t);
    },
    seek(t) {
      engine.t = Math.min(Math.max(t, 0), drill.duration);
      engine.emit();
    },
    // Move time forward by `ms` milliseconds of real time, scaled by the speed.
    advance(ms) {
      const next = engine.t + (ms / 1000) * engine.speed;
      if (next >= drill.duration) {
        engine.t = drill.duration;
        engine.playing = false;
        stopLoop();
      } else {
        engine.t = Math.max(0, next);
      }
      engine.emit();
    },
    play() {
      if (engine.t >= drill.duration) engine.t = 0;
      engine.playing = true;
      lastStamp = 0;
      stopLoop();
      frame = requestAnimationFrame(loop);
      engine.emit();
    },
    pause() {
      engine.playing = false;
      stopLoop();
      engine.emit();
    },
    toggle() {
      if (engine.playing) engine.pause();
      else engine.play();
    },
    setSpeed(speed) {
      engine.speed = speed;
      engine.emit();
    },
    reset() {
      engine.pause();
      engine.seek(0);
    },
  };

  function stopLoop() {
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
  }

  function loop(stamp) {
    frame = 0;
    if (!engine.playing) return;
    if (lastStamp) engine.advance(Math.min(stamp - lastStamp, 100));
    lastStamp = stamp;
    if (engine.playing) frame = requestAnimationFrame(loop);
  }

  return engine;
}
