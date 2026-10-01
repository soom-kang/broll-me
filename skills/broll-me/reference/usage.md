# Run the common CLI

Use `scripts/broll.py` in either host. For the default project-local `npx skills add` installation, use the path below. If your installation differs, set `BROLL_SKILL_DIR` to the actual folder containing the loaded `SKILL.md`. Follow [the workflow](workflow.md) for installation, prompts and recovery steps.

```bash
export BROLL_SKILL_DIR="$PWD/.agents/skills/broll-me"
export BROLL_RUNTIME="$PWD/motion"
python3 "$BROLL_SKILL_DIR/scripts/broll.py" doctor
```

Runtime selection follows `--runtime PATH`, then `BROLL_RUNTIME`, then `./motion`. The CLI connects that runtime’s `.venv/bin/python`, `node_modules` and `browsers`. Executable overrides are `BROLL_PYTHON`, `BROLL_NODE`, `BROLL_FFMPEG`, `BROLL_FFPROBE` and `BROLL_CHROMIUM`. The browser override must match the fixed profile too.

## Choose the command

Place `--runtime` before the subcommand. Paths below are command arguments; replace them with your actual files.

| Command arguments | Result | On failure |
| --- | --- | --- |
| `doctor` | Fixed-version checks and an actual browser launch; no installation | Select matching executables or report the permission block |
| `inspect VIDEO OUT_DIR` | `video.json`, actual-size `contact.png` | Correct the input path or unsupported source streams |
| `words TRANSCRIPT` | Estimated word timing from SRT/VTT cues | Correct the path or subtitle syntax |
| `build OUT_DIR --scene SPEC.json` | HTML, palette snapshot and fonts | Correct the SceneSpec field or use a fresh output folder |
| `build OUT_DIR FRAGMENT.html...` | Compiled custom scene HTML | Correct the fragment; do not combine with `--scene` |
| `check BUILT.html` | Scene-contract, sampled browser and template overflow checks | Fix the reported reference, timing or layout |
| `beats BUILT.html OUT.png TIME...` | Contact sheet at specified times | Use times within scene duration and a writable output path |
| `render BUILT.html OUTPUT` | MP4 or alpha MOV | Read stderr and inspect the encoder/browser error |
| `preview PLAN.json OUT.mp4` | Composite, viewer, compare, timing notes and fonts | Correct the plan or supply an approved compatible input copy |

Build accepts `--palette ID` or `--palette-file custom.json`, defaulting to `warm-orange`. Render accepts `--fps RATE` (default `30`) and `--quality final|draft` (default `final`). Rational FPS such as `30000/1001` is supported. Build and preview accept `--font-mode shared|embedded`, defaulting to `shared` in this CLI.

## Read the result

Except for help, stdout contains one JSON object. `status:completed` with exit code `0` establishes completion of that command. It does not establish human visual approval or completion of later steps. Errors contain `status:error`, `exit_code` and `message`; stderr contains detailed child diagnostics. Usage errors use `2`, timeout uses `124`, and other failures retain the child code or use `1`.

Check the runtime profile in [versions.json](../scripts/runtime/versions.json). Use [setup.sh](../scripts/setup.sh) for an authorized local installation and [troubleshooting](troubleshooting.md) for bounded recovery. The direct Python and Node entry points remain available; their build/review-page font default is embedded.
