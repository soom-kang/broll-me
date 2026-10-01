"""Resolve strict, portable B-roll color tokens without model-specific dependencies."""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path

PALETTES_DIR = Path(__file__).resolve().parent.parent / "palettes"
DEFAULT_PALETTE = "warm-orange"
ROLES = (
    "canvas", "surface", "surfaceAlt", "ink", "muted", "border", "accent",
    "accentDark", "onAccent", "inverseSurface", "inverseInk", "inverseMuted", "shadow",
)
DECORATIVE_ROLES = ("rose", "coral", "honey")
PRESETS = ("warm-orange", "sage-cream", "editorial-blue", "midnight-cyan", "kkumil-pink", "onnimm-orange")
HEX = re.compile(r"#[0-9a-fA-F]{6}\Z")


class PaletteError(ValueError):
    """A palette cannot be used safely or reproducibly."""


def luminance(color: str) -> float:
    values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
    return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast_ratio(a: str, b: str) -> float:
    low, high = sorted((luminance(a), luminance(b)))
    return (high + 0.05) / (low + 0.05)


def contrast_checks(colors: dict[str, str]) -> dict[str, float]:
    pairs = (("ink", "canvas"), ("ink", "surface"), ("ink", "surfaceAlt"),
             ("muted", "surface"), ("muted", "surfaceAlt"),
             ("inverseInk", "inverseSurface"), ("inverseMuted", "inverseSurface"),
             ("onAccent", "accent"))
    return {f"{a}/{b}": contrast_ratio(colors[a], colors[b]) for a, b in pairs}


def validate_palette(data: object) -> dict:
    if not isinstance(data, dict):
        raise PaletteError("palette must be an object with schema_version, id, name, and colors")
    allowed = {"schema_version", "id", "name", "colors"}
    unknown = set(data) - allowed
    if unknown:
        raise PaletteError(f"unknown palette fields: {', '.join(sorted(unknown))}")
    if data.get("schema_version") != 1 or isinstance(data.get("schema_version"), bool):
        raise PaletteError("schema_version must be 1")
    for key in ("id", "name"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise PaletteError(f"{key} must be a non-empty string")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", data["id"]):
        raise PaletteError("id must use lowercase kebab-case")
    colors = data.get("colors")
    if not isinstance(colors, dict):
        raise PaletteError("colors must be an object containing every required role")
    missing = set(ROLES) - set(colors)
    unknown_colors = set(colors) - set(ROLES) - set(DECORATIVE_ROLES)
    if missing:
        raise PaletteError(f"missing palette roles: {', '.join(sorted(missing))}")
    if unknown_colors:
        raise PaletteError(f"unknown palette roles: {', '.join(sorted(unknown_colors))}")
    for role, color in colors.items():
        if not isinstance(color, str) or not HEX.fullmatch(color):
            raise PaletteError(f"{role} must be an exact #RRGGBB color")
    normalized = {role: colors[role].upper() for role in (*ROLES, *DECORATIVE_ROLES) if role in colors}
    failures = {pair: ratio for pair, ratio in contrast_checks(normalized).items() if ratio < 4.5}
    if failures:
        detail = ", ".join(f"{pair}={ratio:.3f}:1" for pair, ratio in failures.items())
        raise PaletteError(f"contrast must be at least 4.5:1; failed {detail}")
    return {"schema_version": 1, "id": data["id"], "name": data["name"], "colors": normalized}


def resolve_palette(palette: str | None = None, palette_file: str | Path | None = None) -> dict:
    if palette is not None and palette_file is not None:
        raise PaletteError("--palette and --palette-file are mutually exclusive")
    if palette_file is None:
        palette = palette or DEFAULT_PALETTE
        if palette not in PRESETS:
            raise PaletteError(f"unknown palette '{palette}'; choose {', '.join(PRESETS)}")
        path = PALETTES_DIR / f"{palette}.json"
    else:
        path = Path(palette_file)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PaletteError(f"cannot read palette {path}: {exc}") from exc
    return validate_palette(data)


def css_variables(palette: dict) -> str:
    variables = []
    for role, color in palette["colors"].items():
        name = re.sub(r"([A-Z])", r"-\1", role).lower()
        variables.append(f"--broll-{name}:{color}")
    return ":root{" + ";".join(variables) + "}"


def preflight_snapshot(palette: dict, path: str | Path, protected_paths=()) -> bool:
    """Reject source collisions and mixed palettes; return whether a safe snapshot exists."""
    target = Path(path)
    if target.is_symlink():
        raise PaletteError(f"palette snapshot must not be a symlink: {target}; use a new output directory")
    resolved_target = target.resolve()
    for protected in protected_paths:
        if resolved_target == Path(protected).resolve():
            raise PaletteError(f"palette snapshot would overwrite input {protected}; use a new output directory")
    if target.exists():
        try:
            existing = resolve_palette(palette_file=target)
        except PaletteError as exc:
            raise PaletteError(f"existing palette snapshot cannot be reused: {target}; use a new output directory") from exc
        if existing != palette:
            raise PaletteError(f"output directory already uses palette '{existing['id']}', requested '{palette['id']}'; use a new output directory")
        return True
    return False


def write_snapshot(palette: dict, path: str | Path, protected_paths=()) -> None:
    """Publish a complete snapshot atomically, without overwriting files or following links."""
    palette = validate_palette(palette)
    target = Path(path)
    if preflight_snapshot(palette, target, protected_paths):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                         prefix=".broll-palette-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(palette, indent=2, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic create-if-absent. A racing file or symlink cannot be overwritten.
        try:
            os.link(temporary, target)
        except FileExistsError:
            if not preflight_snapshot(palette, target, protected_paths):
                raise PaletteError("palette snapshot changed while publishing; retry in a new output directory")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--palette", choices=PRESETS)
    group.add_argument("--palette-file", type=Path)
    parser.add_argument("--out", type=Path, help="write a validated palette snapshot")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list:
        print("\n".join(PRESETS))
        return 0
    try:
        resolved = resolve_palette(args.palette, args.palette_file)
        if args.out:
            write_snapshot(resolved, args.out, (args.palette_file,) if args.palette_file else ())
        print(json.dumps({"palette": resolved, "contrast": contrast_checks(resolved["colors"])}, indent=2))
        return 0
    except (PaletteError, OSError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
