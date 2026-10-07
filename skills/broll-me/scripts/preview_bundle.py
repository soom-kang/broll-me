"""Stage a complete preview bundle and restore prior files on publication failure."""
import argparse
import os
from pathlib import Path
import shutil
import tempfile

from composite import create_preview
from make_pages import write_pages
from media import MediaError, input_file, load_plan


class RecoveryError(MediaError):
    """A publication rollback failed; its staging directory must be retained."""


def publish_bundle(stage, outdir, protected=()):
    files = sorted(path for path in stage.rglob("*") if path.is_file())
    protected = {Path(path).resolve() for path in protected}
    # Validate the entire destination set before moving any existing file.
    for source in files:
        destination = outdir / source.relative_to(stage)
        if destination.resolve() in protected:
            raise MediaError(f"Bundle output must not overwrite an input: {destination}")
        for parent in (destination, *destination.parents):
            if parent.is_symlink():
                raise MediaError(f"Bundle output must not use a symlink: {parent}")
            if parent == outdir:
                break
        if destination.exists() and not destination.is_file():
            raise MediaError(f"Bundle output is not a regular file: {destination}")
        if source.relative_to(stage).parts[0] == "assets" and destination.exists() and destination.read_bytes() != source.read_bytes():
            raise MediaError(f"Bundle asset differs; use a new output directory: {destination}")
    journal = []
    try:
        for source in files:
            destination = outdir / source.relative_to(stage)
            destination.parent.mkdir(parents=True, exist_ok=True)
            backup = None
            if destination.exists():
                backup = stage / ".previous" / source.relative_to(stage)
                backup.parent.mkdir(parents=True, exist_ok=True)
                os.replace(destination, backup)
            journal.append((destination, backup))
            os.replace(source, destination)
    except OSError as error:
        failures = []
        for destination, backup in reversed(journal):
            try:
                if backup is None:
                    destination.unlink(missing_ok=True)
                else:
                    os.replace(backup, destination)
            except OSError as recovery:
                failures.append(f"{destination}: {recovery}")
        if failures:
            raise RecoveryError(f"Bundle publication failed: {error}; recovery files retained at {stage}; rollback failed: {'; '.join(failures)}") from error
        raise MediaError(f"Bundle publication failed; prior files restored: {error}") from error


def create_bundle(plan_path, output, font_mode="shared"):
    plan_path = input_file(plan_path)
    _, source, _, clips = load_plan(plan_path)
    output = Path(output).expanduser().absolute()
    protected = [plan_path, source, *(clip["path"] for clip in clips)]
    if output.suffix.lower() != ".mp4":
        raise MediaError("Output must end with .mp4")
    if output.resolve() in protected:
        raise MediaError("Output must not overwrite an input file")
    outdir = output.parent
    outdir.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".broll-preview-", dir=outdir.parent))
    retain = False
    try:
        preview = stage / output.name
        create_preview(plan_path, preview)
        write_pages(plan_path, preview, font_mode=font_mode, publish_dir=outdir)
        # Once publication starts, unexpected exits must never erase backups.
        retain = True
        try:
            publish_bundle(stage, outdir, protected)
        except RecoveryError:
            raise
        except MediaError:
            # Preflight failed or publication rolled back successfully.
            retain = False
            raise
        except BaseException as error:
            raise RecoveryError(f"Bundle publication interrupted; recovery files retained at {stage}: {error}") from error
        retain = False
    finally:
        if not retain:
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--font-mode", choices=("shared", "embedded"), default="shared")
    args = parser.parse_args()
    try:
        create_bundle(args.plan, args.output, args.font_mode)
    except (MediaError, OSError, ValueError) as error:
        parser.exit(1, f"preview_bundle: {error}\n")


if __name__ == "__main__":
    main()
