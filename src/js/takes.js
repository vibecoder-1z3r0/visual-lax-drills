import { expandTake } from "./drills.js";

// Takes other than a version's default are separate files in takes/ next to index.html. Each one is
// a script that registers itself in window.LAX_TAKES. A script tag (unlike fetch) also works when the
// page is opened straight from disk. Loaded takes are kept in the version's `takes` list.
const pending = new Map();

export function takeIsLoaded(variant, takeIndex) {
  return Boolean(variant.takes[takeIndex]);
}

export function loadTake(drill, variantIndex, takeIndex) {
  const variant = drill.variants[variantIndex];
  if (takeIsLoaded(variant, takeIndex)) return Promise.resolve(variant.takes[takeIndex]);
  const seed = variant.seeds[takeIndex];
  const key = `${drill.id}/${variant.id}/${seed}`;
  if (pending.has(key)) return pending.get(key);
  const promise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `takes/${drill.id}/${variant.id}-${seed}.js`;
    script.onload = () => {
      const raw = window.LAX_TAKES && window.LAX_TAKES[key];
      script.remove();
      if (!raw) return reject(new Error(`take ${key} did not register itself`));
      variant.takes[takeIndex] = expandTake(raw);
      resolve(variant.takes[takeIndex]);
    };
    script.onerror = () => {
      script.remove();
      reject(new Error(`could not load ${script.src}`));
    };
    document.head.appendChild(script);
  }).finally(() => pending.delete(key));
  pending.set(key, promise);
  return promise;
}

// Test hook: load every take of every drill (a few dozen small files).
export async function loadEveryTake(drills) {
  for (const drill of drills) {
    for (let v = 0; v < (drill.variants || []).length; v++) {
      for (let t = 0; t < drill.variants[v].seeds.length; t++) await loadTake(drill, v, t);
    }
  }
}
