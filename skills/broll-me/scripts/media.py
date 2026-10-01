"""Shared local-media validation. Commands use argument arrays and never a shell."""
from contextlib import contextmanager
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile


class MediaError(ValueError):
    pass


def binary(name):
    return os.environ.get("BROLL_" + name.upper(), name)


def run(command, *, timeout=600, text=True):
    try:
        result = subprocess.run(command, capture_output=True, text=text, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise MediaError(f"Cannot run {Path(command[0]).name}: {error}") from error
    if result.returncode:
        detail = result.stderr if text else result.stderr.decode("utf-8", errors="replace")
        raise MediaError(f"{Path(command[0]).name} failed ({result.returncode}): {detail.strip()[-4000:]}")
    return result.stdout


def finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise MediaError(f"{name} must be a finite number")
    return float(value)


def frame_rate(value):
    try:
        if isinstance(value, bool):
            raise ValueError()
        rate = Fraction(str(value))
        if rate <= 0 or rate > 240:
            raise ValueError()
    except (ValueError, ZeroDivisionError) as error:
        raise MediaError("FPS must be a positive rational rate at most 240") from error
    return rate


def input_file(value, base=None):
    if not isinstance(value, (str, Path)) or not str(value):
        raise MediaError("Input path must be a non-empty local path")
    path = Path(value).expanduser()
    if not path.is_absolute() and base is not None:
        path = base / path
    path = path.resolve()
    if not path.is_file():
        raise MediaError(f"Input file not found: {path}")
    return path


def probe(path):
    path = input_file(path)
    try:
        data = json.loads(run([binary("ffprobe"), "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)], timeout=30))
        stream = next(s for s in data["streams"] if s.get("codec_type") == "video")
        width, height = int(stream["width"]), int(stream["height"])
        duration = float(stream.get("duration") or data["format"]["duration"])
        if width <= 0 or height <= 0 or not math.isfinite(duration) or duration <= 0:
            raise ValueError("Invalid video dimensions or duration")
        rate = frame_rate(stream.get("avg_frame_rate") if stream.get("avg_frame_rate") not in {None, "0/0"} else stream.get("r_frame_rate"))
        rotation = int(float(stream.get("tags", {}).get("rotate", 0)))
        for side in stream.get("side_data_list", []):
            if "rotation" in side:
                rotation = int(float(side["rotation"]))
        if rotation % 180:
            width, height = height, width
    except (KeyError, ValueError, TypeError, StopIteration) as error:
        raise MediaError(f"Invalid video metadata: {path}: {error}") from error
    return {"width": width, "height": height, "duration": duration, "fps": str(rate), "rate": rate,
            "audio": [s for s in data["streams"] if s.get("codec_type") == "audio"], "stream": stream,
            "format": data.get("format", {})}


def validate_source_timeline(info):
    """Reject unsupported origins rather than silently shifting or trimming audio."""
    def timing(stream, key, label):
        try:
            value = float(stream[key])
            if not math.isfinite(value):
                raise ValueError()
            return value
        except (KeyError, TypeError, ValueError) as error:
            raise MediaError(f"{label} {key} is unavailable; source timeline cannot be preserved without an approved normalization") from error
    video_start = timing(info["stream"], "start_time", "Video")
    video_duration = timing(info["stream"], "duration", "Video")
    if abs(video_start) > 1e-6 or video_duration <= 0:
        raise MediaError("Unsupported source timeline: video must start at 0. Ask for approval before normalizing the source timeline")
    if abs(video_duration - info["duration"]) > 1e-6:
        raise MediaError("Video duration is ambiguous; source timeline requires an approved normalization")
    format_start = info.get("format", {}).get("start_time")
    if format_start is not None and abs(timing({"start_time": format_start}, "start_time", "Container")) > 1e-6:
        raise MediaError("Unsupported nonzero container timeline; approval is required before normalization")
    for index, audio in enumerate(info["audio"]):
        start = timing(audio, "start_time", f"Audio stream {index}")
        duration = timing(audio, "duration", f"Audio stream {index}")
        if abs(start) > 1e-6 or duration <= 0 or start + duration > video_duration + 1e-6:
            raise MediaError("Unsupported source audio timeline: every audio stream must start at 0 and fit within the video duration. Ask for approval before normalizing or trimming audio")


def load_plan(plan_path):
    plan_path = input_file(plan_path)
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MediaError(f"Cannot read plan: {error}") from error
    if not isinstance(plan, dict) or not isinstance(plan.get("clips"), list):
        raise MediaError("Plan must contain a clips array")
    if not isinstance(plan.get("title", "Video"), str) or not isinstance(plan.get("notes", []), list) or not all(isinstance(n, str) for n in plan.get("notes", [])):
        raise MediaError("Plan title and notes must be strings")
    source = input_file(plan.get("video"), plan_path.parent)
    source_info = probe(source)
    validate_source_timeline(source_info)
    fps = frame_rate(plan.get("fps", source_info["fps"]))
    if abs(float(fps - source_info["rate"])) > 1e-6:
        raise MediaError(f"Plan FPS {fps} differs from source FPS {source_info['fps']}")
    clips = []
    ids = set()
    for index, clip in enumerate(plan["clips"]):
        if not isinstance(clip, dict):
            raise MediaError("Each clip must be an object")
        for key in ("id", "title", "kind"):
            if not isinstance(clip.get(key), str) or not clip[key]:
                raise MediaError(f"Clip {index}: {key} must be a non-empty string")
        if not isinstance(clip.get("line", ""), str):
            raise MediaError(f"Clip {index}: line must be text")
        if clip["id"] in ids:
            raise MediaError(f"Duplicate clip id: {clip['id']}")
        ids.add(clip["id"])
        start, end = finite_number(clip.get("in"), "clip in"), finite_number(clip.get("out"), "clip out")
        if start < 0 or end <= start or end > source_info["duration"] + 1e-6:
            raise MediaError(f"Clip {clip['id']}: invalid slot or outside source duration")
        if clip["kind"] not in {"full", "panel"}:
            raise MediaError("Clip kind must be full or panel")
        path = input_file(clip.get("file"), plan_path.parent)
        required = ".mov" if clip["kind"] == "panel" else ".mp4"
        if path.suffix.lower() != required:
            raise MediaError(f"{clip['kind']} clip requires {required}: {path}")
        info = probe(path)
        if (info["width"], info["height"]) != (source_info["width"], source_info["height"]):
            raise MediaError(f"Clip {clip['id']}: dimensions differ from source")
        if abs(float(info["rate"] - fps)) > 1e-6:
            raise MediaError(f"Clip {clip['id']}: FPS differs from source")
        pixel_format = info["stream"].get("pix_fmt", "")
        if clip["kind"] == "panel" and not pixel_format.startswith(("yuva", "gbrap", "rgba", "argb", "bgra", "abgr", "ya")):
            raise MediaError(f"Panel {clip['id']} does not contain an alpha pixel format")
        clips.append({**clip, "in": start, "out": end, "path": path, "info": info})
    previous_end = 0
    for clip in sorted(clips, key=lambda c: c["in"]):
        if clip["in"] < previous_end - 1e-6:
            raise MediaError("Clip slots overlap; resolve the insertion plan before rendering")
        previous_end = clip["out"]
    return plan, source, source_info, clips


@contextmanager
def atomic_output(output, *, inputs=(), suffix=None):
    output = Path(output).expanduser().resolve()
    if suffix and output.suffix.lower() != suffix:
        raise MediaError(f"Output must end with {suffix}")
    if output in {Path(path).resolve() for path in inputs}:
        raise MediaError("Output must not overwrite an input file")
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".broll-", suffix=output.suffix, dir=output.parent)
    os.close(handle)
    temporary = Path(temporary)
    try:
        yield temporary
        if not temporary.is_file() or not temporary.stat().st_size:
            raise MediaError("Renderer produced no output")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
