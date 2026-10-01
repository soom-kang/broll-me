"""Assemble semantic clip fragments, palette, engine and local fonts into offline HTML.

Usage: python3 build.py OUT_DIR CLIP.html [CLIP.html ...] --palette warm-orange
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

from palette import (PaletteError, css_variables, preflight_snapshot, resolve_palette,
                     validate_palette, write_snapshot)
from fonts import font_css
from scene_templates import compile_scene, load_scene

E = Path(__file__).resolve().parent
CURSOR = ('<svg id="cursor" viewBox="0 0 40 56"><path '
          'd="M3 3 L3 41 L12.5 32 L19 47 L25.5 44.2 L19.2 29.8 L32 29.8 Z" '
          'fill="var(--broll-ink)" stroke="var(--broll-surface)" stroke-width="2.6" '
          'stroke-linejoin="round"/></svg>')


def preflight_outputs(sources, destinations, palette: dict, palette_file=None) -> None:
    """Check the entire batch before any scene or palette output is written."""
    protected = [Path(source) for source in sources]
    if palette_file is not None:
        protected.append(Path(palette_file))
    input_paths = {path.resolve() for path in protected}
    for source in sources:
        if not Path(source).is_file():
            raise ValueError(f"source fragment is not a file: {source}")
    for destination in destinations:
        destination = Path(destination)
        if destination.resolve() in input_paths:
            raise ValueError(f"destination must not overwrite an input: {destination}")
        preflight_snapshot(palette, destination.parent / "palette.resolved.json", protected)


def build(src: str | Path, dst: str | Path, *, palette: str | None = None,
          palette_file: str | Path | None = None, resolved_palette: dict | None = None,
          font_mode: str = "embedded", scene: bool = False) -> Path:
    if resolved_palette is not None and (palette is not None or palette_file is not None):
        raise PaletteError("resolved_palette cannot be combined with palette selectors")
    resolved = validate_palette(resolved_palette) if resolved_palette is not None else resolve_palette(palette, palette_file)
    source, destination = Path(src), Path(dst)
    preflight_outputs((source,), (destination,), resolved, palette_file)
    frag = compile_scene(load_scene(source)) if scene else source.read_text(encoding="utf-8")
    match = re.search(r"<title>(.*?)</title>", frag, re.S)
    title = html.unescape(match.group(1)) if match else source.stem
    css = "\n".join(re.findall(r"<style>(.*?)</style>", frag, re.S))
    js = "\n".join(re.findall(r"<script>(.*?)</script>", frag, re.S))

    def slot(name: str) -> str:
        match = re.search(rf'<div data-slot="{name}">(.*?)</div><!--/{name}-->', frag, re.S)
        return match.group(1) if match else ""

    base = (E / "base.css").read_text(encoding="utf-8")
    base = base.replace("__BROLL_FONT_CSS__", font_css(destination.parent, font_mode))
    # No source-color replacement. CSS consumes semantic vars; JS consumes resolved hex.
    palette_json = json.dumps(resolved["colors"], separators=(",", ":")).replace("<", "\\u003c")
    page = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="broll-palette" content="{html.escape(resolved["id"], quote=True)}">'
            f'<title>{html.escape(title)}</title><style>{css_variables(resolved)}\n{base}\n{css}</style>'
            f'</head><body><div id="wrap"><div id="stage"><div id="world">'
            f'{slot("world")}<div id="shape">{slot("shape")}</div>{slot("over")}</div>{CURSOR}'
            f'</div></div><script>window.BROLL_PALETTE={palette_json};</script>'
            f'<script>{(E / "motion.js").read_text(encoding="utf-8")}</script>'
            f'<script>{js}</script></body></html>')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(page, encoding="utf-8")
    write_snapshot(resolved, destination.parent / "palette.resolved.json",
                   (source, palette_file) if palette_file is not None else (source,))
    return destination


def build_scene(src: str | Path, dst: str | Path, **options) -> Path:
    return build(src, dst, scene=True, **options)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("clips", type=Path, nargs="*")
    parser.add_argument("--scene", type=Path, help="SceneSpec JSON instead of HTML fragments")
    parser.add_argument("--font-mode", choices=("shared", "embedded"), default="embedded")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--palette")
    group.add_argument("--palette-file", type=Path)
    args = parser.parse_args()
    if bool(args.clips) == bool(args.scene):
        parser.error("supply either HTML fragments or --scene SPEC.json")
    try:
        resolved = resolve_palette(args.palette, args.palette_file)
        sources = [args.scene] if args.scene else args.clips
        names = [clip.stem for clip in sources]
        if len(names) != len(set(names)):
            raise ValueError("clips have duplicate output stems; build them into separate directories")
        destinations = [args.out_dir / f"{source.stem}.html" for source in sources]
        preflight_outputs(sources, destinations, resolved, args.palette_file)
        for source in sources:
            destination = build(source, args.out_dir / f"{source.stem}.html", resolved_palette=resolved,
                                font_mode=args.font_mode, scene=bool(args.scene))
            print(f"built {destination}")
        return 0
    except (PaletteError, OSError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
