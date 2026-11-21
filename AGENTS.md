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
- **AI attribution (AIA).** Every commit where Claude wrote or materially edited content ends its body
  with the AIA line, then the trailers (taken from the `many-game-show` project, which uses the same
  standard):

  ```
  AIA PAI SeCeNc Hin R Claude Code Web Sonnet 5.5 Medium v1.0

  Vibe-Coder: Vibe-Coder 1.z3r0 <243014891+vibecoder-1z3r0@users.noreply.github.com>
  Co-authored-by: Vibe-Coder 1.z3r0 <243014891+vibecoder-1z3r0@users.noreply.github.com>
  ```

  Segments: `PAI` primarily AI, `Se` stylistic edits, `Ce` content edits, `Nc` new content, `Hin`
  human-initiated, `R` reviewed by a human. Swap the interface, model or effort tier if a commit is made
  with a different one; keep the rest as issued. This is separate from the no-session-link rule above.
  Commits here also end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` (the harness
  adds it, and the quest map lists it too).
  For reference, the two projects this one borrows from word it differently. `many-game-show` uses the
  AIA line above plus the two human trailers (`AIA_ATTRIBUTION.md`, `CLAUDE.md`). `the-quest-map-generator`
  uses no AIA line: its commits end with the sentence "This work was substantially AI-generated with human
  review and direction throughout.", the two human trailers and the Claude `Co-Authored-By`. This repo
  follows `many-game-show` unless the user says otherwise. Both projects forbid session links in
  commits, PR text and files, use Conventional Commits, and do not open a PR unless asked.

### Screenshots
- The README shows screenshots from `docs/screenshots/`, made by `scripts/screenshots.py` (run
  `make screenshots`). A test fails when `src/` has changed since they were made, so after any change
  that can alter how the page looks (drills, icons, styles, layout, build script), run
  `make screenshots` and commit the images in the same commit. A new drill gets an entry in
  `DRILL_SHOTS` in that script (and a row in the README drills table).

### Security tooling
- AI Guardian hooks are enforcement. If a tool call is blocked, report the violation type and location
  (use `get_violations`) and stop. Do not retry the same thing in another form to get around a block.

## Decisions so far
- **Scope first:** a generic half-field / zone layout. Other formats (men's, women's, box) come later.
- **Drills so far:** ground ball mania (a line of four, one ball rolled out at a time, staggered; it is first in
  the list, so it is the default), two-man pass and shoot, cone weave, catch and throw. Tests and the
  screenshot script find drills by id, never by position, so the order can change.
- **Playback:** full controls (play, pause, scrub, speed, step through keyframes, reset), with a
  caption per phase.
- **Art style:** anime chibi, as inline SVG symbols in a sprite.  Players and the goalie hold a lacrosse stick (drawn inside the icon box at the right, so it is not clipped). Players and the goalie also wear a face cage (the player's is lighter than the goalie's so the eyes stay visible). The goalie's stick has a big, wide head; the coach has no stick but wears a whistle on a lanyard around the neck. A goalie takes its team's color (`team: "a"` red, `"b"` blue), so each side can have one. Cones come in orange, yellow, blue, pink, green, and two two-tone ones: `yellow-orange` (yellow with an orange band) and `orange-yellow` (orange with a yellow band). Icons are centered on the origin
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
  and scales cleanly. The stripes are 5 yards each. Icons are drawn about twice real size (player 1.8
  yards, ball 0.5; a real player is about 0.7 yards across) and each drill zooms in on its action with
  `view: { x, y, w, h }`; `iconScale` makes a drill's actors bigger when it can only zoom a little. Space
  players and set paths from real distances, not from icon size.
- **Drills are data:** actors (player, coach, goalie, ball, cones...) plus per-actor keyframe tracks
  `{t, x, y}` and a caption list. One engine plays all of them. A drill can set `goal: false` to hide the goal and crease and `midfieldLabel: false` to hide the "toward midfield" label (ground ball mania does both).
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
- Tests are Python Playwright. A session fixture serves `dist/` over HTTP from a throwaway local server
  (like GitHub Pages does); each test page fails on any JS `pageerror`. Serving over HTTP matters:
  over `file://` Chromium sometimes drops a `localStorage` write on a quick reload (about 6 in 100 under
  load), which made the theme test flaky. `tests/test_from_disk.py` still opens the page as `file://` to
  prove the single file works from disk. `make serve` serves `dist/` at http://127.0.0.1:8000 for a
  person. Screenshots and traces go to `test-artifacts/` (git-ignored).
- GitHub Actions: `ci.yml` (build, lint, test on Python 3.12; upload `test-artifacts` and `dist`; on
  push to `main`, deploy `dist` to GitHub Pages via the Pages actions, two jobs: artifact then deploy)
  and `release.yml` (on `v*` tags, rebuild, test, attach the single HTML file to a GitHub release).
  Pages must be set to "GitHub Actions" as the source in repo settings.

## Open items
1. **Scaffold: done.** Build, lint, tests, CI, drills, placeholder chibi icons and a theme switch. The
   page is one static file that opens straight from `dist/index.html`; `make serve` is there too, and the
   tests use an HTTP server (see Tooling). (An early attempt that included a localhost URL was blocked by
   AI Guardian as `ssrf_blocked`; it was off when `make serve` was added.) Next: real art, more drills.
2. **Session recorder: done.** `scripts/session_timing.py` (adapted from `many-game-show`) writes
   `session-logs/<session start, UTC>.md` from the session transcript under `~/.claude/projects/`:
   per-turn agent time, human think time and tokens. `make session-log` runs it; `make hooks` (part of
   `make setup`) sets `core.hooksPath` to `scripts/hooks`, whose `pre-commit` hook refreshes the log and
   adds it to each commit, and skips quietly where there is no transcript (CI). The log is public, so
   every prompt is cleaned (harness reminders dropped) and **redacted** (secret-shaped strings, emails,
   Claude session links) before its first 70 characters are kept; keep that redaction and its tests in
   place. One file per session, so a later session never overwrites an earlier one. The earlier copy
   attempt was blocked by AI Guardian (`tool_permission`, subreason `immutable_protection`,
   `viol_23534299`); this version was written here, not copied, at the user's request. If a call is
   blocked again, report it and stop.
3. **Themes: done.** Eight themes: day and night (ours), stadium and field (from `many-board`), stage and
   bright (from `many-game-show`), and navy and gold (the default palettes of `many-board` and
   `many-game-show`: navy/crimson and navy/gold). Only UI palettes are taken; grass, line, team and ball
   colors are chosen here. All the theme files were read, including `many-game-show`'s
   `UI_LOOK_AND_FEEL.md` and `static/index.html`. Their conventions, which this repo already follows:
   the theme is a `data-theme` attribute on `<html>` set from a `<select>` in the header and kept in
   `localStorage`; colors are CSS custom properties with per-theme overrides; a view with a strong look
   may add a `[data-theme="x"]` override but must still work in every theme; colors that mean one thing
   everywhere (for example correct green, wrong red) are hardcoded, not themed. Orbitron display
   fonts are not used here.
4. **AIA rules: done.** Read from both reference projects, including the quest map `AGENTS.md` (the
   guard that blocked it earlier was off). They differ: see Rules. The AIA line comes from
   `many-game-show`; the quest map uses a plain-language sentence instead. If the user wants this repo
   to use the quest map's wording, only the commit footer in `Rules` and in past habits changes.
