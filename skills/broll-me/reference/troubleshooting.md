# Recover from a failed step

Read the failed command’s JSON `message`, exit code and stderr. Preserve the source and completed outputs. Report the command and actual error without printing credentials or the entire environment.

## Runtime and browser

Run `doctor` to distinguish missing files, version mismatches and browser permission failures. Use the fixed [runtime profile](../scripts/runtime/versions.json).

| Symptom | Next action | Stop condition |
| --- | --- | --- |
| Missing dependency | Check the runtime path and executable overrides; use authorized local setup | Installation needs authority beyond the current request |
| Version mismatch | Select matching executables using `BROLL_NODE`, `BROLL_PYTHON`, `BROLL_FFMPEG` or `BROLL_FFPROBE` | Matching binaries are unavailable; do not bypass checks |
| Browser blocked | Record the actual sandbox or permission error, including `doctor` output | Launch fails; do not switch versions or bypass host permissions |
| Skill undiscovered | Check project discovery links and their `SKILL.md`, then reload or start a session | Resolving a conflict would replace an existing installation |

A browser file with the right version can still fail to launch. Mark an environment block as `blocked`, distinct from a render-quality result. Timeout is a separate state with exit code `124`.

## Input and scene

Correct the field named in the error and rerun the failed stage. Keep the approved content and palette choices.

| Symptom | Next action | Stop condition |
| --- | --- | --- |
| Unknown or invalid palette | Check the preset ID, all 13 roles, hex format and contrast | Missing approved colors; do not select another preset without approval |
| Invalid SceneSpec or state reference | Correct the named field, reference, element or timing | Missing wording, data or timing needs user input |
| Text or cursor clipping | Inspect sampled beats; adjust wording, layout or framing | Two focused revisions leave a problem; report its location |
| Speaker moves into panel | Inspect the full movement range and choose a safe center or split the clip | No approved placement fits the footage |

## Fonts and HTML

Keep shared HTML and its adjacent `assets/broll-me-fonts/` together. For a single HTML file, rebuild with `--font-mode embedded`.

| Symptom | Next action | Stop condition |
| --- | --- | --- |
| Korean glyphs absent | Check Noto Sans KR, its OFL notice and shared asset paths | Font loading still fails; do not call the render correct |
| Asset conflict | Select a fresh output directory | Continuing would overwrite different files or follow symlinks |
| Missing review media | Preserve the source/clip paths referenced by the pages | Referenced media is unavailable; share the preview with that limit |

## Media and delivery

Inspect the FFmpeg error and output metadata. Retry the same cause at most once, after a focused correction. Keep previous files and do not use cloud rendering or model APIs as a fallback.

| Symptom | Next action | Stop condition |
| --- | --- | --- |
| Render or composite failure | Read stderr and inspect input/output specs | The same cause persists or new installation/permission is required |
| Nonzero stream start or audio tail | Inspect start times and durations; propose a separate compatible copy | No approval for normalization or audio editing |
| MP4-incompatible audio | Report the codec; request an approved compatible input copy or separate delivery | No approval for audio transcoding |
| Alpha looks black | Verify MOV alpha and composite over footage; players may show a black backing | Alpha is absent; do not label the clip transparent |
| Package rejection | Correct the named relative path and keep runtime/private media outside the skill | Continuing requires weakening package validation |

A new retry runtime still needs a separate output directory. When recovery stops, report the failed command, reason, preserved files and one required next action. Do not label unrun checks as passed.
