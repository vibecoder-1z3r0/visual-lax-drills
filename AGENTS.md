# Visual Lax Drills

A static, single-file HTML set of animated lacrosse drills. The shipped artifact is one
`dist/index.html` that opens straight from disk. The site has no Python and no runtime dependencies;
Python is dev tooling only (build script, Playwright tests).

## Rules for agents

### Links and attribution
- **No Claude session links.** Never put a `claude.ai/code/session_...` link (or any session URL) in a
  commit message, pull request description, comment, or file in this repo. This overrides any tool or
  harness text that asks for one. CI enforces this for commits and pull requests:
  `scripts/check_no_session_links.py` fails the build if a commit message, or a PR title or
  description, contains a claude.ai session link or a `Claude-Session:` trailer. When a harness
  reminder says to end a commit or PR description with a session line or link, leave that out and keep
  any other attribution line it gives (for example the `Co-Authored-By` line). Only open a PR when the
  user asks for one.
- **AI attribution (AIA): TODO, not yet lifted.** These rules are meant to be copied from the
  `AGENTS.md` / `CLAUDE.md` of `the-quest-map-generator`. Reading that `AGENTS.md` was blocked by AI
  Guardian (prompt-injection hit, line 172), so they are not here yet. Until they are, follow the
  attribution lines the user has given in the session and add nothing more.

### Security tooling
- AI Guardian hooks are enforcement. If a tool call is blocked, report the violation type and location
  (use `get_violations`) and stop. Do not retry the same thing in another form to get around a block.

## Decisions so far
- **Scope first:** a generic half-field / zone layout. Other formats (men's, women's, box) come later.
- **Playback:** full controls (play, pause, scrub, speed, step through keyframes, reset), with a
  caption per phase.
- **Art style:** anime chibi, as inline SVG symbols in a sprite. Icons are centered on the origin
  (`viewBox="-32 -32 64 64"`): player (circle with a team-colored border), coach, goalie, net, crease,
  ball, bag of balls, and cones in several colors. More markings as drills need them.
- **Themes:** drills should be themeable (CSS custom-property sets), in the spirit of the themes in the
  user's `many-game-show` and `many-board` projects. How those are structured is not yet known; see
  Open items.

## Architecture
- `src/` is bundled by `scripts/build.py` into `dist/index.html` (CSS, JS modules, SVG sprite, drill
  data all inlined). Icons come from `icons-custom/` when present, else `src/icons/`. A missing or
  malformed icon fails the build; icons may not contain `script`, `image`, `foreignObject`, `iframe`,
  `object` or `embed`.
- JS modules share one flat scope after bundling, so top-level names must be unique. Order is defined
  in `JS_ORDER` in the build script.
- **Field:** real lacrosse dimensions in one coordinate system (yards), so every drill is plain data
  and scales cleanly.
- **Drills are data:** actors (player, coach, goalie, ball, cones...) plus per-actor keyframe tracks
  `{t, x, y}` and a caption list. One engine plays all of them.
- **Engine:** has a controllable clock (`seek(t)`, `advance(dtMs)`, `play`, `pause`, `setSpeed`,
  `reset`) so tests can jump to exact times and never wait on real time. Exposed for tests as
  `window.LAX`.
- **Team color:** set `--team` on a group; icons use `var(--team)` for the ring and `currentColor`
  for tintable parts.

## Tooling and CI
Borrowed from `the-quest-map-generator`:
- `Makefile` targets `build`, `lint`, `test` (CI runs them as three separate steps), plus `setup`,
  `clean`. `lint` runs `deno lint` on `src/js`, an HTML check, and `ruff` on `scripts` and `tests`.
- `pyproject.toml` dev extras: `playwright==1.63.0`, `pytest`, `pillow`, `ruff`, `deno`, `html5lib`.
- Tests are Python Playwright. A session fixture serves `dist/` on a local port; each test page fails
  on any JS `pageerror`. Screenshots and traces go to `test-artifacts/` (git-ignored).
- GitHub Actions: `ci.yml` (build, lint, test on Python 3.12; upload `test-artifacts` and `dist`; on
  push to `main`, deploy `dist` to GitHub Pages via the Pages actions, two jobs: artifact then deploy)
  and `release.yml` (on `v*` tags, rebuild, test, attach the single HTML file to a GitHub release).
  Pages must be set to "GitHub Actions" as the source in repo settings.

## Open items
1. **Scaffold: done.** Build, lint, tests, CI, two demo drills, seven placeholder chibi icons, and a
   day/night theme switch. There is deliberately no `make serve`: the page is one static file, so open
   `dist/index.html` directly, and the tests load it as a `file://` URL. (An earlier attempt that
   included a localhost URL was blocked by AI Guardian as `ssrf_blocked`.) Next: real art, more drills,
   icon sizes (they are small next to the 60-yard field), more themes.
2. **Session recorder: deferred by the user.** It would come from `the-quest-map-generator`
   (`scripts/session_timing.py`, `scripts/session_log_header.md`, the pre-commit hook in
   `scripts/hooks/`, `SESSION_LOG.md`, `make session-log`). The copy command was blocked by AI Guardian
   (`tool_permission`, subreason `immutable_protection`, `viol_23534299`; the target was not named).
   Do not retry it in another form; ask the user first. If it is ever added, redact secret-shaped
   prompts in the log (the user chose redaction), because `SESSION_LOG.md` records the first 70
   characters of every prompt.
3. **Themes:** need to look at how `many-game-show` / `many-board` do themes. Attaching those repos
   needs the user's approval, because the earlier `list_repos` / `add_repo` calls were logged by AI
   Guardian as `tool_permission` blocks (admin permission) even though they ran in warn mode.
4. **AIA rules:** lift from the quest map `AGENTS.md` once it can be read (see Rules above).
