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

## Keep documentation focused

- `README.md` and `README.ko.md`: what the skill does, why it helps, the before-and-after preview and a quick start
- `skills/broll-me/reference/workflow.md` and `workflow.ko.md`: installation, requirements and the complete user workflow
- Other files in `skills/broll-me/reference/`: palettes, CLI, scene templates, engine API and troubleshooting
- `docs/`: sample details and reproduction instructions
- `reports/`: dated verification evidence

Keep the English and Korean versions aligned when editing paired documents. Preserve the README's before-and-after GIFs and direct MP4 links. Link to detailed instructions rather than copying them into several places.

## Packaging and licenses

The portable skill lives in `skills/broll-me/`. Demo footage, local runtimes, evaluation records and private artwork stay outside the skill archives. Public release files are available from [GitHub Releases](https://github.com/soom-kang/broll-me/releases/tag/v0.8.0-beta.2).

Retain the exact [MIT license](skills/broll-me/LICENSE) and [third-party notices](skills/broll-me/THIRD_PARTY_NOTICES.md), including bundled font and icon licenses. See [package sources and scope](skills/broll-me/reference/provenance.md) for acknowledgments and asset provenance.

## Verification history

- [Installation and sample-render report](reports/NPX_DOCUMENTATION.md)
- [Engine improvements and host-execution evidence](reports/ENGINE_IMPROVEMENTS.md)

These are historical records with their own dates and limits. The earlier host evaluation completed two Claude Code fixture requests; Codex was blocked by Chromium permissions and received no quality score. A later local render does not change that host-evaluation result.
