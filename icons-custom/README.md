# icons-custom

Drop an SVG here with the same file name as one in `src/icons/` (for example `player.svg`) and the
build uses it instead of the built-in one. Everything in this folder except this README is
git-ignored, so it is a good place to try out new art.

Rules: a single root `<svg>` with `viewBox="-32 -32 64 64"` (centered on the origin), no `<script>`,
`<image>`, `<foreignObject>`, `<iframe>`, `<object>` or `<embed>`, no event handlers, no external
references. Use `var(--team)` for the team ring and `currentColor` for tintable parts.
