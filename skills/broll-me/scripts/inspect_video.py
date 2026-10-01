"""Inspect local video metadata and heuristic layout candidates.
Usage: python3 inspect_video.py video.mp4 outdir
A dark-band candidate is not verified speaker detection; inspect the contact sheet.
"""
import argparse
import json
from pathlib import Path
import sys
from media import MediaError, atomic_output, binary, input_file, probe, run


def analyze_frames(frames, width, height, duration):
    import numpy as np
    if not len(frames):
        raise MediaError("No video frames were decoded")
    sections = []
    previous = None
    start = 0
    for index, frame in enumerate(frames):
        # Entirely dark frames do not establish an available panel region.
        empty = frame.max() <= 20
        label = "unknown" if empty else ("pip" if frame[:, 60:].mean() < 8 or frame[:, :36].mean() < 8 else "full")
        if label != previous:
            if previous is not None:
                sections.append({"from": start / 4, "to": min(index / 4, duration), "layout": previous})
            previous, start = label, index
    sections.append({"from": start / 4, "to": duration, "layout": previous})
    for section in sections:
        section["verified"] = False
        if section["layout"] != "pip":
            if section["layout"] == "unknown":
                section["warning"] = "Dark frames: no subject box or safe panel placement inferred"
            continue
        boxes = []
        for index in range(int(section["from"] * 4), min(len(frames), int(section["to"] * 4) + 1)):
            frame = frames[index]
            cols, rows = np.where(frame.max(0) > 20)[0], np.where(frame.max(1) > 20)[0]
            if not len(cols) or not len(rows):
                continue
            boxes.append((index / 4, [int(cols.min() * width / 96), int(rows.min() * height / 54), int((cols.max() + 1) * width / 96), int((rows.max() + 1) * height / 54)]))
        if not boxes:
            section.update(layout="unknown", warning="No visible content bounds; do not infer placement")
            continue
        section["subject_box"] = [min(box[1][0] for box in boxes), min(box[1][1] for box in boxes), max(box[1][2] for box in boxes), max(box[1][3] for box in boxes)]
        changes = []
        reference = boxes[0][1]
        for timestamp, box in boxes:
            if max(abs(box[k] - reference[k]) for k in range(4)) > 2 * max(width / 96, height / 54):
                changes.append({"at": timestamp, "box": box})
                reference = box
        section["box_changes"] = changes
        section["warning"] = "Heuristic visible-content bounds only; verify the speaker and empty region visually"
    return sections


def inspect_video(video, outdir):
    try:
        import numpy as np
    except ImportError as error:
        raise MediaError("NumPy is missing; run setup.sh and use runtime/.venv/bin/python") from error
    source = input_file(video)
    outdir = Path(outdir).resolve()
    if source in {outdir / "contact.png", outdir / "video.json"}:
        raise MediaError("Inspection output must not overwrite the source")
    info = probe(source)
    outdir.mkdir(parents=True, exist_ok=True)
    with atomic_output(outdir / "contact.png", inputs=[source], suffix=".png") as temporary:
        run([binary("ffmpeg"), "-v", "error", "-nostdin", "-y", "-i", str(source), "-vf", f"fps=1/{max(.01, info['duration'] / 16):.6f},scale=480:-1,tile=4x4:padding=4", "-frames:v", "1", str(temporary)])
    raw = run([binary("ffmpeg"), "-v", "error", "-nostdin", "-i", str(source), "-vf", "fps=4,scale=96:54,format=gray", "-f", "rawvideo", "-"], text=False)
    if len(raw) % (54 * 96):
        raise MediaError("Decoded analysis frames have an invalid byte count")
    frames = np.frombuffer(raw, np.uint8).reshape(-1, 54, 96)
    sections = analyze_frames(frames, info["width"], info["height"], info["duration"])
    result = {k: info[k] for k in ("width", "height", "fps", "duration")}
    result.update(sections=sections, layout_method="near-black-band heuristic", requires_visual_review=True)
    with atomic_output(outdir / "video.json", inputs=[source], suffix=".json") as temporary:
        temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("outdir", type=Path)
    args = parser.parse_args()
    try:
        inspect_video(args.video, args.outdir)
    except (MediaError, OSError) as error:
        parser.exit(1, f"inspect_video: {error}\n")


if __name__ == "__main__":
    main()
