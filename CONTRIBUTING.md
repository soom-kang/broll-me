# Contributing

## Report a problem

Include the failing command, its error output, your host (Codex or Claude Code), runtime versions and the smallest input that reproduces the issue. Remove credentials, private footage and customer information before sharing a report.

For setup or rendering failures, start with [troubleshooting](skills/broll-me/reference/troubleshooting.md). A browser permission failure is an environment block, not a render-quality result.

## Check changes

Run these commands from the repository root:

```bash
make check
python3 scripts/package.py
```

`make check` runs package validation, Python unit tests and Node tests. Packaging writes `broll-me.skill`, `broll-me.zip` and `package-manifest.json` to `dist/` and checks archive contents and extraction.

Rendering changes also need the [pinned runtime](skills/broll-me/scripts/runtime/versions.json), scene checks and playback review. Report local CLI results, actual host execution and human approval separately.

For review-page changes, check background shortcuts, focused native controls and the compare seek slider in the browser. Include a missing media reference and a successful local Retry; confirm that clip navigation or layout selection still works while playback is unavailable. Check that active compare loading pauses the pair and restores manual Play, while inactive loading does not stop playback. Media-error assertions must wait for Retry and the current failed reference, rather than a loading message. Use the existing test suites and keep browser verification within the affected behavior.

## Keep documentation focused

- `README.md` and `README.ko.md`: what the skill does, why it helps, the before-and-after preview and a quick start
- `skills/broll-me/reference/workflow.md` and `workflow.ko.md`: installation, requirements and the complete user workflow
- Other files in `skills/broll-me/reference/`: palettes, CLI, scene templates, engine API and troubleshooting
- `docs/`: sample details and reproduction instructions
- `reports/`: dated verification evidence

Keep the English and Korean versions aligned when editing paired documents. Preserve the README's before-and-after GIFs and direct MP4 links. Link to detailed instructions rather than copying them into several places.

## Packaging and licenses

The portable skill lives in `skills/broll-me/`. Demo footage, local runtimes, evaluation records and private artwork stay outside the skill archives. Public release files are available from [GitHub Releases](https://github.com/soom-kang/broll-me/releases/tag/v0.8.0-beta.2).

Keep `SKILL.md` frontmatter within the portable subset checked by `scripts/validate_package.py`: top-level `name`, `description` and optional `license` are single-line strings; optional `metadata` is `{}` or a flat map with two-space indentation and simple scalar values. Use `name: broll-me` and a description of 1–1024 characters without angle brackets. Quote text containing `: ` or ` #`, or text that looks like a boolean, number or null. Lists, nested maps, multiline values, tags and anchors are unsupported. Both package backends run this check before creating archives; installing PyYAML does not widen the accepted format.

Retain the exact [MIT license](LICENSE) and [third-party notices](skills/broll-me/THIRD_PARTY_NOTICES.md), including bundled font and icon licenses. See [package sources and scope](skills/broll-me/reference/provenance.md) for acknowledgments and asset provenance.

When updating the root `LICENSE`, keep `skills/broll-me/LICENSE` byte-identical so the portable Skill retains its own license and internal references.

Generated embedded-font HTML carries the full OFL notices as named CSS comments; shared-font HTML needs its adjacent font and notice files. Preserve those notices when changing font delivery. Referenced media and custom assets still need their own files and applicable notices.

## Verification history

- [Current checkout QA, 2026-10-12](reports/QA-2026-10-12.md) and [local JIRA-style tickets](reports/QA-TICKETS-2026-10-12.md): the final cumulative review including QA-014/015 retains all fifteen locally resolved findings and found no additional supported defect. Current CLI guards, normal batch, existing suites, four browser views and exact-source temporary archives passed; two case-sensitive fixtures remain skipped. The Node identity/cleanup/rename boundary and temporary batch-probe writes before final artifacts remain documented. This review changed only QA records and this history; source, tests and prior artifacts were preserved. These tickets have not been filed in an external tracker.
- [Installation and sample-render report](reports/NPX_DOCUMENTATION.md)
- [Engine improvements and host-execution evidence](reports/ENGINE_IMPROVEMENTS.md)

These are historical records with their own dates and limits. The earlier host evaluation completed two Claude Code fixture requests; Codex was blocked by Chromium permissions and received no quality score. A later local render does not change that host-evaluation result.
