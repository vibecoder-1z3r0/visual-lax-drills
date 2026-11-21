# Visual Lax Drills

Animated lacrosse drills in a single static HTML file, drawn with anime chibi style icons (players,
goalies, coaches, nets, balls, cones). Pick a drill, then play, pause, scrub, change the speed, or
switch themes.

Open `dist/index.html` in a browser after building. There is no server and no runtime dependency.

## Develop

```bash
make setup   # one time: virtualenv, dev tools, Playwright's Chromium
make build   # src/ -> dist/index.html
make lint    # deno lint, HTML check, ruff
make test    # Playwright (Python) tests against dist/index.html
```

Tests write screenshots to `test-artifacts/`. Add a drill by adding data to `src/js/drills.js`; add
or replace art by editing `src/icons/` (or dropping files in `icons-custom/`, which is git-ignored).
See `AGENTS.md` for the plan and the rules for agents working in this repo.
