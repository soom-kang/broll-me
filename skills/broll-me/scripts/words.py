"""Estimate word times from SRT or WebVTT cues; these are not forced alignment.

Usage: python3 words.py transcript.srt > words.txt
"""
import argparse
import html
from pathlib import Path
import re


def timestamp(value):
    match = re.fullmatch(r"(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})", value.strip())
    if not match:
        raise ValueError(f"Invalid subtitle timestamp: {value!r}")
    hours, minutes, seconds, millis = match.groups()
    if int(minutes) > 59 or int(seconds) > 59:
        raise ValueError(f"Invalid subtitle timestamp: {value!r}")
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def parse_cues(text):
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    cues = []
    previous = -1
    for block_index, block in enumerate(re.split(r"\n\s*\n", text.strip())):
        lines = block.strip().splitlines()
        if not lines:
            continue
        first = lines[0]
        if block_index == 0 and re.fullmatch(r"WEBVTT(?:[ \t].*)?", first):
            continue
        # Reserved blocks require a token boundary, not a cue-ID prefix.
        if re.match(r"NOTE(?:[ \t]|$)", first) or first in {"STYLE", "REGION"}:
            continue
        timing = next((i for i, line in enumerate(lines[:2]) if "-->" in line), None)
        if timing is None:
            raise ValueError(f"Subtitle cue has no timing line: {lines[0]!r}")
        endpoints = re.split(r"\s*-->\s*", lines[timing], maxsplit=1)
        if len(endpoints) != 2 or not endpoints[1].split():
            raise ValueError("Subtitle cue is missing its end timestamp")
        start = timestamp(endpoints[0])
        end = timestamp(endpoints[1].split()[0])
        if end <= start or start < previous:
            raise ValueError("Subtitle cues must have increasing start times and positive durations")
        previous = start
        words = html.unescape(re.sub(r"<[^>]*>", "", " ".join(lines[timing + 1:]))).split()
        if words:
            cues.append((start, end, words))
    if not cues:
        raise ValueError("No non-empty timed subtitle cues found")
    return cues


def estimated_words(cues):
    for start, end, words in cues:
        total = sum(len(word) + 1 for word in words)
        position = 0
        output = []
        for word in words:
            output.append(f"{start + (end - start) * position / total:.2f}:{word}")
            position += len(word) + 1
        yield " ".join(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path)
    args = parser.parse_args()
    if args.transcript.suffix.lower() not in {".srt", ".vtt"}:
        parser.error("Use a timed .srt or .vtt transcript")
    try:
        print("\n".join(estimated_words(parse_cues(args.transcript.read_text(encoding="utf-8-sig")))))
    except (OSError, ValueError) as error:
        parser.exit(1, f"words: {error}\n")


if __name__ == "__main__":
    main()
