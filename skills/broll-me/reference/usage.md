# Run the common CLI

Use `scripts/broll.py` in either host. For the default project-local `npx skills add` installation, use the path below. If your installation differs, set `BROLL_SKILL_DIR` to the actual folder containing the loaded `SKILL.md`. Follow [the workflow](workflow.md) for installation, prompts and recovery steps.

```bash
export BROLL_SKILL_DIR="$PWD/.agents/skills/broll-me"
export BROLL_RUNTIME="${BROLL_RUNTIME:-$PWD/works/.runtime/broll-me}"
python3 "$BROLL_SKILL_DIR/scripts/broll.py" doctor
```

Run from the working project, separate from the installed skill folder. Reuse an explicit runtime by setting its absolute path before these commands. The skill's default is `works/.runtime/broll-me/`; direct CLI selection remains `--runtime PATH`, then `BROLL_RUNTIME`, then `./motion`. The CLI connects that runtime’s `.venv/bin/python`, `node_modules` and `browsers`. Executable overrides are `BROLL_PYTHON`, `BROLL_NODE`, `BROLL_FFMPEG`, `BROLL_FFPROBE` and `BROLL_CHROMIUM`. The browser override must match the fixed profile too. A failure in the selected runtime requires a reported error before retrying the affected step.

## Choose the command

Place `--runtime` before the subcommand. Paths below are explicit command arguments; the CLI does not choose task folders. For skill work, use `inputs/` for supplied files, `works/<task>/` for persistent intermediates and drafts, and `outputs/<task>/` for final files. Explicit user paths take precedence. Choose a short English task name; suffix it with `-02`, then `-03`, if it exists in either work or output folder. An explicit continuation reuses the task. Ask about missing required inputs or ambiguous video/subtitle pairs. A standalone prompt with supplied wording or data needs no input file.

| Command arguments | Result | On failure |
| --- | --- | --- |
| `doctor` | Fixed-version checks and an actual browser launch; no installation | Select matching executables or report the permission block |
| `inspect VIDEO OUT_DIR` | `video.json`, actual-size `contact.png` | Correct the input path or unsupported source streams |
| `words TRANSCRIPT` | Estimated word timing from SRT/VTT cues | Correct the path or subtitle syntax |
| `build OUT_DIR --scene SPEC.json` | HTML, palette snapshot and fonts | Correct the SceneSpec field or use a fresh output folder |
| `build OUT_DIR FRAGMENT.html...` | Compiled custom scene HTML | Correct the fragment; do not combine with `--scene` |
| `check BUILT.html` | Scene contracts, sampled browser errors, resource request failures and template overflow checks | Fix the reported reference, timing or layout |
| `beats BUILT.html OUT.png TIME...` | Contact sheet at specified times | Use times within scene duration and a writable output path |
| `render BUILT.html OUTPUT` | MP4 or alpha MOV | Read stderr and inspect the encoder/browser error |
| `preview PLAN.json OUT.mp4` | Composite, viewer, compare, timing notes and fonts, staged before publication | Correct the plan or input; inspect retained recovery files before retrying |

`words` reads cue text and timing when a WebVTT cue identifier starts with a reserved block name, such as `NOTEworthy`, `STYLE-demo`, `REGION-1` or `WEBVTT-demo`. It skips actual WebVTT headers and `NOTE`, `STYLE` and `REGION` blocks. Cue identifiers are not included in the word-timing output.

Build accepts `--palette ID` or `--palette-file custom.json`, defaulting to `warm-orange`. Render accepts `--fps RATE` (default `30`) and `--quality final|draft` (default `final`). Rational FPS such as `30000/1001` is supported. Build and preview accept `--font-mode shared|embedded`, defaulting to `shared` in this CLI.

Save a plan at `works/palette-card/plan.json` with `video: "../../inputs/source.mp4"` and clip `file: "../../outputs/palette-card/scene.mp4"`. Plan paths resolve from the plan file. After rendering final clips in `outputs/palette-card/`, create review files there:

```bash
python3 "$BROLL_SKILL_DIR/scripts/broll.py" preview \
  works/palette-card/plan.json outputs/palette-card/preview.mp4
```

Deliver scene HTML with its palette snapshot, fonts and required local assets in `outputs/<task>/scenes/<scene>/`. Check references after copying the bundle and render from that location. Final references must not depend on `works/`; `compare.html` may reference the source in `inputs/`. Preserve prior results on failure and report unresolved custom resources before claiming delivery complete. Engine atomic temporary files and OS temporary files keep their existing behavior.

`preview` completes its media and review files in a temporary `.broll-preview-*` directory beside the output folder, then publishes them file by file. Preparation failures leave existing output files unchanged. A filesystem publication error triggers an attempt to restore previous files. An interruption or failed rollback retains the staging directory and any `.previous` backups; preserve them and inspect the outputs before retrying. Follow [media recovery](troubleshooting.md#media-and-delivery) when the error reports retained recovery files.

## Read the result

Except for help, stdout contains one JSON object. `status:completed` with exit code `0` establishes completion of that command. It does not establish human visual approval or completion of later steps. Errors contain `status:error`, `exit_code` and `message`; stderr contains detailed child diagnostics. Usage errors use `2`, timeout uses `124`, and other failures retain the child code or use `1`.

Check the runtime profile in [versions.json](../scripts/runtime/versions.json). Use [setup.sh](../scripts/setup.sh) for an authorized local installation and [troubleshooting](troubleshooting.md) for bounded recovery. The direct Python and Node entry points remain available; their build/review-page font default is embedded.
