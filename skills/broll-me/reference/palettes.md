# Palette templates

Palette selection changes colors while retaining a scene's content, coordinates, timing, morphs, cursor motion and full-frame/transparent export behavior. It does not grade footage, derive colors from source video, or recolor authentic assets.

Use a built-in preset or one complete custom JSON. The default is `warm-orange`. Both Codex and Claude run the same resolver and consume the same frozen values.

| ID | Canvas | Surface | Ink | Accent |
|---|---|---|---|---|
| `warm-orange` | `#E9E7E2` | `#FFFFFF` | `#0B0B0B` | `#FF5A1F` |
| `sage-cream` | `#F4F1E8` | `#FFFDF7` | `#24382C` | `#5E7D64` |
| `editorial-blue` | `#F3F6FA` | `#FFFFFF` | `#172B4D` | `#2F5BEA` |
| `midnight-cyan` | `#111827` | `#1F2937` | `#F9FAFB` | `#67E8F9` |
| `kkumil-pink` | `#FFF0E6` | `#FFFFFF` | `#333333` | `#FF5C8D` |
| `onnimm-orange` | `#FCFBF8` | `#FFFFFF` | `#354135` | `#FF8A50` |

The ONNIMM accent follows its current local UI `--brand-orange`, not the app icon's distinct orange. These presets describe graphics, not production state. Brand primary colors remain exact; their text counterparts are separate roles.

## Contract

All 13 roles are required: `canvas`, `surface`, `surfaceAlt`, `ink`, `muted`, `border`, `accent`, `accentDark`, `onAccent`, `inverseSurface`, `inverseInk`, `inverseMuted`, `shadow`. Every color is `#RRGGBB`. No short hex, RGB strings, CSS functions or implicit fill-in is accepted. Lowercase hex is normalized to uppercase. `palettes/schema.json` defines structure; `engine/palette.py` also checks text contrast. Neither a model nor runtime chooses missing colors.

| Role | Use |
|---|---|
| `canvas` | Full-frame background; never substitutes for `bg:null`. |
| `surface`, `surfaceAlt` | Main and secondary panels. |
| `ink`, `muted` | Primary and secondary text on ordinary panels. |
| `border` | Separators, tracks and outlines; not body text. |
| `accent`, `accentDark` | Brand highlight and deeper decorative tone. |
| `onAccent` | Text or icons directly on `accent`. |
| `inverseSurface` | Opposite-tone chip, pill or panel. |
| `inverseInk`, `inverseMuted` | Text on inverse panels. |
| `shadow` | Shadow tint, used with explicit opacity. |

The only optional registered decorative roles are `rose`, `coral`, `honey`. `kkumil-pink` includes rose `#FF8FA6` and coral `#FFCDB5`; `onnimm-orange` includes honey `#F1D3B2` and apricot `#FAE5D5` as `surfaceAlt`. These extra colors may decorate shapes; they do not acquire implicit text/contrast roles. Refer to an optional role only when the selected palette declares it. A shared template must use a core role or an explicit core fallback.

Required contrast is at least 4.5:1 for `ink/canvas`, `ink/surface`, `ink/surfaceAlt`, `muted/surface`, `muted/surfaceAlt`, `inverseInk/inverseSurface`, `inverseMuted/inverseSurface`, `onAccent/accent`. Unknown roles, incomplete palettes, unreadable pairs and invalid files fail before HTML is written. Accent text elsewhere, animated colors and opacity still require visual review; validation is not full-frame accessibility certification. Never automatically alter an approved brand accent to pass.

## Author and build

CSS uses semantic variables such as `var(--broll-ink)` and `var(--broll-surface-alt)`. Script uses `M.palette.ink`, `M.palette.surfaceAlt`. `M.ctrack` requires resolved hex colors; CSS variable strings are not hex.

```js
const P = M.palette;
const color = M.ctrack(P.surface, [[0.5, P.inverseSurface]]);
const tint = M.rgba(P.accent, 0.25);
const pulse = M.mixColors(P.ink, P.accent, M.clamp(t));
```

`M.rgba(hex, alpha=1)` returns an RGBA string with alpha clamped to 0–1. `M.mixColors(a, b, t)` returns an exact interpolated RGB hex with `t` clamped to 0–1. Both reject non-finite numbers and malformed colors. `M.palette` is frozen during initialization. Colors are injected before `motion.js`.

```sh
python3 engine/build.py /tmp/broll-demo examples/palette-demo.html --palette kkumil-pink
python3 engine/build.py /tmp/broll-panel examples/panel-demo.html --palette onnimm-orange
python3 engine/build.py /tmp/custom examples/palette-demo.html --palette-file custom.json
python3 engine/palette.py --palette midnight-cyan
```

Flags `--palette` and `--palette-file` are mutually exclusive. Copy a preset JSON as the custom template, change `id`, `name` and all needed colors, then validate it. Built HTML embeds colors; fonts can be embedded or shared locally. Each output directory receives `palette.resolved.json`. Reuse that snapshot with `--palette-file` in a **different output directory** to reproduce the palette. An output directory holds one palette: an existing different palette causes failure before any HTML is written. Same-palette builds reuse the snapshot unchanged. Snapshot/input collisions and snapshot symlinks are rejected for the entire CLI batch before outputs. New snapshots are published atomically without overwriting existing files or following symlinks. Choose a new output directory when these checks fail; do not delete or replace user-owned files to continue.

## Verification and limits

Verify the same fragment under at least one light and one dark palette. Check ordinary, inverse, accent, cursor and selected labels at transition and hold times. Selected text uses clipped normal-blend overlays, not difference blend. Preserve source layout/timing and keep explicit `bg:null` transparent. Six `examples/opus-aoe2/` fragments retain their geometry and timings; the two 1-second 640×360 demo fragments provide inexpensive integration fixtures. Korean glyphs come from embedded local Noto Sans KR after Geist/Geist Mono.

Do not apply palette color replacement to arbitrary user HTML: author semantic roles in CSS and JavaScript, including computed RGB values and SVG. This avoids changing factual screenshots, logos and animation geometry. Font size, safe areas and legibility over real footage still require inspection and approval.
