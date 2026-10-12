# Recover from a failed step

Read the failed command’s JSON `message`, exit code and stderr. Preserve the source and completed outputs. Report the command and actual error without printing credentials or the entire environment.

## Runtime and browser

Run `doctor` to distinguish missing files, version mismatches and browser permission failures. Use the fixed [runtime profile](../scripts/runtime/versions.json).

| Symptom | Next action | Stop condition |
| --- | --- | --- |
| Missing dependency | Check the runtime path and executable overrides; use authorized local setup | Installation needs authority beyond the current request |
| Version mismatch | Select matching executables using `BROLL_NODE`, `BROLL_PYTHON`, `BROLL_FFMPEG` or `BROLL_FFPROBE` | Matching binaries are unavailable; do not bypass checks |
| Browser blocked | Record the actual sandbox or permission error, including `doctor` output | Launch fails; do not switch versions or bypass host permissions |
| Timeout (`124`) | Read cancellation and cleanup diagnostics; inspect reported staging files and any surviving process from that run | Cleanup is forced, failed or unconfirmed; resolve the retained state before retrying |
| Skill undiscovered | Check project discovery links and their `SKILL.md`, then reload or start a session | Resolving a conflict would replace an existing installation |

A browser file with the right version can still fail to launch. Mark an environment block as `blocked`, distinct from a render-quality result. Timeout is a separate state with exit code `124`.

The CLI deadline defaults to ten minutes (`BROLL_TIMEOUT_MS=600000`). On POSIX it sends `SIGTERM`, allows five seconds for cleanup, then kills remaining members of the process group it created. Capture and reaping have a further bounded wait. The renderer closes FFmpeg and Chromium before publishing the video, then removes its temporary directory. Cancellation during resource cleanup keeps a previous output unchanged.

If stderr reports forced termination, failed cleanup or a staging path:

1. Preserve the prior output and reported `.broll-render-*` directory; check whether a process from that run is still alive.
2. Inspect the staged video and diagnostics. Completed renderer cleanup and exit `124` can occur together; `124` does not prove cleanup failed or succeeded.
3. Resolve any surviving process or retained files from that run before retrying. Do not treat a partial staged video as a completed render.

Forced termination cannot execute renderer cleanup. The owned POSIX process group does not cover descendants that detach into another group; descendant cleanup is also not guaranteed on non-POSIX hosts. Report cleanup as unconfirmed when the diagnostics do not establish it.

## Input and scene

Correct the field named in the error and rerun the failed stage. Keep the approved content and palette choices.

| Symptom | Next action | Stop condition |
| --- | --- | --- |
| Unknown or invalid palette | Check the preset ID, all 13 roles, hex format and contrast | Missing approved colors; do not select another preset without approval |
| Invalid SceneSpec or state reference | Correct the named field, reference, element or timing | Missing wording, data or timing needs user input |
| Build output aliases an input or is a symlink | Choose a fresh output directory; preserve the reported link and its target | Reusing the path would overwrite an input or follow an output link |
| Build batch destinations collide on the filesystem | Read both source/output pairs; change one output stem or build into separate directories | Case or normalization aliases still refer to one output entry; do not rerun the same batch |
| Palette writer lock exists | Check the active build/palette writer and retained recovery files | Do not remove an active or uninspected `.broll-palette.lock` |
| Text or cursor clipping | Inspect sampled beats; adjust wording, layout or framing | Two focused revisions leave a problem; report its location |
| Speaker moves into panel | Inspect the full movement range and choose a safe center or split the clip | No approved placement fits the footage |

## Fonts and HTML

Keep shared HTML and its adjacent `assets/broll-me-fonts/` together, including both OFL notices. For a single HTML file, rebuild with `--font-mode embedded`; the full notices appear in named CSS comments in the HTML source. Referenced media and custom assets still need separate delivery.

| Symptom | Next action | Stop condition |
| --- | --- | --- |
| Korean glyphs absent | Check Noto Sans KR, its OFL notice and shared asset paths | Font loading still fails; do not call the render correct |
| Font notice missing or empty | Restore the named OFL file from the skill source, then rebuild | The complete notice is unavailable; do not omit or invent the text |
| `Resource load failed` | Check the reported URL; include the required local file or replace a network dependency with a local or embedded resource | The resource still fails or cannot be verified; do not bypass network restrictions |
| Asset conflict | Select a fresh output directory | Continuing would overwrite different files or follow symlinks |

## Review pages

Read the visible media message and affected reference in `viewer.html` or `compare.html`. The pages keep Play/Pause in step with the actual video; a failed load does not appear to be playing.

| Symptom | Next action | Stop condition |
| --- | --- | --- |
| Media load error | Restore the file at the displayed local reference, or correct the reference and regenerate the pages; use Retry to reload | The file is unavailable or the browser cannot decode it; report the affected review as incomplete |
| Autoplay blocked | Activate Play manually | Manual playback still fails; inspect the media error rather than repeating Play |
| Page shortcut does not run from a control | Move focus to the page background for page shortcuts; use the focused control's own keys | Keep native button, checkbox, input and layout behavior; do not bypass it |

While media loads or has failed, the viewer disables Play, Sound and Auto; compare disables Play, Sound and seeking until both active videos are ready. Viewer Prev/Next and the clip list remain usable; compare layout selection remains usable. Retry reloads the existing local reference without modifying source files. Compare restores the saved review time and waits for manual Play. Keep the original source and clip paths; no cloud fallback is attempted.

When an active compare video starts loading or waits for data, both active videos pause and the timeline retains the master video's review time. Once both are ready, press Play to resume. Loading events from the unused layout do not stop the active pair. A loading message alone is not a media error; Retry appears with the failed reference.

## Media and delivery

Inspect the FFmpeg error and output metadata. Retry the same cause at most once, after a focused correction. Keep previous files and do not use cloud rendering or model APIs as a fallback.

| Symptom | Next action | Stop condition |
| --- | --- | --- |
| Render or composite failure | Read stderr and inspect input/output specs | The same cause persists or new installation/permission is required |
| Node `beats` output shares the HTML input's identity | Choose a separate PNG file; preserve the reported source and hardlink | Do not unlink or rename the input to bypass the guard |
| Beat cleanup or publication failed | Check whether the error says the sheet was published; preserve and inspect any reported `.broll-beats-*` staging path | Cleanup or output state is unresolved; inspect before retrying |
| Composite, inspection or review output is a symlink/non-regular file, or a parent is not a directory | Select a regular file destination under real directories; preserve the blocked entry and any link target | Do not redirect writes through the rejected path |
| Media output shares a protected input's filesystem identity | Choose a separate output file; case aliases and hardlinks to a protected source, plan, clip or preview are refused as applicable | Do not rename only the letter case or unlink the protected input to bypass the check |
| Preview publication failure | Read stderr; check whether previous files were restored or recovery files were retained | Restoration failed or publication was interrupted; inspect recovery files before retrying |
| Nonzero stream start or audio tail | Inspect start times and durations; propose a separate compatible copy | No approval for normalization or audio editing |
| MP4-incompatible audio | Report the codec; request an approved compatible input copy or separate delivery | No approval for audio transcoding |
| Alpha looks black | Verify MOV alpha and composite over footage; players may show a black backing | Alpha is absent; do not label the clip transparent |
| Package rejection | Correct the named relative path and keep runtime/private media outside the skill | Continuing requires weakening package validation |

Preview checks its requested MP4 before staging, then checks all final destinations against protected source, plan and clip identities before creating any backup. It prepares the complete bundle before publishing files individually. Preparation failure leaves existing output files unchanged; a publication validation or filesystem error triggers a rollback attempt. Interrupted publication or a failed rollback can leave a partial output bundle. If stderr reports `recovery files retained at ...`, use these steps:

1. Preserve the reported `.broll-preview-*` directory and its `.previous` backups beside the output folder.
2. Inspect the output files, staged files and backups to establish which files were published or moved.
3. Restore the required previous files before retrying, and report any unresolved recovery failure.

Do not delete retained recovery files or rerun preview before inspecting them and completing any needed recovery.

Build uses `.broll-palette.lock` to coordinate HTML and snapshot publication. If an HTML publication fails, a snapshot newly created by that build is rolled back; an existing compatible snapshot is retained. A rollback or cleanup failure reports retained `.broll-build-*` or `.broll-palette-*` files and the lock location. Cleanup can fail after coherent outputs have already been published.

Batch destination preflight uses a disposable `.broll-build-preflight-*` directory on the target filesystem. It removes temporary name reservations before writing final HTML, fonts or the palette. A collision leaves existing deliverables and a missing final output directory unchanged. If creating or cleaning the probe fails, resolve the reported filesystem error before retrying; do not bypass the check with a guessed case rule.

1. Preserve the reported staging files, snapshot and lock; check whether a writer is still running.
2. Inspect the prior HTML, staged HTML and palette to identify completed publication or pending recovery. Do not overwrite an unexpected writer's snapshot.
3. Complete the required recovery before removing only the inspected lock or staging files. Retry only after the active writer has finished and the output state is understood.

A lock left by an interrupted process is not automatically considered stale or deleted. The build does not promise multi-file atomic visibility, a batch transaction or automatic recovery after sudden OS exit.

A new retry runtime still needs a separate output directory. When recovery stops, report the failed command, reason, preserved files and one required next action. Do not label unrun checks as passed.
