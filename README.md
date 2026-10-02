[![Input footage beside the broll-me pink card output](docs/assets/pink-demo-comparison.gif)](docs/assets/pink-demo.html)

[Play the comparison locally](docs/assets/pink-demo.html) · [Input MP4](docs/assets/pink-demo-input.mp4) · [Output MP4](docs/assets/pink-demo-output.mp4) · [Still image](docs/assets/pink-demo-comparison.png)

[English](README.md) · [한국어](README.ko.md)

# broll-me

Install one skill, then ask Codex or Claude Code to turn supplied words into motion-graphic B-roll. Choose a palette for cards, terminals, charts or transparent panels.

The comparison above uses a **6.607-second excerpt** and the current `card` template with `kkumil-pink`. The speaker remains visible for the first 2.436 seconds; a pink cutaway then illustrates the spoken point about pigment mixtures and treatment photos. The graphic represents an idea, not a product screen or customer record. See [sample details](docs/pink-demo.md).

![broll-me: one motion graphic, several palettes](skills/broll-me/reference/assets/broll-me-title.png)

## 1. Install with npx

Open a terminal in the project where you will use the skill. Install with the [skills CLI](https://github.com/vercel-labs/skills#install-a-skill). After the repository is published, run:

```bash
npx skills add soom-kang/broll-me --skill broll-me --agent codex claude-code
```

**Publication pending:** `soom-kang/broll-me` is the planned GitHub source. This work does not publish it or verify remote installation. Until publication, install from a downloaded checkout or an extracted ZIP:

```bash
# Replace this path with your checkout or extracted package folder.
npx skills add /path/to/broll-me --skill broll-me --agent codex claude-code
npx skills list --agent codex claude-code
```

Expect **one skill: `broll-me`**. Codex reads `.agents/skills/broll-me`; Claude Code reads `.claude/skills/broll-me`. The default installer keeps one canonical copy and links the host paths to it. You do not need a second motion skill. Local installation was verified with `skills` CLI `1.7.0`; see the [installation report](reports/NPX_DOCUMENTATION.md).

If `npx` is missing, provide Node.js and npm first. If the source cannot be fetched, use the local command above. Reload the host's skill list or start a new session if the command is not visible. See [installation and recovery](skills/broll-me/reference/workflow.md#1-install-one-skill) before replacing an existing installation.

## 2. Provide your video and subtitles

Put matching files in your project's `inputs/` folder, or give the agent readable paths. SRT and VTT both work. Notes are optional; the timed transcript is required for inserts. For a standalone clip, provide the wording or chart data in a file or in your request.

```text
inputs/source.mp4
inputs/source.srt
inputs/notes.json       # optional
```

The agent resolves the working project's absolute path before reading files. Without explicit input paths, it looks in `inputs/` and asks you to choose when multiple video/subtitle pairs match or a required input is missing. Supplied wording or data is enough for a standalone request without files.

It keeps plans, scene sources, inspections, drafts and logs in `works/<task>/`, and delivers final files in `outputs/<task>/`. It chooses a short English task name such as `palette-card`; an existing name in either folder gets a suffix such as `-02`. An explicit continuation reuses the named task. Your input and output paths take precedence. The agent preserves originals and previous results.

Skill installation adds instructions and engine files. Rendering also needs the pinned local runtime below. The agent checks it before rendering and can run project-local setup when the required binaries are available. It reports missing binaries or browser permissions instead of hiding the failure.

It reuses a runtime you specify. Otherwise it selects `works/.runtime/broll-me/` and sets `BROLL_RUNTIME` before browser checks. A failure in that runtime stops the affected step with its error.

| Component | Required version |
| --- | --- |
| Node.js | `24.21.0`, with npm |
| Python | `3.12.14` |
| FFmpeg / FFprobe | `9.0.2`; `libx264` and `prores_ks` encoders |
| Local modules | Playwright `1.62.1`, NumPy `2.3.5` |
| Chromium | Revision `1234`, version `151.0.7922.34` |

## 3. Copy a prompt

In **Codex**, use `$broll-me`:

```text
Use $broll-me with inputs/source.mp4 and its matching inputs/source.srt.
Read inputs/notes.json if it exists. Use the kkumil-pink palette and a card
cutaway about pigment mixtures and treatment photos. Keep the opening
speaker footage visible. Propose a short insertion slot from the subtitles,
then show a draft. Preserve the source and copy its audio into the preview.
Deliver final clips, preview.mp4, viewer.html, compare.html and TIMING.md
under outputs/palette-card so I can review them in this local workspace.
```

In **Claude Code**, use `/broll-me` with the same request:

```text
/broll-me
Use inputs/source.mp4 and its matching inputs/source.srt.
Read inputs/notes.json if it exists. Use the kkumil-pink palette and a card
cutaway about pigment mixtures and treatment photos. Keep the opening
speaker footage visible. Propose a short insertion slot from the subtitles,
then show a draft. Preserve the source and copy its audio into the preview.
Deliver final clips, preview.mp4, viewer.html, compare.html and TIMING.md
under outputs/palette-card so I can review them in this local workspace.
```

Replace the subject and paths with your own. To reproduce the comparison at the top, use the prepared sample and [exact sample prompt](docs/pink-demo.md#reproduce-the-sample). The existing full-length preview supplied as a reference is not presented as a current broll-me result.

For a standalone clip, ask: `Use $broll-me to make a 6-second Korean card with kkumil-pink. Title: 지난 시술 기록을 한눈에. Body: 색소 배합, 시술 사진.` In Claude Code, replace the invocation with `/broll-me`.

## 4. Review the draft

Confirm the proposed palette, wording and insertion time. Open the HTML review page, then check the speech timing, Korean text and transitions. The agent reuses decisions you already approved.

Draft captures one image per frame without motion blur. Final uses four subframes with motion blur. Both keep the same dimensions, FPS and frame count. Source-video work uses the inspected source specification; standalone defaults are 1920×1080, six seconds and 30 FPS.

SRT/VTT word timing is an estimate. Check it against playback. If text clips, shorten the wording or split the scene. If the browser or encoder fails, use the command and error in the agent's report to follow [recovery instructions](skills/broll-me/reference/troubleshooting.md).

## 5. Receive the result

Expect these files under `outputs/<task>/` for source-video inserts:

| Output | Use |
| --- | --- |
| MP4 clips / alpha MOV panels | Insert them in your editor; put transparent panels above the video |
| `preview.mp4` | Watch the inserts against the supplied footage |
| `viewer.html`, `compare.html` | Review individual clips and compare with the source |
| `TIMING.md` | Check each clip's insertion time and quoted speech |
| Scene HTML and `palette.resolved.json` | Edit the scene and inspect its resolved colors |

Scene HTML travels with its palette snapshot, shared `assets/broll-me-fonts/` folder and required local assets. The agent checks that final references do not depend on `works/`; `compare.html` may still reference the original in `inputs/`. It reports unresolved custom resources before claiming delivery complete. Select `--font-mode embedded` when you need one HTML file. Previews copy the input audio stream; unsupported source timing or MP4-incompatible audio causes an explicit failure. The skill does not normalize or transcode source audio as a fallback.

Follow the [English workflow](skills/broll-me/reference/workflow.md) or [한국어 사용 가이드](skills/broll-me/reference/workflow.ko.md) for setup, manual CLI commands, palette changes and archive installation.

<img src="skills/broll-me/reference/assets/workflow-en.png" width="480" alt="Install → provide inputs → run a prompt → review the draft → deliver final files">

1. Install one skill.
2. Provide inputs and select a palette.
3. Run the prompt in your host.
4. Review the draft and approve changes.
5. Receive final clips and review files.

## Choose a palette

Use one preset, or supply custom JSON with all 13 color roles. Choose either `--palette` or `--palette-file`; see [palette templates](skills/broll-me/reference/palettes.md).

| Preset | Canvas | Accent |
| --- | --- | --- |
| `warm-orange` (default) | `#E9E7E2` | `#FF5A1F` |
| `sage-cream` | `#F4F1E8` | `#5E7D64` |
| `editorial-blue` | `#F3F6FA` | `#2F5BEA` |
| `midnight-cyan` | `#111827` | `#67E8F9` |
| `kkumil-pink` | `#FFF0E6` | `#FF5C8D` |
| `onnimm-orange` | `#FCFBF8` | `#FF8A50` |

Palette changes affect the generated graphic while preserving its content, geometry, motion and timing. Source grading, photorealistic generation and final master editing remain outside the skill's scope.

## Maintainer checks

From this checkout, run `make check`, then `python3 scripts/package.py`. The [skill archive](dist/broll-me.skill), [ZIP](dist/broll-me.zip) and [hash manifest](dist/package-manifest.json) contain the installable skill. Demo footage, runtime files, evaluation records and private artwork stay outside those archives.

The new sample validates local installation and rendering. Earlier host evaluations remain separate: Claude Code completed two fixture requests; Codex stopped at Chromium permission errors and received no quality score. See [host evidence](reports/ENGINE_IMPROVEMENTS.md). Human playback approval remains a separate check.

Keep the [MIT license](skills/broll-me/LICENSE) and [font and icon notices](skills/broll-me/THIRD_PARTY_NOTICES.md) with redistributed copies. The workflow draws inspiration from [HyperFrames' motion-graphics skill](https://github.com/heygen-com/hyperframes/blob/main/skills/motion-graphics/SKILL.md); this identifies a workflow reference, not an engine code source.
