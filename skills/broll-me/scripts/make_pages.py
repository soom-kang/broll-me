"""Write local-font review pages and the editor timing sheet.
Usage: python3 make_pages.py motion/plan.json motion/out/preview.mp4
"""
import argparse
import html
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote
from media import MediaError, atomic_output, binary, input_file, load_plan, probe, run

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
sys.path.insert(0, str(TEMPLATES.parent / "engine"))
from fonts import font_css


def script_json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def fill_template(template, replacements):
    """Replace only original template markers, never markers in inserted data."""
    pattern = "|".join(re.escape(key) for key in sorted(replacements, key=len, reverse=True))
    return re.sub(pattern, lambda match: replacements[match.group(0)], template)


def local_fonts(output_dir=".", font_mode="embedded"):
    return font_css(output_dir, font_mode)


def web_path(path, outdir):
    return quote(Path(os.path.relpath(path, outdir)).as_posix(), safe="/")


def fmt(value):
    return f"{int(value // 60)}:{value % 60:05.2f}"


def markdown_cell(value):
    return str(value).replace("\n", " ").replace("\r", " ").replace("|", "\\|")


def write_pages(plan_path, preview_path, font_mode="embedded"):
    plan_path = input_file(plan_path)
    plan, source, source_info, clips = load_plan(plan_path)
    preview = input_file(preview_path)
    if preview == source or preview in {c["path"] for c in clips}:
        raise MediaError("Preview must be a separate output file")
    outdir = preview.parent
    preview_info = probe(preview)
    duration = preview_info["duration"]
    if abs(duration - source_info["duration"]) > 2 / float(source_info["rate"]):
        raise MediaError("Preview duration differs from source")
    if preview_info["rate"] != source_info["rate"] or (preview_info["width"], preview_info["height"]) != (source_info["width"], source_info["height"]):
        raise MediaError("Preview dimensions or FPS differ from source")
    title = plan.get("title", "Video")
    pages = []
    input_paths = [plan_path, source, preview, *(c["path"] for c in clips)]
    for index, clip in enumerate(clips, 1):
        path = clip["path"]
        if clip["kind"] == "panel":
            panel_preview = outdir / (f"{index:02d}-" + path.stem + "_preview.mp4")
            info = clip["info"]
            with atomic_output(panel_preview, inputs=input_paths, suffix=".mp4") as temporary:
                run([binary("ffmpeg"), "-v", "error", "-nostdin", "-y", "-f", "lavfi", "-i", f"color=black:s={info['width']}x{info['height']}:r={info['fps']}:d={info['duration']}", "-i", str(path), "-filter_complex", "[0:v][1:v]overlay=shortest=1:format=auto,format=yuv420p[v]", "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "20", "-t", str(info["duration"]), str(temporary)])
            web_source = web_path(panel_preview, outdir)
        else:
            web_source = web_path(path, outdir)
        pages.append({"n": clip["id"], "t": clip["title"], "tc": f"{fmt(clip['in'])} – {fmt(clip['out'])}", "q": clip.get("line", ""), "f": path.name, "src": web_source, "alpha": clip["kind"] == "panel"})
    pages.insert(0, {"n": "▶", "full": True, "t": "Full preview · your video with every clip", "tc": "whole video", "q": "Composite for review. For the final cut, place the clips in your editor.", "f": preview.name, "src": web_path(preview, outdir)})
    replacements = {"/*TITLE*/": html.escape(title, quote=True), "/*FONT_CSS*/": local_fonts(outdir, font_mode)}
    viewer = fill_template((TEMPLATES / "viewer.html").read_text(encoding="utf-8"), {
        **replacements, "/*CLIPS*/[]": script_json(pages), "/*SUB*/": f"{len(clips)} clips + full preview",
    })
    comparison = fill_template((TEMPLATES / "compare.html").read_text(encoding="utf-8"), {
        **replacements, "/*DUR*/0": str(duration),
        "/*MARKS*/[]": script_json([[c["in"], c["out"], c["id"], c["title"]] for c in clips]),
        "/*ORIG*/": html.escape(web_path(source, outdir), quote=True),
        "/*BROLL*/": html.escape(web_path(preview, outdir), quote=True),
        "/*SUB*/": "Left or top is the original. Right or bottom has the motion graphics cut in.",
    })
    rows = ["| File | In | Out | Treatment | Covers the line |", "|---|---|---|---|---|"]
    for clip in clips:
        cells = [clip["path"].name, fmt(clip["in"]), fmt(clip["out"]), "transparent panel" if clip["kind"] == "panel" else "full-frame cutaway", clip.get("line", "")]
        rows.append("| " + " | ".join(markdown_cell(c) for c in cells) + " |")
    notes = plan.get("notes", [])
    timing = f"# B-roll for {markdown_cell(title)}\n\nPreview is for review. Original video and audio are preserved. Place the individual clips in your final editor.\n\n" + "\n".join(rows)
    if notes:
        timing += "\n\nNotes\n" + "\n".join("- " + markdown_cell(note) for note in notes)
    for filename, content in [("viewer.html", viewer), ("compare.html", comparison), ("TIMING.md", timing + "\n")]:
        with atomic_output(outdir / filename, inputs=input_paths) as temporary:
            temporary.write_text(content, encoding="utf-8")
        print(f"wrote {outdir / filename}")
    return [outdir / name for name in ("viewer.html", "compare.html", "TIMING.md")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("preview", type=Path)
    parser.add_argument("--font-mode", choices=("shared", "embedded"), default="embedded")
    args = parser.parse_args()
    try:
        write_pages(args.plan, args.preview, font_mode=args.font_mode)
    except (MediaError, OSError, ValueError) as error:
        parser.exit(1, f"make_pages: {error}\n")


if __name__ == "__main__":
    main()
