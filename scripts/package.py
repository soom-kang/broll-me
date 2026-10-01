#!/usr/bin/env python3
"""Package curated source with skill-creator when available, then verify both archives."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from validate_package import collect_files, verify_archive


def creator_default() -> Path | None:
    for base in (".agents", ".claude", ".codex"):
        candidate = Path.home() / base / "skills/skill-creator"
        if (candidate / "scripts/package_skill.py").is_file():
            return candidate
    return None


def build_package(skill: Path, output: Path, creator: Path | None = None,
                  require_creator: bool = False) -> dict:
    files = collect_files(skill)
    if creator is not None and not (creator / "scripts/package_skill.py").is_file():
        raise ValueError(f"skill-creator packager missing from {creator}")
    available = creator is not None and importlib.util.find_spec("yaml") is not None
    if require_creator and not available:
        raise ValueError("skill-creator packaging requires a creator path and PyYAML in this dev Python")
    with tempfile.TemporaryDirectory(prefix="broll-package-") as tmp:
        stage = Path(tmp) / "broll-me"
        for name, data in files.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        archive = Path(tmp) / "broll-me.skill"
        backend = "skill-creator" if available else "stdlib-curated"
        if available:
            subprocess.run([sys.executable, "-m", "scripts.package_skill", str(stage), tmp],
                           cwd=creator.resolve(), check=True)
        else:
            print("skill-creator/PyYAML unavailable; using validated stdlib ZIP packaging")
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
                for name, data in files.items():
                    info = zipfile.ZipInfo(f"broll-me/{name}", date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    package.writestr(info, data)
        verify_archive(archive, files)
        output.mkdir(parents=True, exist_ok=True)
        skill_archive = output / "broll-me.skill"
        zip_archive = output / "broll-me.zip"
        shutil.copyfile(archive, skill_archive)
        shutil.copyfile(archive, zip_archive)
        verify_archive(skill_archive, files)
        verify_archive(zip_archive, files)
        manifest = {"skill": "broll-me", "packaging_backend": backend,
                    "validation": "curated source, exact archive bytes and extraction round-trip passed",
                    "archives": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (skill_archive, zip_archive)},
                    "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
        (output / "package-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", type=Path, default=root / "skills/broll-me")
    parser.add_argument("--output", type=Path, default=root / "dist")
    parser.add_argument("--creator-path", type=Path, default=creator_default())
    parser.add_argument("--require-creator", action="store_true")
    args = parser.parse_args()
    try:
        result = build_package(args.skill, args.output, args.creator_path, args.require_creator)
        print(json.dumps({"status": "passed", "backend": result["packaging_backend"], "output": str(args.output.resolve()), "files": len(result["files"])}))
    except (OSError, ValueError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        print(f"Packaging failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
