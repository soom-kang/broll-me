"""Create a review preview with hard-cut B-roll and stream-copied source audio.
Usage: python3 composite.py motion/plan.json motion/out/preview.mp4
"""
import argparse
from pathlib import Path
from media import MediaError, atomic_output, binary, load_plan, probe, run


def composite_command(source, info, clips, output):
    fps = info["fps"]
    cmd = [binary("ffmpeg"), "-v", "error", "-nostdin", "-y", "-i", str(source)]
    filters = [f"[0:v]setpts=PTS-STARTPTS,fps={fps}[base]"]
    last = "base"
    for index, clip in enumerate(clips, 1):
        cmd += ["-i", str(clip["path"])]
        slot = clip["out"] - clip["in"]
        # Include one frame of pad so the final output frame cannot fall through.
        hold = max(0, slot - clip["info"]["duration"]) + 1 / float(info["rate"])
        filters.append(f"[{index}:v]setpts=PTS-STARTPTS,fps={fps},format=yuva444p,tpad=stop_mode=clone:stop_duration={hold:.9f},trim=duration={slot:.9f},setpts=PTS-STARTPTS+{clip['in']:.9f}/TB[c{index}]")
        filters.append(f"[{last}][c{index}]overlay=enable='gte(t,{clip['in']:.9f})*lt(t,{clip['out']:.9f})':eof_action=pass:repeatlast=0[v{index}]")
        last = f"v{index}"
    filters.append(f"[{last}]format=yuv420p[v]")
    cmd += ["-filter_complex", ";".join(filters), "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-r", fps, "-c:a", "copy", "-t", str(info["duration"]), "-movflags", "+faststart", str(output)]
    return cmd


def create_preview(plan_path, output):
    _, source, info, clips = load_plan(plan_path)
    with atomic_output(output, inputs=[source, plan_path, *(c["path"] for c in clips)], suffix=".mp4") as temporary:
        try:
            run(composite_command(source, info, clips, temporary))
        except MediaError as error:
            message = str(error)
            if info["audio"]:
                message += " Source audio is copied unchanged; MP4-incompatible audio requires explicit approval before transcoding."
            raise MediaError(message) from error
        rendered = probe(temporary)
        if abs(rendered["duration"] - info["duration"]) > 2 / float(info["rate"]):
            raise MediaError("Preview duration does not match source video")
        if rendered["rate"] != info["rate"] or (rendered["width"], rendered["height"]) != (info["width"], info["height"]):
            raise MediaError("Preview dimensions or FPS do not match source video")
        if [s.get("codec_name") for s in rendered["audio"]] != [s.get("codec_name") for s in info["audio"]]:
            raise MediaError("Preview audio streams do not match source streams")
    print(f"wrote {Path(output).resolve()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        create_preview(args.plan, args.output)
    except (MediaError, OSError) as error:
        parser.exit(1, f"composite: {error}\n")


if __name__ == "__main__":
    main()
