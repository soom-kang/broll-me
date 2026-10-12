"""Assemble semantic clip fragments, palette, engine and local fonts into offline HTML.

Usage: python3 build.py OUT_DIR CLIP.html [CLIP.html ...] --palette warm-orange
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from palette import (PaletteError, PaletteRecoveryError, _publish_snapshot, css_variables,
                     preflight_snapshot, resolve_palette, snapshot_lock, validate_palette)
from fonts import font_css
from scene_templates import compile_scene, load_scene

E = Path(__file__).resolve().parent
CURSOR = ('<svg id="cursor" viewBox="0 0 40 56"><path '
          'd="M3 3 L3 41 L12.5 32 L19 47 L25.5 44.2 L19.2 29.8 L32 29.8 Z" '
          'fill="var(--broll-ink)" stroke="var(--broll-surface)" stroke-width="2.6" '
          'stroke-linejoin="round"/></svg>')


def check_destination(destination: Path, protected) -> None:
    if destination.is_symlink():
        raise ValueError(f"destination must not be a symlink: {destination}; use a new output directory")
    for path in protected:
        if (destination.resolve() == path.resolve()
                or (destination.exists() and path.exists() and destination.samefile(path))):
            raise ValueError(f"destination must not overwrite an input: {destination}; use a new output directory")


def check_batch_destinations(sources, destinations) -> None:
    """Reserve names in a disposable target-filesystem directory, never final outputs."""
    if len(destinations) < 2:
        return
    groups = {}
    for index, destination in enumerate(destinations):
        destination = Path(destination)
        resolved = destination.resolve()
        anchor = resolved.parent
        while not anchor.exists():
            anchor = anchor.parent
        if not anchor.is_dir():
            raise ValueError(f"output parent must be a directory: {anchor}")
        info = anchor.stat()
        group = groups.setdefault((info.st_dev, info.st_ino), (anchor, []))
        source = sources[index] if index < len(sources) else "unspecified source"
        group[1].append((source, destination, resolved.relative_to(anchor)))
    for anchor, outputs in groups.values():
        if len(outputs) < 2:
            continue
        # A new directory inherits the target filesystem's name handling. Full
        # names also preserve NAME_MAX, unlike prefixing final filenames.
        with tempfile.TemporaryDirectory(prefix=".broll-build-preflight-", dir=anchor) as temporary:
            reservations = {}
            for source, destination, relative in outputs:
                reservation = Path(temporary) / relative
                reservation.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with reservation.open("xb"):
                        pass
                except FileExistsError as error:
                    info = reservation.stat()
                    previous_source, previous_destination = reservations[(info.st_dev, info.st_ino)]
                    raise ValueError(
                        f"batch output destinations collide on this filesystem: "
                        f"{previous_source} -> {previous_destination}; {source} -> {destination}; "
                        "build them into separate directories"
                    ) from error
                info = reservation.stat()
                reservations[(info.st_dev, info.st_ino)] = (source, destination)


def preflight_outputs(sources, destinations, palette: dict, palette_file=None) -> None:
    """Check the entire batch before any scene or palette output is written."""
    sources, destinations = list(sources), list(destinations)
    protected = [Path(source) for source in sources]
    if palette_file is not None:
        protected.append(Path(palette_file))
    for source in sources:
        if not Path(source).is_file():
            raise ValueError(f"source fragment is not a file: {source}")
    for destination in destinations:
        destination = Path(destination)
        if destination.name.casefold() == "palette.resolved.json":
            raise ValueError(f"HTML destination conflicts with the reserved palette snapshot: {destination}; use a different output path")
        check_destination(destination, protected)
        preflight_snapshot(palette, destination.parent / "palette.resolved.json", protected)
    check_batch_destinations(sources, destinations)


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
    protected = (source, Path(palette_file)) if palette_file is not None else (source,)
    stage = Path(tempfile.mkdtemp(prefix=".broll-build-", dir=destination.parent))
    temporary = stage / destination.name
    retain = False
    published = False
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(page)
            stream.flush()
            os.fsync(stream.fileno())
        snapshot = destination.parent / "palette.resolved.json"
        with snapshot_lock(destination.parent):
            check_destination(destination, protected)
            existed = preflight_snapshot(resolved, snapshot, protected)
            try:
                created = _publish_snapshot(resolved, snapshot, protected)
            except PaletteRecoveryError:
                raise
            except BaseException as error:
                if not existed and snapshot.exists():
                    raise PaletteRecoveryError(f"snapshot publication interrupted: {error}; recovery files retained at {stage}; inspect {snapshot} and {destination.parent / '.broll-palette.lock'} before retrying") from error
                raise
            try:
                check_destination(destination, protected)
                preflight_snapshot(resolved, snapshot, protected)
                # Replace the directory entry, never truncate a shared input inode.
                os.replace(temporary, destination)
                published = True
            except BaseException as error:
                if created is not None:
                    try:
                        if snapshot.is_symlink():
                            raise OSError("palette snapshot changed during rollback")
                        info = snapshot.stat()
                        if (info.st_dev, info.st_ino) != created:
                            raise OSError("palette snapshot ownership changed during rollback")
                        snapshot.unlink()
                    except OSError as recovery:
                        raise PaletteRecoveryError(f"build publication failed: {error}; recovery files retained at {stage}; snapshot rollback failed: {recovery}; inspect {snapshot} and {destination.parent / '.broll-palette.lock'} before retrying") from error
                raise
    except PaletteRecoveryError as error:
        retain = True
        if str(stage) not in str(error):
            raise PaletteRecoveryError(f"{error}; prepared HTML recovery directory retained at {stage}") from error
        raise
    finally:
        if not retain:
            try:
                shutil.rmtree(stage)
            except OSError as error:
                state = "HTML and palette published" if published else "HTML not published"
                raise PaletteRecoveryError(f"build cleanup failed at {stage}: {error}; {state}; inspect the outputs and recovery directory before retrying") from error
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
