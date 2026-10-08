![broll-me: one motion graphic, several palettes](skills/broll-me/reference/assets/broll-me-title.png)

[English](README.md) · [한국어](README.ko.md)

# broll-me

**A Codex and Claude Code skill for creating motion-graphic B-roll.**

Turn your wording, data or subtitled footage into animated cards, terminals, charts and transparent panels. Get editable HTML scenes, rendered clips and review files for your video edit.

## Why broll-me

An interview or explainer often needs a visual to make a spoken idea clear. Making that insert means choosing the right words, designing a graphic, animating it and lining it up with the speech. Repeating those steps for each insert adds work, especially when the style needs to stay consistent.

broll-me brings those steps into one prompt-driven workflow: propose a scene and its timing, build it with a chosen palette, review a draft and render the approved result. The editor keeps control of the wording, placement and final edit.

## Before and after

| Input · original footage                                                                                                           | Output · broll-me                                                                                                                                                     |
| ---------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [![Input preview: the café speaker throughout the passage](docs/assets/onnimm-context-input.gif)](docs/assets/onnimm-context.html) | [![Output preview: the same speaker, then a consent-history graphic, then the speaker again](docs/assets/onnimm-context-output.gif)](docs/assets/onnimm-context.html) |
| [Watch input MP4](docs/assets/onnimm-context-input.mp4)                                                                            | [Watch output MP4](docs/assets/onnimm-context-output.mp4)                                                                                                             |

Both show the same 17.851-second passage. The output adds a short consent-history graphic, then returns to the speaker. It is an illustrative graphic, not a product screen or customer record.

Open the [comparison page](docs/assets/onnimm-context.html) locally with its MP4s to play both in sync; only the output plays sound. GitHub's GIFs play independently. [See all 7 B-roll scenes](docs/assets/onnimm-highlights.html) or read the [sample details](docs/onnimm-demo.md).

## Quick start

### 1. Install

Run this in the project where you will use the skill. Node.js and npm are needed for `npx`.

```bash
npx skills add https://github.com/soom-kang/broll-me/tree/v0.8.0-beta.2 --skill broll-me --agent codex claude-code
```

This installs the **`v0.8.0-beta.2` beta**. See the [release notes](https://github.com/soom-kang/broll-me/releases/tag/v0.8.0-beta.2) for its verification scope. Rendering also needs the [pinned local runtime](skills/broll-me/reference/workflow.md#2-provide-inputs-and-choose-a-palette); installing the skill alone does not prepare it.

### 2. Ask for a clip

In Codex:

```text
Use $broll-me to make a 6-second card with the kkumil-pink palette.
Title: 지난 시술 기록을 한눈에
Body: 색소 배합, 시술 사진
Show me a draft, then deliver the approved final MP4 and editable scene.
```

In Claude Code, replace `$broll-me` with `/broll-me`. For inserts in an existing video, provide the footage and its matching SRT/VTT, then ask for suggested wording and insertion times. See the [full prompt examples](skills/broll-me/reference/workflow.md#3-run-a-prompt).

### 3. Review and use

Check the draft's wording, readability and timing before requesting the final render. Final files go in `outputs/<task>/`; drafts and working files go in `works/<task>/`.

- **Clips:** MP4 for full-frame graphics; ProRes 4444 MOV for transparent panels
- **Editable sources:** scene HTML, resolved palette, fonts and required local assets
- **Video-insert review:** `preview.mp4`, `viewer.html`, `compare.html` and `TIMING.md`

Keep each HTML bundle with its assets. See [delivery details](skills/broll-me/reference/workflow.md#5-receive-final-files) before moving or sharing it. If preview delivery fails, follow the [recovery instructions](skills/broll-me/reference/troubleshooting.md#media-and-delivery) before retrying.

## Documentation

- [Installation and user guide](skills/broll-me/reference/workflow.md): requirements, input files, prompts, draft review and delivery
- [Palettes](skills/broll-me/reference/palettes.md): six presets and custom colors
- [CLI reference](skills/broll-me/reference/usage.md) · [Scene templates](skills/broll-me/reference/scenes.md) · [Engine API](skills/broll-me/reference/engine-api.md)
- [Examples](docs/onnimm-demo.md) · [Reproduce the pink card sample](docs/pink-demo.md)
- [Troubleshooting](skills/broll-me/reference/troubleshooting.md)
- [Contributing and verification](CONTRIBUTING.md)

## Scope and limitations

broll-me creates HTML-based motion graphics. Photorealistic video generation, speech recognition, source color grading and final master editing are outside its scope.

Subtitle-derived word timing and speaker-position estimates need playback review. Preview composition copies the source audio stream and rejects unsupported timing or codecs; it does not silently transcode audio. A successful technical check does not replace editorial approval.

## License

[MIT](LICENSE). Keep the license and [third-party font and icon notices](skills/broll-me/THIRD_PARTY_NOTICES.md) with redistributed copies. See [sources and acknowledgments](skills/broll-me/reference/provenance.md) for workflow and asset references.
