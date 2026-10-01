# Write a scene template

Save one SceneSpec JSON and build it with the common CLI. Reuse the same JSON in separate output folders to compare palettes while keeping content, geometry and timing.

```json
{
  "schema_version": 1,
  "template": "card",
  "title": "오늘의 설명",
  "body": "제공한 내용을 카드로 보여줍니다.",
  "width": 1920,
  "height": 1080,
  "duration": 6
}
```

## Select the content

Choose the template that fits your supplied message. Terminal lines display text and do not execute commands.

| Template | Required content | Treatment |
| --- | --- | --- |
| `card` | `title`, `body` | Card morph on a canvas |
| `terminal` | `title`, `lines` string array | Inverse surface with time-based typing |
| `chart` | `title`, `bars` containing `label` and `value` | Nonnegative supplied values, widths relative to the maximum |
| `panel` | `title`, `body` | `bg:null`; transparent MOV output |

Common required fields are `schema_version:1`, `template` and `title`. Optional fields are `subtitle`, `width`, `height`, `duration` and `center:[x,y]`. Standalone defaults are 1920×1080 and six seconds, with CLI rendering at 30 FPS. For inserts, copy the actual dimensions and FPS from inspection. Center coordinates use pixels; inspect footage to choose a safe position.

Select the palette through `--palette` or `--palette-file`, outside the SceneSpec. Use supplied data for charts; without values, choose a card. Label approved illustrative values in the plan. For custom morphs, use HTML fragments with [Engine API](engine-api.md).

## Build and check

Set `BROLL_SKILL_DIR` and `BROLL_RUNTIME` as shown in [the workflow](workflow.md). Save your JSON as `card.json` before running these commands.

```bash
python3 "$BROLL_SKILL_DIR/scripts/broll.py" build motion/pink \
  --scene card.json --palette kkumil-pink
python3 "$BROLL_SKILL_DIR/scripts/broll.py" check motion/pink/card.html
python3 "$BROLL_SKILL_DIR/scripts/broll.py" render \
  motion/pink/card.html motion/out/card.mp4 --fps 30
```

Missing content, invalid geometry, duration or chart values cause failure before output. The builder escapes wording as text. If `check` reports text overflow, shorten the wording, adjust layout or split the message. Review typography and motion yourself before delivery; do not omit approved content without approval to pass a check.
