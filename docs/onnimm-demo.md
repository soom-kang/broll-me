# ONNIMM before-and-after sample

[English](onnimm-demo.md) · [한국어](onnimm-demo.ko.md) · [Back to README](../README.md)

This sample adds short `onnimm-orange` motion graphics to a café conversation. The graphics explain treatment records, consent history and access scopes. They are illustrative, not product screens or customer records.

## Watch the comparison

- [Input MP4](assets/onnimm-context-input.mp4)
- [Output MP4](assets/onnimm-context-output.mp4)
- [Synchronized comparison page](assets/onnimm-context.html)
- [All 7 B-roll scenes · 42.509 seconds](assets/onnimm-highlights.html)

Open the HTML page locally and keep the MP4s in the same folder. Both videos play together; only the output plays sound. The GIFs embedded in the README play independently and may start a moment apart.

The output shows the speaker for 5.005 seconds, a consent-history graphic for 7.841 seconds, then the speaker for another 5.005 seconds.

## Sample specifications

| Item | Value |
| --- | --- |
| Source frames | 1972–2506, inclusive |
| Source time range | 01:05.799–01:23.650 |
| Comparison duration | 17.851 seconds |
| Input and output MP4 | 535 frames each; 1920×1080; `30000/1001` FPS |
| README GIFs | Same range; 480×270; 10 FPS; silent |
| Palette | `onnimm-orange` |

The range includes the fourth insert from a supplied broll-me production preview. This documentation sample was extracted from that preview; it is not a new host-execution test.

Both excerpts use the same speech from the original video, encoded to AAC for the cut. The source video and supplied preview are unchanged. See the [frame ranges and hashes](assets/onnimm-context.json) and the [highlight metadata](assets/onnimm-highlights.json).

## Try it with your footage

Install broll-me and prepare the runtime using the [user guide](../skills/broll-me/reference/workflow.md). Put your footage and matching subtitles in the working project's `inputs/` folder, then use this in Codex:

```text
Use $broll-me with inputs/source.mp4 and its matching inputs/source.srt.
Read inputs/notes.json if it exists. Use the onnimm-orange palette for short
B-roll cutaways about treatment records, consent history and access scopes.
Keep the speaker visible between inserts. Propose the wording and insertion
slots from the subtitles, then show a draft. Preserve the source and copy
its audio into the preview.
Deliver final clips, preview.mp4, viewer.html, compare.html and TIMING.md
under outputs/onnimm-cafe-broll.
```

In Claude Code, replace `$broll-me` with `/broll-me`. Change the subject and paths to match your footage. This request follows the sample's workflow; it does not recreate its exact scene layout.

For a sample with scene sources and manual reproduction commands, see the [pink card example](pink-demo.md).
