"""Palette contract, offline build, and source semantic migration regression tests."""
import copy
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "broll-me"
sys.path.insert(0, str(SKILL / "engine"))
from palette import (DEFAULT_PALETTE, PRESETS, ROLES, PaletteError, PaletteRecoveryError, contrast_checks,
                     css_variables, resolve_palette, validate_palette, write_snapshot)
import build as builder
from build import build, build_scene


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
            # OFL text contains attribution URLs; only the notice comments are exempt.
            resources = re.sub(r"/\* Font notice: [^\n]+\n.*?\n\*/", "", text, flags=re.S)
            self.assertIsNone(re.search(r"https?://", resources), "Scene must not reference remote resources")
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
            for name in ["palette.resolved.json", "Palette.Resolved.JSON"]:
                reserved = folder / "reserved" / name
                with self.assertRaisesRegex(ValueError, "reserved palette snapshot"):
                    build(fragment, reserved, font_mode="shared")
                self.assertFalse(reserved.parent.exists())

    def test_build_rejects_input_hardlinks_before_writing(self):
        cases = ("fragment", "scene", "palette")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                folder = pathlib.Path(tmp)
                source = folder / ("source.json" if case == "scene" else "source.html")
                example = SKILL / "examples" / ("scenes/card.json" if case == "scene" else "palette-demo.html")
                source.write_bytes(example.read_bytes())
                options = {"font_mode": "shared"}
                protected = source
                if case == "palette":
                    protected = folder / "custom.json"
                    protected.write_text(json.dumps(resolve_palette()))
                    options["palette_file"] = protected
                destination = folder / "out" / "clip.html"
                destination.parent.mkdir()
                os.link(protected, destination)
                original = protected.read_bytes()
                compile_clip = build_scene if case == "scene" else build
                with self.assertRaisesRegex(ValueError, "overwrite an input.*use a new output directory"):
                    compile_clip(source, destination, **options)
                self.assertEqual(protected.read_bytes(), original)
                self.assertEqual(destination.read_bytes(), original)
                self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_batch_rejects_hardlink_to_later_source_before_first_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            sources = [folder / "first.html", folder / "later.html"]
            for source in sources:
                source.write_bytes((SKILL / "examples/palette-demo.html").read_bytes())
            output = folder / "out"
            output.mkdir()
            alias = output / "first.html"
            os.link(sources[1], alias)
            before = [source.read_bytes() for source in sources]
            result = subprocess.run([sys.executable, str(SKILL / "engine/build.py"),
                                     str(output), *map(str, sources)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("overwrite an input", result.stderr)
            self.assertEqual([source.read_bytes() for source in sources], before)
            self.assertEqual(list(output.iterdir()), [alias])

    def test_batch_rejects_filesystem_equivalent_names_before_artifact_writes(self):
        pairs = (("Intro", "intro"), ("Caf\u00e9", "Cafe\u0301"))
        checked = 0
        for first, second in pairs:
            with self.subTest(names=(first, second)), tempfile.TemporaryDirectory() as tmp:
                folder = pathlib.Path(tmp)
                probe = folder / first
                probe.touch()
                equivalent = (folder / second).exists() and (folder / second).samefile(probe)
                probe.unlink()
                if not equivalent:
                    continue
                checked += 1
                sources = [folder / "a" / f"{first}.html", folder / "b" / f"{second}.html"]
                for index, source in enumerate(sources):
                    source.parent.mkdir()
                    source.write_text(f"<title>SCENE {index}</title>")
                for mode in ("shared", "embedded"):
                    for exists in (False, True):
                        with self.subTest(font_mode=mode, existing_outputs=exists):
                            output = folder / f"out-{mode}-{exists}"
                            if exists:
                                output.mkdir()
                                (output / f"{first}.html").write_bytes(b"approved prior HTML")
                                write_snapshot(resolve_palette(), output / "palette.resolved.json")
                                builder.font_css(output, "shared")
                            before = {path.relative_to(folder): path.read_bytes()
                                      for path in folder.rglob("*") if path.is_file()}
                            result = subprocess.run([sys.executable, str(SKILL / "engine/build.py"),
                                                     str(output), *map(str, sources), "--font-mode", mode],
                                                    capture_output=True, text=True)
                            self.assertEqual(result.returncode, 2, result.stderr)
                            self.assertIn("batch output destinations collide", result.stderr)
                            self.assertTrue(all(str(source) in result.stderr for source in sources))
                            self.assertNotIn("built ", result.stdout)
                            after = {path.relative_to(folder): path.read_bytes()
                                     for path in folder.rglob("*") if path.is_file()}
                            self.assertEqual(after, before)
                            self.assertEqual(output.exists(), exists)
                            self.assertEqual(list(folder.rglob(".broll-build-preflight-*")), [])
        if not checked:
            self.skipTest("target filesystem has no case/normalization aliases for these fixtures")

    def test_batch_distinct_outputs_build_in_both_font_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            sources = [folder / "one.html", folder / "two.html"]
            for index, source in enumerate(sources):
                source.write_text(f"<title>DISTINCT {index}</title>")
            for mode in ("shared", "embedded"):
                output = folder / mode
                result = subprocess.run([sys.executable, str(SKILL / "engine/build.py"),
                                         str(output), *map(str, sources), "--font-mode", mode],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.count("built "), 2)
                for index, source in enumerate(sources):
                    self.assertIn(f"<title>DISTINCT {index}</title>", (output / source.name).read_text())
                self.assertEqual((output / "assets/broll-me-fonts").exists(), mode == "shared")
            self.assertEqual(list(folder.rglob(".broll-build-preflight-*")), [])

    def test_batch_case_sensitive_filesystem_allows_case_only_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            probe = folder / "CASE-PROBE"
            probe.touch()
            if (folder / "case-probe").exists():
                self.skipTest("target filesystem treats case-only names as aliases")
            sources = [folder / "a" / "Intro.html", folder / "b" / "intro.html"]
            for index, source in enumerate(sources):
                source.parent.mkdir()
                source.write_text(f"<title>CASE {index}</title>")
            output = folder / "out"
            builder.preflight_outputs(sources, [output / source.name for source in sources], resolve_palette())
            self.assertFalse(output.exists())
            result = subprocess.run([sys.executable, str(SKILL / "engine/build.py"), str(output),
                                     *map(str, sources), "--font-mode", "shared"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((output / "Intro.html").samefile(output / "intro.html"))

    def test_build_rejects_output_symlink_and_preserves_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            target = folder / "unrelated.html"
            target.write_text("user-owned output")
            destination = folder / "out" / "clip.html"
            destination.parent.mkdir()
            destination.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink.*use a new output directory"):
                build(SKILL / "examples/palette-demo.html", destination, font_mode="shared")
            self.assertTrue(destination.is_symlink())
            self.assertEqual(target.read_text(), "user-owned output")
            self.assertEqual(list(destination.parent.iterdir()), [destination])

    def test_build_atomic_replace_preserves_input_if_alias_appears_at_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            source = folder / "source.html"
            source.write_bytes((SKILL / "examples/palette-demo.html").read_bytes())
            original = source.read_bytes()
            destination = folder / "out" / "clip.html"
            replace = os.replace

            def replace_with_racing_alias(temporary, output):
                os.link(source, output)
                replace(temporary, output)

            with patch.object(builder.os, "replace", side_effect=replace_with_racing_alias):
                build(source, destination, font_mode="shared")
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse(destination.samefile(source))
            self.assertIn("<!doctype html>", destination.read_text())
            self.assertEqual(list(destination.parent.glob(".broll-build-*")), [])

    def test_conflicting_palette_after_preflight_preserves_prior_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            destination = folder / "scene.html"
            destination.write_bytes(b"approved prior HTML")
            snapshot = folder / "palette.resolved.json"

            def publish_conflict(*args):
                write_snapshot(resolve_palette("midnight-cyan"), snapshot)
                return ""

            with patch.object(builder, "font_css", side_effect=publish_conflict):
                with self.assertRaisesRegex(PaletteError, "midnight-cyan"):
                    build(SKILL / "examples/palette-demo.html", destination)
            self.assertEqual(destination.read_bytes(), b"approved prior HTML")
            self.assertEqual(json.loads(snapshot.read_text())["id"], "midnight-cyan")
            self.assertEqual(list(folder.glob(".broll-*")), [])

    def test_html_publication_failure_rolls_back_only_its_new_snapshot(self):
        for existing in (False, True):
            with self.subTest(existing_snapshot=existing), tempfile.TemporaryDirectory() as tmp:
                folder = pathlib.Path(tmp)
                destination = folder / "scene.html"
                destination.write_bytes(b"approved prior HTML")
                snapshot = folder / "palette.resolved.json"
                if existing:
                    write_snapshot(resolve_palette(), snapshot)
                    original = snapshot.read_bytes(), snapshot.stat().st_mtime_ns
                with patch.object(builder.os, "replace", side_effect=OSError("HTML publication failed")):
                    with self.assertRaisesRegex(OSError, "HTML publication failed"):
                        build(SKILL / "examples/palette-demo.html", destination, font_mode="shared")
                self.assertEqual(destination.read_bytes(), b"approved prior HTML")
                if existing:
                    self.assertEqual((snapshot.read_bytes(), snapshot.stat().st_mtime_ns), original)
                else:
                    self.assertFalse(snapshot.exists())
                self.assertEqual(list(folder.glob(".broll-*")), [])

    def test_failed_snapshot_rollback_retains_recovery_and_blocks_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = pathlib.Path(tmp)
            destination = folder / "scene.html"
            destination.write_bytes(b"approved prior HTML")
            snapshot = folder / "palette.resolved.json"
            unlink = pathlib.Path.unlink

            def fail_snapshot_unlink(path, *args, **kwargs):
                if path == snapshot:
                    raise OSError("snapshot rollback failed")
                return unlink(path, *args, **kwargs)

            with patch.object(builder.os, "replace", side_effect=OSError("HTML publication failed")), \
                 patch.object(pathlib.Path, "unlink", new=fail_snapshot_unlink):
                with self.assertRaisesRegex(PaletteRecoveryError, "recovery files retained"):
                    build(SKILL / "examples/palette-demo.html", destination, font_mode="shared")
            self.assertEqual(destination.read_bytes(), b"approved prior HTML")
            self.assertEqual(json.loads(snapshot.read_text()), resolve_palette())
            stages = list(folder.glob(".broll-build-*"))
            self.assertEqual(len(stages), 1)
            self.assertIn("<!doctype html>", (stages[0] / destination.name).read_text())
            lock = folder / ".broll-palette.lock"
            self.assertTrue(lock.is_dir())
            before = destination.read_bytes(), snapshot.read_bytes()
            with self.assertRaisesRegex(PaletteError, "writer lock exists"):
                build(SKILL / "examples/palette-demo.html", destination, font_mode="shared")
            with self.assertRaisesRegex(PaletteError, "writer lock exists"):
                write_snapshot(resolve_palette(), snapshot)
            self.assertEqual((destination.read_bytes(), snapshot.read_bytes()), before)
            self.assertTrue(lock.is_dir())
            self.assertEqual(list(folder.glob(".broll-build-*")), stages)

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
