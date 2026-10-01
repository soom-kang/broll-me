"""Palette contract, offline build, and source semantic migration regression tests."""
import copy
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "broll-me"
sys.path.insert(0, str(SKILL / "engine"))
from palette import (DEFAULT_PALETTE, PRESETS, ROLES, PaletteError, contrast_checks,
                     css_variables, resolve_palette, validate_palette, write_snapshot)
from build import build


class PaletteTests(unittest.TestCase):
    def test_presets_preserve_approved_core_and_readable_pairs(self):
        cores = {
            "warm-orange": ("#E9E7E2", "#FFFFFF", "#0B0B0B", "#FF5A1F"),
            "sage-cream": ("#F4F1E8", "#FFFDF7", "#24382C", "#5E7D64"),
            "editorial-blue": ("#F3F6FA", "#FFFFFF", "#172B4D", "#2F5BEA"),
            "midnight-cyan": ("#111827", "#1F2937", "#F9FAFB", "#67E8F9"),
            "kkumil-pink": ("#FFF0E6", "#FFFFFF", "#333333", "#FF5C8D"),
            "onnimm-orange": ("#FCFBF8", "#FFFFFF", "#354135", "#FF8A50"),
        }
        for name in PRESETS:
            with self.subTest(name=name):
                colors = resolve_palette(name)["colors"]
                self.assertEqual(tuple(colors[role] for role in ("canvas", "surface", "ink", "accent")), cores[name])
                self.assertTrue(set(ROLES) <= set(colors))
                self.assertTrue(all(r >= 4.5 for r in contrast_checks(colors).values()))
        self.assertEqual(resolve_palette()["id"], DEFAULT_PALETTE)

    def test_custom_complete_palette_normalizes_without_altering_brand(self):
        data = resolve_palette("kkumil-pink")
        data["id"] = "custom-pink"
        data["colors"]["accent"] = "#ff5c8d"
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "custom.json"
            path.write_text(json.dumps(data))
            resolved = resolve_palette(palette_file=path)
        self.assertEqual(resolved["colors"]["accent"], "#FF5C8D")
        self.assertEqual(resolved["colors"]["rose"], "#FF8FA6")

    def test_invalid_roles_formats_and_contrast_fail(self):
        original = resolve_palette()
        cases = []
        missing = copy.deepcopy(original); del missing["colors"]["ink"]; cases.append(missing)
        unknown = copy.deepcopy(original); unknown["colors"]["secretRole"] = "#FFFFFF"; cases.append(unknown)
        for value in ("#fff", "red", "var(--x)", "rgb(0,0,0)", 123):
            data = copy.deepcopy(original); data["colors"]["ink"] = value; cases.append(data)
        for role in ("ink", "muted", "onAccent", "inverseInk", "inverseMuted"):
            data = copy.deepcopy(original)
            background = "accent" if role == "onAccent" else "inverseSurface" if role.startswith("inverse") else "surface"
            data["colors"][role] = data["colors"][background]; cases.append(data)
        for data in cases:
            with self.subTest(data=data):
                with self.assertRaises(PaletteError): validate_palette(data)
        with self.assertRaises(PaletteError): resolve_palette("../schema")
        with self.assertRaises(PaletteError): resolve_palette("warm-orange", "custom.json")

    def test_mutually_exclusive_cli_and_no_invalid_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = pathlib.Path(tmp) / "invalid"
            command = [sys.executable, str(SKILL / "engine" / "build.py"), str(output),
                       str(SKILL / "examples" / "palette-demo.html")]
            result = subprocess.run(command + ["--palette", "warm-orange", "--palette-file", "missing.json"], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            result = subprocess.run(command + ["--palette", "unknown"], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_build_palette_is_frozen_before_engine_and_reproducible(self):
        fragment = SKILL / "examples" / "palette-demo.html"
        before = fragment.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            first = build(fragment, folder / "first.html", palette="midnight-cyan")
            snapshot = folder / "palette.resolved.json"
            second = build(fragment, folder / "reproduced" / "second.html", palette_file=snapshot)
            text = first.read_text()
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertLess(text.index("window.BROLL_PALETTE="), text.index("const M = window.M"))
            self.assertIn("--broll-canvas:#111827", text)
            self.assertIn("M.palette", text)
            self.assertIn("Noto Sans KR", text)
            self.assertNotIn("__NOTOSANSKR__", text)
            self.assertNotRegex(text, r"https?://")
            self.assertEqual(json.loads(snapshot.read_text()), resolve_palette("midnight-cyan"))
        self.assertEqual(fragment.read_bytes(), before)
        with self.assertRaises(ValueError): build(fragment, fragment)

    def test_different_palette_in_same_directory_is_rejected_without_writes(self):
        fragment = SKILL / "examples" / "palette-demo.html"
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            first = build(fragment, folder / "first.html", palette="kkumil-pink")
            snapshot = folder / "palette.resolved.json"
            original_html, original_snapshot = first.read_bytes(), snapshot.read_bytes()
            with self.assertRaisesRegex(PaletteError, "use a new output directory"):
                build(fragment, folder / "second.html", palette="midnight-cyan")
            self.assertFalse((folder / "second.html").exists())
            self.assertEqual(first.read_bytes(), original_html)
            self.assertEqual(snapshot.read_bytes(), original_snapshot)
            # API-provided palette data must obey the same directory guard.
            with self.assertRaises(PaletteError):
                build(fragment, folder / "third.html", resolved_palette=resolve_palette())
            self.assertFalse((folder / "third.html").exists())
            result = subprocess.run([sys.executable, str(SKILL / "engine" / "build.py"),
                                     str(folder), str(fragment), "--palette", "midnight-cyan"],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("use a new output directory", result.stderr)
            self.assertFalse((folder / "palette-demo.html").exists())
            self.assertEqual(first.read_bytes(), original_html)
            self.assertEqual(snapshot.read_bytes(), original_snapshot)
            before_time = snapshot.stat().st_mtime_ns
            build(fragment, folder / "same.html", palette="kkumil-pink")
            self.assertEqual(snapshot.stat().st_mtime_ns, before_time)

    def test_snapshot_collision_and_symlink_do_not_overwrite_sources(self):
        fragment = SKILL / "examples" / "palette-demo.html"
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            source = folder / "palette.resolved.json"
            source.write_bytes(fragment.read_bytes())
            original = source.read_bytes()
            with self.assertRaisesRegex(PaletteError, "overwrite input"):
                build(source, folder / "palette.resolved.html")
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse((folder / "palette.resolved.html").exists())
            output = folder / "linked"
            output.mkdir()
            snapshot = output / "palette.resolved.json"
            snapshot.symlink_to(source)
            with self.assertRaisesRegex(PaletteError, "symlink"):
                build(fragment, output / "scene.html")
            self.assertEqual(source.read_bytes(), original)
            self.assertTrue(snapshot.is_symlink())
            self.assertFalse((output / "scene.html").exists())

    def test_batch_checks_subsequent_snapshot_source_before_first_output(self):
        fragment = SKILL / "examples" / "palette-demo.html"
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            output = folder / "out"
            output.mkdir()
            later_source = output / "palette.resolved.json"
            later_source.write_bytes(fragment.read_bytes())
            before = later_source.read_bytes()
            result = subprocess.run([sys.executable, str(SKILL / "engine" / "build.py"),
                                     str(output), str(fragment), str(later_source)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("overwrite input", result.stderr)
            self.assertEqual(later_source.read_bytes(), before)
            self.assertEqual(list(output.iterdir()), [later_source])

    def test_custom_palette_file_collision_fails_before_html(self):
        fragment = SKILL / "examples" / "palette-demo.html"
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            palette_file = folder / "palette.resolved.json"
            palette_file.write_text(json.dumps(resolve_palette()))
            original = palette_file.read_bytes()
            result = subprocess.run([sys.executable, str(SKILL / "engine" / "build.py"),
                                     str(folder), str(fragment), "--palette-file", str(palette_file)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("overwrite input", result.stderr)
            self.assertFalse((folder / "palette-demo.html").exists())
            self.assertEqual(palette_file.read_bytes(), original)

    def test_atomic_snapshot_reuses_equal_file_and_rejects_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            target = folder / "palette.resolved.json"
            write_snapshot(resolve_palette(), target)
            original, timestamp = target.read_bytes(), target.stat().st_mtime_ns
            write_snapshot(resolve_palette(), target)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(target.stat().st_mtime_ns, timestamp)
            self.assertEqual(list(folder.iterdir()), [target])
            with self.assertRaises(PaletteError): write_snapshot(resolve_palette("sage-cream"), target)
            link = folder / "linked.json"
            link.symlink_to(target)
            with self.assertRaisesRegex(PaletteError, "symlink"):
                write_snapshot(resolve_palette("sage-cream"), link)
            self.assertTrue(link.is_symlink())
            self.assertEqual(target.read_bytes(), original)

    def test_primary_authoring_skeleton_uses_palette_roles(self):
        api = (SKILL / "reference" / "engine-api.md").read_text()
        skeleton = api.split("```html", 1)[1].split("```", 1)[0]
        self.assertIn("const P = M.palette;", skeleton)
        self.assertIn("bg:P.canvas", skeleton)
        self.assertIn("bg:P.surface", skeleton)
        self.assertNotRegex(skeleton, r"#[0-9a-fA-F]{3,8}\b")

    def test_examples_are_semantic_including_numeric_colors_and_alpha(self):
        examples = list((SKILL / "examples" / "opus-aoe2").glob("*.html"))
        self.assertEqual(len(examples), 6)
        for path in examples:
            with self.subTest(path=path.name):
                text = path.read_text()
                self.assertNotRegex(text, r"#[0-9a-fA-F]{3,8}\b")
                self.assertNotRegex(text, r"rgba?\(\s*\d")
                self.assertIn("const P=M.palette", text)
        self.assertIn("bg:null", (SKILL / "examples" / "opus-aoe2" / "02-pip-builds.html").read_text())
        self.assertIn("M.mixColors(P.ink,P.accent,k)", (SKILL / "examples" / "opus-aoe2" / "02-pip-builds.html").read_text())
        self.assertIn("M.rgba(P.accent,k)", (SKILL / "examples" / "opus-aoe2" / "04-master-prompt.html").read_text())
        self.assertNotIn("mix-blend-mode:difference", (SKILL / "engine" / "base.css").read_text())
        self.assertIn("--broll-surface-alt", css_variables(resolve_palette()))


if __name__ == "__main__":
    unittest.main()
