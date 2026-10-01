---
name: broll-me
description: "Create motion-graphic B-roll cutaways and transparent panels using a chosen brand palette. Use for video inserts timed to SRT/VTT, palette changes that preserve motion, Korean graphic cards, terminal or chart animations, and standalone B-roll scene briefs. Excludes photorealistic video generation, source color grading, and general video editing."
license: MIT
---

# broll-me

Create a local motion graphic from the user’s brief. After project-local installation with `npx skills add`, invoke `$broll-me` in Codex or `/broll-me` in Claude Code. Both hosts use this one skill, the same CLI, scene templates and palette resolver. Start with [the workflow](reference/workflow.md) for installation and prompt examples; [한국어 사용 가이드](reference/workflow.ko.md) covers the same steps.

## Gather the inputs

Require a scene purpose and supplied wording or data. For source-video inserts, also require readable footage and its matching SRT/VTT transcript. Without footage, create a standalone clip and omit source inspection and composition claims.

Reuse the user’s palette and approvals. Default to `warm-orange`, medium density, six seconds, 1920×1080 and 30 FPS for standalone work. For inserts, use inspected source dimensions and FPS. Optional inputs include full-frame/panel treatment, clip duration, safe areas and insertion slots.

Use this skill for HTML-based motion graphics. Photorealistic generation, source grading, speech recognition, final master editing, posting and external messages fall outside its scope. A request to recolor real skin or lips needs a different workflow; offer palette changes to the graphic itself.

## Complete five steps

1. Prepare the inputs and runtime. Find the actual folder containing this `SKILL.md`; use it as `BROLL_SKILL_DIR` instead of assuming a source checkout. Keep output and runtime under the calling project. Reuse a ready runtime and run `scripts/broll.py doctor` before browser work. For an authorized local rendering request, if the pinned binaries are available but project modules or Chromium are missing, run `scripts/setup.sh` for the project-local runtime, then repeat doctor. Read [CLI usage](reference/usage.md) for executable overrides. Report missing binaries or permissions with the exact command and recovery action. Do not install system tools, change global settings or bypass version checks.
2. Inspect source footage when supplied, then select the palette and slots. Open the contact sheet yourself. Word timing from SRT/VTT is estimated, and speaker boxes are heuristics. Present clip in/out times, quoted speech, motion, palette and treatment. Confirm new creative decisions when required, and reuse an already approved plan. See [Palette templates](reference/palettes.md) for the six presets and custom JSON.
3. Author one message per clip. Use [Scene templates](reference/scenes.md) for card, terminal, chart and panel JSON. Read [Engine API](reference/engine-api.md) only for custom morphs or fragments. Build with either `--scene` or HTML fragments, and either `--palette` or `--palette-file`. Retain `palette.resolved.json`; use separate output folders to compare palettes.
4. Check and render within the approved scope. Run `check`, capture key beats and inspect transitions, Korean glyphs, contrast and framing. Use draft for review and final for delivery. Render full-frame scenes to MP4 and transparent `bg:null` panels to alpha MOV. A successful draft does not establish final delivery. Read [Recovery instructions](reference/troubleshooting.md) on failure.
5. Review and deliver. For supplied footage, use the approved plan with `preview` to create a separate preview, `viewer.html`, `compare.html` and `TIMING.md`. Preserve the source and its audio. Deliver shared-font HTML with its adjacent font folder, or select embedded mode when a single HTML is required. Report output files, palette, checks, blocked work and remaining human review.

## Apply editorial judgment

Use a 3–10-second cutaway where it explains the speech. Keep the speaker visible for the opening hook and personal or emotional statements. Start with about two seconds of face footage between cutaways, then adjust to the actual edit. For a panel, avoid the speaker’s full movement range across the slot.

Keep one continuous shape where the message supports it, and align cursor actions to speech beats. Check framing after zooms. Split long wording into states instead of shrinking it until unreadable. Record illustrative content in plan notes. Do not invent results, prices, claims or quotations, and do not recolor factual screenshots, logos or source subjects.

## Stop and report

Correct invalid input rather than guessing missing values. Preserve outputs on failure. Use a focused retry only when the cause has changed; repeated failures need the command, actual error and required next input. Do not switch to cloud rendering, model APIs or external uploads as an automatic fallback.

Finish when the requested outputs pass specification and playback checks, with palette snapshots and applicable review files delivered. Distinguish local verification, actual host execution and human approval. Without footage, do not claim source synchronization or audio preservation. The preview supports insertion review; the editor still confirms speech timing, transitions and audio mix.

## Recognize the requests

- `Use $broll-me to create a 6-second Korean card with kkumil-pink.` Create the requested standalone graphic.
- `/broll-me source.mp4 transcript.vtt; use an onnimm-orange panel and retain audio. Deliver all clips with a local HTML review page.` Inspect the supplied files and follow the source-video path.
- `Make my real skin pink with this palette.` Explain the scope and offer graphic palette changes.

Keep [MIT](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md) in redistributed copies. [Package sources and scope](reference/provenance.md) records palette and font references.
