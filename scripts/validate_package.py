#!/usr/bin/env python3
"""Validate the portable skill and collect a curated, credential-free package."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import zipfile

ROOT_FILES = {"SKILL.md", "LICENSE", "THIRD_PARTY_NOTICES.md"}
ROOT_DIRS = {"agents", "engine", "reference", "scripts", "templates", "examples", "palettes", "licenses"}
SUFFIXES = {".md", ".txt", ".json", ".html", ".css", ".js", ".mjs", ".py", ".sh", ".yaml", ".yml", ".woff", ".woff2", ".ttf", ".otf"}
DOCUMENT_IMAGES = {"reference/assets/broll-me-title.png", "reference/assets/workflow-en.png", "reference/assets/workflow-ko.png"}
IGNORE_DIRS = {"__pycache__", "node_modules", "evals"}
IGNORE_FILES = {".DS_Store"}
REQUIRED = {"SKILL.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "engine/build.py", "engine/motion.js", "reference/engine-api.md", "scripts/setup.sh", "agents/openai.yaml"}
SECRET_CONTENT = re.compile(r"(?:-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16})\b)")
COMMON_FIELDS = {"name", "description", "license", "metadata"}
IMPLICIT_WORDS = {"null", "~", "true", "false", "yes", "no", "on", "off", "y", "n"}
JSON_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
YAML_NUMBER = re.compile(r"[-+]?(?:0[bBoOxX][0-9a-fA-F_]+|(?:[0-9][0-9_]*(?:\.[0-9_]*)?|\.[0-9_]+)(?:[eE][-+]?[0-9_]+)?|(?:[0-9][0-9_]*:)+[0-9_]+(?:\.[0-9_]*)?|\.(?:inf|nan))", re.I)
YAML_DATE = re.compile(r"[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}(?:[Tt ].*)?")


def portable_scalar(raw: str, *, string_only: bool, context: str) -> str:
    """Validate one single-line scalar; this deliberately does not parse full YAML."""
    value = raw.strip(" ")
    if value.startswith('"'):
        try:
            value, end = json.JSONDecoder().raw_decode(value)
        except ValueError as exc:
            raise ValueError(f"Invalid double-quoted portable scalar: {context}") from exc
        tail = raw.strip(" ")[end:]
        if tail and not re.fullmatch(r" +#.*", tail):
            raise ValueError(f"Trailing content after portable scalar: {context}")
    elif value.startswith("'"):
        quoted: list[str] = []
        index = 1
        while index < len(value):
            if value[index] != "'":
                quoted.append(value[index])
                index += 1
            elif index + 1 < len(value) and value[index + 1] == "'":
                quoted.append("'")
                index += 2
            else:
                tail = value[index + 1:]
                if tail and not re.fullmatch(r" +#.*", tail):
                    raise ValueError(f"Trailing content after portable scalar: {context}")
                value = "".join(quoted)
                break
        else:
            raise ValueError(f"Unterminated single-quoted portable scalar: {context}")
    else:
        value = re.split(r"(?:^| +)#", value, maxsplit=1)[0].rstrip(" ")
        if value and (value[0] in "[]{},&*!|>'\"%@`" or re.match(r"[-?:](?: |$)", value)
                      or re.search(r":(?: |$)", value)):
            raise ValueError(f"Unsupported portable scalar syntax: {context}")
        implicit = not value or value.lower() in IMPLICIT_WORDS or YAML_NUMBER.fullmatch(value) or YAML_DATE.fullmatch(value)
        if implicit:
            if string_only:
                raise ValueError(f"Portable field must be a string: {context}; quote scalar-looking text")
            if value and value.lower() not in IMPLICIT_WORDS and not JSON_NUMBER.fullmatch(value):
                raise ValueError(f"Unsupported portable number/date syntax: {context}; quote it as a string")
    if any(ord(char) < 32 or 127 <= ord(char) <= 159 or 0xD800 <= ord(char) <= 0xDFFF
           or char in "\u2028\u2029\ufeff\ufffe\uffff" for char in value):
        raise ValueError(f"Control characters are not supported in portable scalars: {context}")
    return value


def validate_frontmatter(text: str) -> None:
    match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", text, re.S)
    if not match:
        raise ValueError("SKILL.md must start with YAML frontmatter")
    body = match.group(1)
    if any((ord(char) < 32 and char != "\n") or 127 <= ord(char) <= 159
           or 0xD800 <= ord(char) <= 0xDFFF or char in "\u2028\u2029\ufeff\ufffe\uffff" for char in body):
        raise ValueError("Control characters and tabs are not supported in portable frontmatter")
    data: dict[str, str] = {}
    metadata_keys: set[str] = set()
    metadata_block = False
    for line in body.split("\n"):
        if not line.strip(" ") or line.lstrip(" ").startswith("#"):
            continue
        if line.startswith(" "):
            if not metadata_block:
                raise ValueError("Only the active metadata map may be nested in portable frontmatter")
            child = re.fullmatch(r"  ([A-Za-z_][A-Za-z0-9_-]*):(?: +(.*))?", line)
            if not child or child[1] in metadata_keys or child[1].lower() in IMPLICIT_WORDS:
                raise ValueError(f"Unsupported or duplicate portable metadata key: {line}")
            portable_scalar(child[2] or "", string_only=False, context=f"metadata.{child[1]}")
            metadata_keys.add(child[1])
            continue
        if metadata_block and not metadata_keys:
            raise ValueError("Portable metadata must be a map; use {} for an empty map")
        metadata_block = False
        field = re.fullmatch(r"([a-z-]+):(?: +(.*))?", line)
        if not field or field[1] not in COMMON_FIELDS or field[1] in data:
            raise ValueError(f"Unsupported or duplicate portable frontmatter field: {line}")
        if field[1] == "metadata":
            value = re.split(r"(?:^| +)#", (field[2] or "").strip(" "), maxsplit=1)[0].rstrip(" ")
            if value not in {"", "{}"}:
                raise ValueError("Portable metadata must be {} or a flat map with two-space indentation")
            metadata_block = not value
            data[field[1]] = value
        else:
            data[field[1]] = portable_scalar(field[2] or "", string_only=True, context=field[1])
    if metadata_block and not metadata_keys:
        raise ValueError("Portable metadata must be a map; use {} for an empty map")
    if data.get("name") != "broll-me":
        raise ValueError("Skill name must be broll-me")
    description = data.get("description", "")
    if not isinstance(description, str) or not 1 <= len(description) <= 1024:
        raise ValueError("Skill description must contain 1-1024 characters")
    if "<" in description or ">" in description:
        raise ValueError("Skill description must not contain angle brackets")


def collect_files(skill: Path) -> dict[str, bytes]:
    skill = skill.resolve(strict=True)
    if skill.name != "broll-me" or not skill.is_dir():
        raise ValueError("Canonical skill root must be a directory named broll-me")
    files: dict[str, bytes] = {}
    for path in sorted(skill.rglob("*")):
        rel = path.relative_to(skill)
        if path.is_symlink():
            raise ValueError(f"Skill source must not contain symlinks: {rel}")
        if any(part == ".git" or part.lower().startswith(".env") or PurePosixPath(part).stem.lower() in {"credentials", "secrets", ".aws", ".ssh"} for part in rel.parts):
            raise ValueError(f"Forbidden credential or repository path: {rel}")
        if any(part in IGNORE_DIRS for part in rel.parts) or path.name in IGNORE_FILES or path.suffix == ".pyc":
            continue
        if not path.is_file():
            continue
        if (len(rel.parts) == 1 and rel.name not in ROOT_FILES) or (len(rel.parts) > 1 and rel.parts[0] not in ROOT_DIRS):
            raise ValueError(f"Uncurated skill package path: {rel}")
        document_image = rel.as_posix() in DOCUMENT_IMAGES
        if path.name not in ROOT_FILES and path.suffix.lower() not in SUFFIXES and not document_image:
            raise ValueError(f"Unsupported package file; media/private artwork excluded: {rel}")
        if path.suffix.lower() in {".woff", ".woff2", ".ttf", ".otf"} and rel.parts[:2] != ("engine", "fonts"):
            raise ValueError(f"Font outside curated engine/fonts: {rel}")
        content = path.read_bytes()
        if document_image and not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError(f"Documentation image must be PNG: {rel}")
        if not document_image and path.suffix.lower() not in {".woff", ".woff2", ".ttf", ".otf"}:
            text = content.decode("utf-8")
            if SECRET_CONTENT.search(text):
                raise ValueError(f"Credential-like content found in {rel}; value omitted")
            if path.suffix == ".json":
                json.loads(text)
        files[rel.as_posix()] = content
    missing = REQUIRED - files.keys()
    if missing:
        raise ValueError(f"Required package files missing: {', '.join(sorted(missing))}")
    validate_frontmatter(files["SKILL.md"].decode())
    for name, data in files.items():
        if not name.endswith(".md"):
            continue
        text = data.decode()
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            target = target.split("#", 1)[0].strip().strip("<>")
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            resolved = (skill / name).parent / target
            try:
                resolved.resolve().relative_to(skill)
            except ValueError as exc:
                raise ValueError(f"Reference escapes skill package: {name} -> {target}") from exc
            if not resolved.exists():
                raise ValueError(f"Missing internal reference: {name} -> {target}")
    return files


def verify_archive(archive: Path, files: dict[str, bytes]) -> None:
    expected = {f"broll-me/{name}": content for name, content in files.items()}
    with zipfile.ZipFile(archive) as package:
        infos = package.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)) or set(names) != expected.keys():
            raise ValueError("Archive file list differs from curated source")
        for info in infos:
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in info.filename or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(f"Unsafe archive entry: {info.filename}")
            if info.file_size != len(expected[info.filename]) or package.read(info) != expected[info.filename]:
                raise ValueError(f"Archive bytes differ from source: {info.filename}")
        with tempfile.TemporaryDirectory(prefix="broll-roundtrip-") as tmp:
            package.extractall(tmp)
            for name, content in expected.items():
                if (Path(tmp) / name).read_bytes() != content:
                    raise ValueError(f"Archive round-trip mismatch: {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", nargs="?", type=Path, default=Path(__file__).resolve().parents[1] / "skills/broll-me")
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    try:
        files = collect_files(args.skill)
        if args.archive:
            verify_archive(args.archive, files)
        print(json.dumps({"status": "passed", "files": len(files), "archive": str(args.archive) if args.archive else None,
                          "source_digest": hashlib.sha256(b"".join(name.encode() + b"\0" + hashlib.sha256(data).digest() for name, data in files.items())).hexdigest()}))
    except (OSError, ValueError, UnicodeError, zipfile.BadZipFile) as exc:
        print(f"Package validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
