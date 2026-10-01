#!/usr/bin/env python3
"""Install one canonical skill into project-local Codex and Claude discovery paths."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import sys

HOST_PATHS = {"codex": ".agents/skills", "claude": ".claude/skills"}


def install(source: Path, project: Path, host: str = "both", dry_run: bool = False) -> list[Path]:
    source = source.resolve(strict=True)
    project = project.resolve(strict=True)
    if not project.is_dir() or not (source / "SKILL.md").is_file():
        raise ValueError("Source must contain SKILL.md and project must be an existing directory")
    if source.name != "broll-me":
        raise ValueError("Canonical skill directory must be named broll-me")
    targets = [project / path / "broll-me" for name, path in HOST_PATHS.items()
               if host == "both" or name == host]
    if not targets:
        raise ValueError(f"Unknown host: {host}")
    for target in targets:
        if target.is_symlink() and target.resolve() == source:
            continue
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"Refusing to replace existing path: {target}")
        # A linked discovery parent could redirect installation outside this project.
        for parent in target.parents:
            if parent == project:
                break
            if parent.is_symlink():
                raise ValueError(f"Refusing symlinked discovery parent: {parent}")
    for target in targets:
        existing = target.is_symlink() and target.resolve() == source
        if not dry_run and not existing:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(os.path.relpath(source, target.parent), target_is_directory=True)
        action = "already installed" if existing else "would install" if dry_run else "installed"
        print(f"{action}: {target} -> {source}")
        if existing or not dry_run:
            print(f"Remove this link only: unlink {shlex.quote(str(target))}")
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--source", type=Path,
                        default=Path(__file__).resolve().parents[1] / "skills/broll-me")
    parser.add_argument("--host", choices=["both", "codex", "claude"], default="both")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        install(args.source, args.project, args.host, args.dry_run)
    except (OSError, ValueError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
