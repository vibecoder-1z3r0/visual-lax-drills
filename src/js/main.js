import { ICON_SIZE } from "./constants.js";
import { DRILLS } from "./drills.js";
import { resolveDrill, trackAt } from "./engine.js";
import { loadEveryTake, loadTake } from "./takes.js";
import { app, initUi } from "./ui.js";

initUi();

// Test hook: lets the test suite drive the engine and read the data inside the real built page.
window.LAX = {
  app,
  DRILLS,
  trackAt,
  ICON_SIZE,
  resolveDrill,
  loadTake,
  loadEveryTake: () => loadEveryTake(DRILLS),
};
