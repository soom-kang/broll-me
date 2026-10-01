# Reproduce the pink comparison

Open [the comparison page](assets/pink-demo.html), then press **Play both**. It plays the input and output together with audio from the output only. GitHub displays the README GIF; download the sample folder to use the local HTML player.

[English](pink-demo.md) · [한국어](pink-demo.ko.md)

## What the sample shows

The current broll-me skill generated a `card` using `kkumil-pink`. The speaker remains visible until 2.436 seconds. The card then illustrates pigment mixtures and treatment photos. It is explanatory artwork, not an actual product screen or customer record.

| Property | Value |
| --- | --- |
| Original range | Frame 1592 through 1789; approximately 00:53.120–00:59.726 |
| Prepared excerpt | 198 frames; 6.6066 seconds |
| Video specification | 1920×1080; `30000/1001` FPS; H.264 MP4 |
| Cutaway slot | Frame 73 through 197 of the excerpt; 2.435767–6.6066 seconds |
| Graphic | Card template; `kkumil-pink`; 125 frames; final rendering |

The source and its matching SRT supplied the wording. The existing full-length preview served as a reference for selecting the passage. This new output was rendered through the skill installed by `npx skills add`; it is not a crop of that historical output.

The original video was unchanged. Excerpt preparation encoded video and AAC audio once to cut the requested range and reset timestamps. The preview then copied the excerpt's audio stream without normalizing or transcoding it. SRT cues were clipped and shifted to the excerpt; the card keeps the spoken captions visible. The README GIF is silent, scaled to 1024 pixels wide and sampled at 10 FPS. Use MP4 for the original sample frame rate.

## Reproduce the sample

Install broll-me in a working project. From this checkout, copy `docs/assets/` to the same relative location if your project is elsewhere. Start with `$broll-me` in Codex or `/broll-me` in Claude Code, then paste:

```text
Use docs/assets/pink-demo-input.mp4 and docs/assets/pink-demo.srt.
Use docs/assets/pink-demo-plan.json as the approved insertion plan.
The approved palette is kkumil-pink and the template is card.
Keep the first 2.435767 seconds of speaker footage visible.
In the 2.435767–6.6066-second slot, show:
Title: 지난 시술 기록을 한눈에
Subtitle: 설명용 그래픽
Body: 색소 배합 / 시술 사진
Preserve the spoken captions while the full-frame card is visible.
Use the inspected 1920×1080 and 30000/1001 FPS specification.
Reuse a ready runtime, or prepare a project-local runtime if needed.
Show a draft and deliver final clips, preview.mp4, viewer.html,
compare.html, TIMING.md and the resolved palette under motion/pink-demo/out.
Keep input files unchanged and copy the excerpt audio into the preview.
```

This prompt reproduces the content and insertion plan. An agent may author a different layout. To reproduce the supplied layout, use the [scene JSON](assets/pink-demo-scene.json) and [captioned fragment](assets/pink-demo-card.html). The fragment compiles the card template, adds the supplied captions and adjusts Korean text boxes; it does not alter the engine.

After the skill is installed and the pinned runtime is ready, the exact rendering commands are:

```bash
export BROLL_SKILL_DIR="$PWD/.agents/skills/broll-me"
export BROLL_RUNTIME="$PWD/motion"
python3 "$BROLL_SKILL_DIR/scripts/broll.py" doctor
python3 "$BROLL_SKILL_DIR/scripts/broll.py" build motion/pink-demo/built \
  docs/assets/pink-demo-card.html --palette kkumil-pink
python3 "$BROLL_SKILL_DIR/scripts/broll.py" check \
  motion/pink-demo/built/pink-demo-card.html
python3 "$BROLL_SKILL_DIR/scripts/broll.py" render \
  motion/pink-demo/built/pink-demo-card.html motion/pink-demo/card.mp4 \
  --fps 30000/1001 --quality final
```

Expect the checked HTML, shared fonts, palette snapshot and 125-frame card. Correct runtime errors before retrying. For preview, copy the supplied plan to `motion/pink-demo/plan.json`, change its `video` to `../../docs/assets/pink-demo-input.mp4` and its clip `file` to `card.mp4`, then run:

```bash
python3 "$BROLL_SKILL_DIR/scripts/broll.py" preview \
  motion/pink-demo/plan.json motion/pink-demo/out/preview.mp4
```

Expect a 198-frame preview and review files. Relative paths resolve from the plan. If timing or audio validation fails, keep the input and correct the plan or provide an approved compatible copy.

## Review the files

1. Play [input](assets/pink-demo-input.mp4) and [output](assets/pink-demo-output.mp4).
2. Inspect the [comparison](assets/pink-demo.html) and [individual clip viewer](assets/viewer.html).
3. Read [timing](assets/TIMING.md) and the [palette snapshot](assets/pink-scene/palette.resolved.json).
4. Open the [editable built scene](assets/pink-scene/pink-demo-card.html) with its adjacent font assets.
5. Check [technical verification](../reports/NPX_DOCUMENTATION.md); human listening and playback approval remain pending.
