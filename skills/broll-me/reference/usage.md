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

Build rejects an existing HTML output symlink or an output that shares an input's file identity, including hard links to scene specifications, fragments or custom palette files. The CLI checks the complete batch before writing deliverables. Choose a fresh output directory when an alias is reported. The name `palette.resolved.json` is reserved for the snapshot and cannot be an HTML destination.

Batch builds also reject filesystem-equivalent destination names, including case and normalization aliases, before writing final HTML, fonts or the palette snapshot. An exclusive name-reservation probe uses a temporary `.broll-build-preflight-*` directory on the target filesystem, at the existing output directory or nearest existing ancestor. It mirrors missing relative directories and removes the probe before building. This preflight creates temporary entries; it does not create a missing final output directory or change existing deliverables. It uses the filesystem's name handling instead of unconditional casefolding, so distinct case-sensitive names remain supported. Collision errors name both sources and destinations; use different names or separate output directories. Single-output builds skip this probe.

Build prepares HTML in a `.broll-build-*` directory, then uses the same `.broll-palette.lock` as standalone palette writers to check compatibility, publish the snapshot and replace the HTML. An HTML publication failure removes only a snapshot created by that build; a reusable snapshot is preserved. A conflicting palette fails before replacing the HTML. An occupied lock fails immediately and is never automatically reclaimed. If rollback or cleanup fails, inspect the reported outputs, staging files and lock before retrying. Successful publication followed by a cleanup error can leave complete outputs. This is coordination with rollback for cooperating writers, not atomic visibility of multiple files or an all-or-nothing CLI batch.

Python composite, inspection and review-page outputs reject symlinks in the output path and parent directories. They also reject outputs with the same filesystem identity as a protected input, including case aliases and distinct hardlink entries. Protection covers the source, plan and clips for composition, the source for inspection, and the source, plan, clips and selected preview for review pages. The checks use resolved paths and `samefile()`, rather than folding filename case; distinct files on a case-sensitive filesystem remain allowed. Choose a separate file under a real output directory. The standard macOS `/tmp` and `/var` aliases to `/private/tmp` and `/private/var` remain supported. Readable input symlinks remain allowed. Direct review-page generation writes beside the selected preview argument; a preview-file symlink does not move the generated pages into its target directory. Publication checks do not claim protection against a hostile process replacing a directory after the final check.

Direct review-page generation checks viewer, compare, timing-sheet and all derived panel-preview destinations before rendering panels or copying fonts. Inspection checks both contact-sheet and report destinations before encoding. These checks reject output symlinks, existing non-regular files, non-directory parents and protected-input identity collisions. Shared mode also validates all font sources, asset directories and existing font/notice files for symlink, type and byte conflicts before rendering a panel. Validation creates no directories or assets; font copying and atomic publication recheck their destinations. These known failures leave prior outputs unchanged. The preflight does not make multiple files one transaction or guarantee rollback for later filesystem failures.

Build accepts `--palette ID` or `--palette-file custom.json`, defaulting to `warm-orange`. Render accepts `--fps RATE` (default `30`) and `--quality final|draft` (default `final`). Rational FPS such as `30000/1001` is supported. Build and preview accept `--font-mode shared|embedded`, defaulting to `shared` in this CLI.

Custom fragments keep the existing `[w, z]` spring inputs, including overdamping (`z > 1`). Overdamping now affects the response instead of falling back to critical damping; re-preview affected fragments to check settling times. See [custom springs](engine-api.md#custom-springs) for the calculation and compatibility limits.

Shared font mode copies the three font files and both OFL notices to `assets/broll-me-fonts/` beside the HTML. Embedded mode includes the font data and full named OFL notices as CSS comments in each HTML source, without adding visible page content. Both modes fail if a required source notice is missing or empty. Referenced media, custom assets and their notices must still accompany the output; see [third-party notices](../THIRD_PARTY_NOTICES.md).

Final alpha rendering averages four subframes with 16-bit premultiplied RGB, then restores straight alpha. A visible color keeps its intensity as its coverage fades. Accumulation stays continuous when Chromium PNGs switch between RGB and RGBA at the fixed viewport size. Draft rendering and opaque final rendering keep their existing filters; FPS, frame count and output codecs are unchanged. Render closes the encoder and browser before replacing the output with its staged video, so cancellation during that cleanup preserves the previous output.

Node `beats` checks its PNG destination against the HTML input's resolved path and filesystem device/inode before opening the browser or creating outputs. A hardlink to that input is refused; readable HTML input symlinks remain allowed. Contact-sheet staging uses `.broll-beats-*` beside the destination. Capture, encoding and resource-cleanup failures preserve a prior sheet and attempt both encoder and browser cleanup. After cleanup, publication rechecks input identity and renames the staged PNG, replacing the destination entry without truncating other hardlinks or a symlink target. The shared Node output helper also rejects protected-input identities for render. Existing Node parent-path behavior is retained; the Python output symlink policy above applies to its own entry points. These checks do not prevent a hostile process from changing paths after the final check. Inspect any staging path reported by a cleanup failure before retrying.

Save a plan at `works/palette-card/plan.json` with `video: "../../inputs/source.mp4"` and clip `file: "../../outputs/palette-card/scene.mp4"`. Plan paths resolve from the plan file. After rendering final clips in `outputs/palette-card/`, create review files there:

```bash
python3 "$BROLL_SKILL_DIR/scripts/broll.py" preview \
  works/palette-card/plan.json outputs/palette-card/preview.mp4
```

Deliver scene HTML with its palette snapshot, fonts and required local assets in `outputs/<task>/scenes/<scene>/`. Check references after copying the bundle and render from that location. Final references must not depend on `works/`; `compare.html` may reference the source in `inputs/`. Preserve prior results on failure and report unresolved custom resources before claiming delivery complete. Engine atomic temporary files and OS temporary files keep their existing behavior.

`preview` checks its requested MP4 against protected source, plan and clip identities before creating a staging directory or encoding. It completes its media and review files in a temporary `.broll-preview-*` directory beside the output folder, then checks every final destination against those inputs before the first backup or publication write. Case aliases and hardlinks to protected inputs are refused. Preparation failures leave existing output files unchanged. Publication rechecks each destination; a validation or filesystem error triggers an attempt to restore previous files. An interruption or failed rollback retains the staging directory and any `.previous` backups; preserve them and inspect the outputs before retrying. Follow [media recovery](troubleshooting.md#media-and-delivery) when the error reports retained recovery files.

## Use the review pages

In `viewer.html`, background `Space` toggles playback and `ArrowLeft` / `ArrowRight` select clips. In `compare.html`, background `Space` toggles playback and the arrow keys seek by two seconds. These shortcuts apply outside interactive controls. Focused buttons, checkboxes, inputs and layout controls retain their own keyboard behavior. The compare seek slider handles its own two-second arrow step once; `Space` on that slider does not toggle playback.

Play/Pause follows actual media playback. While media loads or has failed, the viewer disables Play, Sound and Auto; compare disables Play, Sound and seeking until both active videos are ready. Viewer clip navigation and compare layout controls remain available. A failed load shows the affected media reference and a Retry button. Restore that local file or correct its reference before retrying; Retry reloads the same reference. Compare retries at the saved review time and waits for manual Play. Selecting another viewer clip or retrying clears the prior failure as the new load begins. These pages do not modify source files or substitute a remote resource.

If the browser blocks autoplay, the page requests a manual Play action and leaves Play available. A missing or unsupported media file remains a load error. See [review-page recovery](troubleshooting.md#review-pages) for those failures.

## Read the result

Except for help, stdout contains one JSON object. `status:completed` with exit code `0` establishes completion of that command. It does not establish human visual approval or completion of later steps. Errors contain `status:error`, `exit_code` and `message`; stderr contains detailed child diagnostics. Usage errors use `2`, timeout uses `124`, and other failures retain the child code or use `1`.

`BROLL_TIMEOUT_MS` sets the child-command deadline in milliseconds (default `600000`). At the deadline, the CLI requests cancellation with `SIGTERM` on POSIX and allows five seconds for cleanup. It then kills any remaining members of its owned POSIX process group and bounds diagnostic capture and reaping to roughly two more seconds. Timeout remains exit `124` even when cleanup completes. Stderr distinguishes completed renderer cleanup from forced or unconfirmed termination. Forced termination cannot run renderer cleanup; detached descendants and non-POSIX descendant cleanup are not guaranteed. Preserve any reported staging directory and follow [timeout recovery](troubleshooting.md#runtime-and-browser) before retrying.

Check the runtime profile in [versions.json](../scripts/runtime/versions.json). Use [setup.sh](../scripts/setup.sh) for an authorized local installation and [troubleshooting](troubleshooting.md) for bounded recovery. The direct Python and Node entry points remain available; their build/review-page font default is embedded.
