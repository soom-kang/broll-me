"""Regression coverage for subtitle, insertion, and review-page contracts."""
from fractions import Fraction
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "broll-me"
sys.path.insert(0, str(SKILL / "scripts"))
import composite
import inspect_video
import make_pages
import media
import preview_bundle
import words
import fonts


def info(duration=10, alpha=False):
    return {"width": 320, "height": 180, "duration": duration, "fps": "30000/1001", "rate": Fraction(30000, 1001), "audio": [], "stream": {"pix_fmt": "yuva444p10le" if alpha else "yuv420p", "start_time": "0", "duration": str(duration)}}


def case_alias(test, path):
    alias = path.with_name(path.name.swapcase())
    if not alias.exists() or not alias.samefile(path):
        test.skipTest("Fixture filesystem does not expose a case-equivalent file alias")
    test.assertNotEqual(alias.resolve(), path.resolve())
    return alias


class SubtitleTests(unittest.TestCase):
    def test_reserved_prefix_cue_ids_are_preserved(self):
        blocks = ["WEBVTT", "NOTE comment\nignored", "STYLE\n::cue { color: white; }", "REGION\nid:local"]
        identifiers = ["opening", "NOTEworthy", "STYLE-demo", "REGION-1", "WEBVTT-demo"]
        blocks += [f"{identifier}\n00:{index:02d}.000 --> 00:{index + 1:02d}.000\n{identifier}"
                   for index, identifier in enumerate(identifiers, 1)]
        cues = words.parse_cues("\n\n".join(blocks))
        self.assertEqual([cue[2] for cue in cues], [[identifier] for identifier in identifiers])
        self.assertEqual([(cue[0], cue[1]) for cue in cues], [(index, index + 1) for index in range(1, 6)])

    def test_srt_and_vtt_have_same_estimates(self):
        srt = "1\r\n00:00:01,000 --> 00:00:03,000\r\n원하는 색감\r\n"
        vtt = "\ufeffWEBVTT\n\nNOTE local note\nignored\n\nopening\n00:01.000 --> 00:03.000 align:start position:10%\n<v Speaker><b>원하는</b> 색감\n"
        self.assertEqual(list(words.estimated_words(words.parse_cues(srt))), list(words.estimated_words(words.parse_cues(vtt))))

    def test_subtitle_invalid_timing_fails(self):
        for text in ["1\n00:00:03,000 --> 00:00:01,000\na", "WEBVTT\n\n00:65.000 --> 01:10.000\na", "plain transcript"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                words.parse_cues(text)

    def test_estimates_stay_inside_cue(self):
        result = list(words.estimated_words([(1, 2, ["one", "longer", "three"])]))[0]
        times = [float(item.split(":", 1)[0]) for item in result.split()]
        self.assertEqual(times[0], 1)
        self.assertTrue(all(1 <= value < 2 for value in times))
        self.assertEqual(times, sorted(times))


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="broll-delivery-")
        self.directory = Path(self.temp.name)
        for name in ["source #?.mp4", "clip with spaces.mp4", "panel.mov"]:
            (self.directory / name).write_bytes(b"fixture")
        self.plan = {"video": "source #?.mp4", "fps": "30000/1001", "clips": [{"id": "01", "title": "clip", "in": 2, "out": 8, "kind": "full", "file": "clip with spaces.mp4"}]}

    def tearDown(self):
        self.temp.cleanup()

    def load(self, plan=None):
        path = self.directory / "plan.json"
        path.write_text(json.dumps(plan or self.plan), encoding="utf-8")
        def fake_probe(value):
            return info(10 if Path(value).name.startswith("source") else 1, Path(value).suffix == ".mov")
        with patch.object(media, "probe", side_effect=fake_probe):
            return media.load_plan(path)

    def test_short_clip_holds_full_slot_and_audio_copy_has_no_shortest(self):
        _, source, source_info, clips = self.load()
        command = composite.composite_command(source, source_info, clips, self.directory / "output with spaces.mp4")
        filters = command[command.index("-filter_complex") + 1]
        self.assertIn("stop_duration=5.033366667", filters)
        self.assertIn("lt(t,8.000000000)", filters)
        self.assertEqual(command[command.index("-c:a") + 1], "copy")
        self.assertEqual(command[command.index("-r") + 1], "30000/1001")
        self.assertEqual(command[command.index("-t") + 1], "10")
        self.assertNotIn("-shortest", command)
        self.assertIn(str((self.directory / "clip with spaces.mp4").resolve()), command)

    def test_out_of_bounds_and_overlap_fail(self):
        self.plan["clips"][0]["out"] = 11
        with self.assertRaisesRegex(media.MediaError, "outside source"):
            self.load()
        self.plan["clips"][0]["out"] = 8
        self.plan["clips"].append({"id": "02", "title": "other", "in": 4, "out": 9, "kind": "full", "file": "clip with spaces.mp4"})
        with self.assertRaisesRegex(media.MediaError, "overlap"):
            self.load()

    def test_wrong_fps_and_panel_container_fail(self):
        self.plan["fps"] = "30"
        with self.assertRaisesRegex(media.MediaError, "differs from source"):
            self.load()
        self.plan["fps"] = "30000/1001"
        self.plan["clips"][0]["kind"] = "panel"
        with self.assertRaisesRegex(media.MediaError, "requires .mov"):
            self.load()

    def test_atomic_failure_preserves_previous_output_and_source(self):
        output = self.directory / "preview.mp4"
        output.write_bytes(b"previous")
        with self.assertRaises(RuntimeError):
            with media.atomic_output(output) as temporary:
                temporary.write_bytes(b"partial")
                raise RuntimeError("encoder failed")
        self.assertEqual(output.read_bytes(), b"previous")
        self.assertEqual(list(self.directory.glob(".broll-*")), [])
        with self.assertRaisesRegex(media.MediaError, "overwrite"):
            with media.atomic_output(output, inputs=[output]):
                self.fail("Must not permit source overwrite")

    def test_atomic_success_replaces_previous_output(self):
        output = self.directory / "preview.mp4"
        output.write_bytes(b"previous")
        with media.atomic_output(output, suffix=".mp4") as temporary:
            temporary.write_bytes(b"new preview")
        self.assertEqual(output.read_bytes(), b"new preview")
        self.assertEqual(list(self.directory.glob(".broll-*")), [])

    def test_atomic_case_alias_refuses_before_first_write(self):
        source = self.directory / "SOURCE.mp4"
        source.write_bytes(b"protected source")
        output = case_alias(self, source)
        with patch.object(Path, "mkdir") as create_directory, \
             patch.object(media.tempfile, "mkstemp") as create_temporary:
            with self.assertRaisesRegex(media.MediaError, "overwrite"):
                with media.atomic_output(output, inputs=[source], suffix=".mp4"):
                    self.fail("Must reject a filesystem-equivalent protected input")
        create_directory.assert_not_called()
        create_temporary.assert_not_called()
        self.assertEqual(source.read_bytes(), b"protected source")

    def test_atomic_distinct_hardlink_to_readable_input_symlink_is_rejected(self):
        source = self.directory / "protected.mp4"
        source.write_bytes(b"protected source")
        readable = self.directory / "readable-input.mp4"
        readable.symlink_to(source)
        output = self.directory / "distinct-hardlink.mp4"
        os.link(source, output)
        self.assertNotEqual(source.resolve(), output.resolve())
        with patch.object(media.tempfile, "mkstemp") as create_temporary:
            with self.assertRaisesRegex(media.MediaError, "overwrite"):
                with media.atomic_output(output, inputs=[readable], suffix=".mp4"):
                    self.fail("Output hardlinks to protected inputs are conservatively refused")
        create_temporary.assert_not_called()
        self.assertTrue(readable.is_symlink())
        self.assertTrue(source.samefile(output))
        self.assertEqual(source.read_bytes(), b"protected source")
        self.assertEqual(output.read_bytes(), b"protected source")

    def test_atomic_rechecks_input_identity_before_publication(self):
        source = self.directory / "protected.mp4"
        source.write_bytes(b"protected source")
        output = self.directory / "new-output.mp4"
        with self.assertRaisesRegex(media.MediaError, "overwrite"):
            with media.atomic_output(output, inputs=[source], suffix=".mp4") as temporary:
                temporary.write_bytes(b"new preview")
                os.link(source, output)
        self.assertTrue(source.samefile(output))
        self.assertEqual(source.read_bytes(), b"protected source")
        self.assertEqual(list(self.directory.glob(".broll-*")), [])

    def test_case_sensitive_distinct_files_are_not_rejected_by_name(self):
        source = self.directory / "PROTECTED.mp4"
        source.write_bytes(b"protected source")
        output = self.directory / "protected.mp4"
        if output.exists():
            self.skipTest("Fixture filesystem is case-insensitive; distinct case-only entries unavailable")
        output.write_bytes(b"previous distinct output")
        self.assertFalse(source.samefile(output))
        with media.atomic_output(output, inputs=[source], suffix=".mp4") as temporary:
            temporary.write_bytes(b"new preview")
        self.assertEqual(source.read_bytes(), b"protected source")
        self.assertEqual(output.read_bytes(), b"new preview")

    def test_output_preflight_and_atomic_output_reject_nonregular_paths_without_writes(self):
        missing = self.directory / "missing" / "output.mp4"
        media.validate_output_path(missing)
        self.assertFalse(missing.parent.exists())
        regular = self.directory / "regular.mp4"
        regular.write_bytes(b"previous regular output")
        media.validate_output_path(regular)
        self.assertEqual(regular.read_bytes(), b"previous regular output")
        for kind in ["directory", "fifo", "parent-file"]:
            with self.subTest(kind=kind):
                blocked = self.directory / (kind + ".mp4")
                if kind == "directory":
                    blocked.mkdir()
                    (blocked / "keep.bin").write_bytes(b"unrelated directory contents")
                    output = blocked
                elif kind == "fifo":
                    os.mkfifo(blocked)
                    output = blocked
                else:
                    blocked.write_bytes(b"unrelated parent file")
                    output = blocked / "child.mp4"
                with self.assertRaises(media.MediaError):
                    media.validate_output_path(output)
                with patch.object(media.tempfile, "mkstemp") as create_temporary:
                    with self.assertRaises(media.MediaError):
                        with media.atomic_output(output):
                            self.fail("Must reject before creating a temporary output")
                create_temporary.assert_not_called()
                self.assertEqual(list(self.directory.glob(".broll-*")), [])
                if kind == "directory":
                    self.assertEqual((blocked / "keep.bin").read_bytes(), b"unrelated directory contents")
                elif kind == "fifo":
                    self.assertTrue(stat.S_ISFIFO(blocked.lstat().st_mode))
                else:
                    self.assertEqual(blocked.read_bytes(), b"unrelated parent file")

    def test_atomic_rejects_existing_and_dangling_output_symlinks(self):
        for present in [True, False]:
            with self.subTest(target_present=present):
                target = self.directory / f"target-{present}.mp4"
                if present:
                    target.write_bytes(b"target unchanged")
                output = self.directory / f"alias-{present}.mp4"
                output.symlink_to(target)
                with self.assertRaisesRegex(media.MediaError, "symlink"):
                    with media.atomic_output(output, suffix=".mp4"):
                        self.fail("Must not render to an output symlink")
                self.assertTrue(output.is_symlink())
                self.assertEqual(output.readlink(), target)
                if present:
                    self.assertEqual(target.read_bytes(), b"target unchanged")
                else:
                    self.assertFalse(target.exists())
        self.assertEqual(list(self.directory.glob(".broll-*")), [])

    def test_atomic_rejects_output_parent_symlink(self):
        target = self.directory / "target-directory"
        target.mkdir()
        (target / "preview.mp4").write_bytes(b"previous")
        alias = self.directory / "output-directory"
        alias.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(media.MediaError, "symlink"):
            with media.atomic_output(alias / "preview.mp4", suffix=".mp4"):
                self.fail("Must not render through a directory symlink")
        self.assertTrue(alias.is_symlink())
        self.assertEqual((target / "preview.mp4").read_bytes(), b"previous")
        self.assertEqual(list(target.glob(".broll-*")), [])

    def test_atomic_rejects_symlink_inserted_before_publication(self):
        output = self.directory / "preview.mp4"
        target = self.directory / "target.mp4"
        target.write_bytes(b"target unchanged")
        with self.assertRaisesRegex(media.MediaError, "symlink"):
            with media.atomic_output(output, suffix=".mp4") as temporary:
                temporary.write_bytes(b"new preview")
                output.symlink_to(target)
        self.assertTrue(output.is_symlink())
        self.assertEqual(output.readlink(), target)
        self.assertEqual(target.read_bytes(), b"target unchanged")
        self.assertEqual(list(self.directory.glob(".broll-*")), [])

    def test_atomic_late_parent_symlink_cleanup_preserves_target(self):
        parent = self.directory / "output-directory"
        parent.mkdir()
        (parent / "preview.mp4").write_bytes(b"previous")
        target = self.directory / "target-directory"
        target.mkdir()
        (target / "preview.mp4").write_bytes(b"target unchanged")
        saved = self.directory / "saved-directory"
        with self.assertRaisesRegex(media.MediaError, "symlink"):
            with media.atomic_output(parent / "preview.mp4", suffix=".mp4") as temporary:
                temporary.write_bytes(b"new preview")
                (target / temporary.name).write_bytes(b"unrelated target file")
                parent.rename(saved)
                parent.symlink_to(target, target_is_directory=True)
        self.assertTrue(parent.is_symlink())
        self.assertEqual((saved / "preview.mp4").read_bytes(), b"previous")
        self.assertEqual((target / "preview.mp4").read_bytes(), b"target unchanged")
        self.assertEqual((target / temporary.name).read_bytes(), b"unrelated target file")
        self.assertEqual(list(saved.glob(".broll-*")), [])


class ReviewAndLayoutTests(unittest.TestCase):
    def test_shared_font_validation_is_read_only_and_accepts_identical_assets(self):
        with tempfile.TemporaryDirectory(prefix="broll-font-preflight-") as directory:
            output = Path(directory) / "missing" / "export"
            fonts.validate_shared_fonts(output)
            self.assertFalse(output.parent.exists())
            css = fonts.font_css(output, "shared")
            files = {path: path.read_bytes() for path in output.rglob("*") if path.is_file()}
            fonts.validate_shared_fonts(output)
            self.assertEqual(fonts.font_css(output, "shared"), css)
            self.assertEqual({path: path.read_bytes() for path in output.rglob("*") if path.is_file()}, files)

    def test_font_modes_retain_complete_notices_and_shared_asset_bytes(self):
        with tempfile.TemporaryDirectory(prefix="broll-font-notices-") as directory:
            output = Path(directory) / "export"
            css = fonts.font_css(output, "embedded")
            self.assertFalse(output.exists())
            self.assertEqual(css.count("data:font/"), 3)
            comments = dict(re.findall(r"/\* Font notice: ([^\n]+)\n(.*?)\n\*/", css, re.S))
            for filename in fonts.NOTICES:
                self.assertEqual(html.unescape(comments[filename]), (fonts.FONTS / filename).read_text(encoding="utf-8"))
            shared_css = fonts.font_css(output, "shared")
            self.assertNotIn("data:font/", shared_css)
            asset_dir = output / "assets" / "broll-me-fonts"
            filenames = [filename for _, filename, _, _ in fonts.FONT_FILES] + list(fonts.NOTICES)
            self.assertEqual(sorted(path.name for path in asset_dir.iterdir()), sorted(filenames))
            for filename in filenames:
                self.assertEqual((asset_dir / filename).read_bytes(), (fonts.FONTS / filename).read_bytes())
            self.assertEqual(fonts.font_css(output, "shared"), shared_css)
            (asset_dir / fonts.NOTICES[0]).write_text("unrelated notice", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "font asset differs"):
                fonts.font_css(output, "shared")
            self.assertEqual((asset_dir / fonts.NOTICES[0]).read_text(encoding="utf-8"), "unrelated notice")

    def test_required_font_notices_fail_before_asset_creation_in_both_modes(self):
        for mode in ["embedded", "shared"]:
            for filename in fonts.NOTICES:
                for failure in ["missing", "empty"]:
                    with self.subTest(mode=mode, filename=filename, failure=failure), \
                         tempfile.TemporaryDirectory(prefix="broll-font-notices-") as directory:
                        source = Path(directory) / "fonts"
                        shutil.copytree(fonts.FONTS, source)
                        if failure == "missing":
                            (source / filename).unlink()
                        else:
                            (source / filename).write_text(" \n\t", encoding="utf-8")
                        output = Path(directory) / "export"
                        with patch.object(fonts, "FONTS", source), \
                             self.assertRaisesRegex(ValueError, f"font notice is {failure}"):
                            fonts.font_css(output, mode)
                        self.assertFalse(output.exists())

    def test_embedded_notice_cannot_end_the_css_comment_or_style_element(self):
        notice = "Copyright fixture & contributors &lt; *&#47;\n*/ </StYlE><script>bad()</script>\n<terms>"
        with tempfile.TemporaryDirectory(prefix="broll-font-notices-") as directory:
            source = Path(directory) / "fonts"
            shutil.copytree(fonts.FONTS, source)
            (source / fonts.NOTICES[0]).write_text(notice, encoding="utf-8")
            with patch.object(fonts, "FONTS", source):
                css = fonts.font_css(Path(directory) / "export", "embedded")
        self.assertNotIn("<", css)
        self.assertEqual(css.count("*/"), len(fonts.NOTICES))
        comments = dict(re.findall(r"/\* Font notice: ([^\n]+)\n(.*?)\n\*/", css, re.S))
        self.assertEqual(html.unescape(comments[fonts.NOTICES[0]]), notice)
        self.assertEqual(css.count("@font-face"), 3)

    def test_inserted_metadata_is_not_template_input(self):
        data = {"title": "/*TITLE*/ /*CLIPS*/[]", "line": "Use /*FONT_CSS*/ here </script>"}
        source = "<title>/*TITLE*/</title><script>const clips=/*CLIPS*/[];</script>/*FONT_CSS*/"
        filled = make_pages.fill_template(source, {
            "/*TITLE*/": data["title"], "/*CLIPS*/[]": make_pages.script_json(data),
            "/*FONT_CSS*/": "font-css\nsecond-line",
        })
        payload = filled.split("const clips=", 1)[1].split(";</script>", 1)[0]
        self.assertEqual(json.loads(payload), data)
        self.assertIn("<title>/*TITLE*/ /*CLIPS*/[]</title>", filled)
        self.assertEqual(filled.count("font-css\nsecond-line"), 1)

    def test_metadata_script_escape_roundtrips(self):
        data = {"title": "</script><img src=x onerror=alert(1)> & \u2028 \u2029"}
        encoded = make_pages.script_json(data)
        self.assertNotIn("<", encoded)
        self.assertNotIn("\u2028", encoded)
        self.assertEqual(json.loads(encoded), data)

    def test_local_fonts_and_dom_metadata(self):
        self.assertIn("data:font/woff2;base64,", make_pages.local_fonts())
        self.assertIn("font-family:'Noto Sans KR'", make_pages.local_fonts())
        for name in ["viewer.html", "compare.html"]:
            source = (SKILL / "templates" / name).read_text(encoding="utf-8")
            self.assertNotIn("fonts.googleapis.com", source)
            self.assertNotIn("innerHTML", source)
            self.assertIn("textContent", source)

    def test_url_and_markdown_escape(self):
        self.assertEqual(make_pages.web_path(Path("/tmp/folder #?/clip.mp4"), Path("/tmp")), "folder%20%23%3F/clip.mp4")
        self.assertEqual(make_pages.markdown_cell("a|b\nnext"), "a\\|b next")

    def test_dark_frames_do_not_invent_subject_box(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("NumPy not available; run using runtime virtualenv")
        sections = inspect_video.analyze_frames(np.zeros((4, 54, 96), dtype=np.uint8), 320, 180, 1)
        self.assertEqual(sections[0]["layout"], "unknown")
        self.assertNotIn("subject_box", sections[0])
        self.assertFalse(sections[0]["verified"])


class ProjectFolderDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="broll-project-delivery-")
        self.directory = Path(self.temp.name).resolve()
        self.inputs = self.directory / "inputs"
        self.work = self.directory / "works" / "folder-routing"
        self.output = self.directory / "outputs" / "folder-routing"
        for folder in [self.inputs, self.work, self.output]:
            folder.mkdir(parents=True)
        self.source = self.inputs / "source.mp4"
        self.clip = self.output / "clip with spaces.mp4"
        self.preview = self.output / "preview.mp4"
        for path, content in [(self.source, b"source fixture"), (self.clip, b"clip fixture"), (self.preview, b"previous preview")]:
            path.write_bytes(content)
        self.plan = {
            "title": "Project folder delivery", "video": "../../inputs/source.mp4", "fps": "30000/1001",
            "clips": [{"id": "01", "title": "clip", "in": 2, "out": 8, "kind": "full", "file": "../../outputs/folder-routing/clip with spaces.mp4"}],
        }
        self.plan_path = self.work / "plan.json"
        self.write_plan()

    def tearDown(self):
        self.temp.cleanup()

    def write_plan(self):
        self.plan_path.write_text(json.dumps(self.plan), encoding="utf-8")

    def fake_probe(self, path):
        return info(1 if Path(path) == self.clip else 10)

    def tree_state(self):
        """Record bytes and entry types without opening FIFOs or following aliases."""
        state = {}
        for path in self.directory.rglob("*"):
            contents = str(path.readlink()) if path.is_symlink() else path.read_bytes() if path.is_file() else None
            state[str(path.relative_to(self.directory))] = (stat.S_IFMT(path.lstat().st_mode), contents)
        return state

    def test_plan_resolves_inputs_and_outputs_from_work_directory(self):
        with patch.object(media, "probe", side_effect=self.fake_probe):
            _, source, _, clips = media.load_plan(self.plan_path)
        self.assertEqual(source, self.source.resolve())
        self.assertEqual(clips[0]["path"], self.clip.resolve())
        self.assertEqual(self.source.read_bytes(), b"source fixture")

    def test_selected_parent_symlink_is_rejected_by_media_entry_points(self):
        alias = self.directory / "output-alias"
        alias.symlink_to(self.output, target_is_directory=True)
        actions = [
            ("inspection", lambda: inspect_video.inspect_video(self.source, alias)),
            ("review pages", lambda: make_pages.write_pages(self.plan_path, alias / self.preview.name)),
            ("preview bundle", lambda: preview_bundle.create_bundle(self.plan_path, alias / self.preview.name)),
        ]
        with patch.dict(sys.modules, {"numpy": object()}), \
             patch.object(media, "probe", side_effect=self.fake_probe), \
             patch.object(inspect_video, "probe") as inspection_probe, \
             patch.object(make_pages, "probe") as pages_probe, \
             patch.object(preview_bundle, "create_preview") as render:
            for name, action in actions:
                with self.subTest(entry_point=name), self.assertRaisesRegex(media.MediaError, "symlink"):
                    action()
        inspection_probe.assert_not_called()
        pages_probe.assert_not_called()
        render.assert_not_called()
        self.assertTrue(alias.is_symlink())
        self.assertEqual(self.preview.read_bytes(), b"previous preview")
        self.assertEqual(self.source.read_bytes(), b"source fixture")
        self.assertFalse((self.output / "viewer.html").exists())

    def test_readable_preview_symlink_keeps_selected_output_directory(self):
        selected = self.directory / "selected-review-directory"
        selected.mkdir()
        alias = selected / "preview-link.mp4"
        alias.symlink_to(self.preview)
        with patch.object(media, "probe", side_effect=self.fake_probe), \
             patch.object(make_pages, "probe", side_effect=self.fake_probe):
            pages = make_pages.write_pages(self.plan_path, alias)
        self.assertEqual(pages, [selected / name for name in ["viewer.html", "compare.html", "TIMING.md"]])
        viewer = pages[0].read_text(encoding="utf-8")
        clips = json.loads(viewer.split("const CLIPS=", 1)[1].split(";", 1)[0])
        self.assertEqual((selected / unquote(clips[0]["src"])).resolve(), self.preview)
        self.assertTrue(alias.is_symlink())
        self.assertEqual(self.preview.read_bytes(), b"previous preview")
        self.assertFalse((self.output / "viewer.html").exists())

    def test_review_output_case_aliases_protect_all_inputs_before_writes(self):
        for role in ["source", "plan", "clip", "preview"]:
            with self.subTest(protected_input=role):
                output = self.output / ("case-" + role)
                output.mkdir()
                source, clip = self.source, self.clip
                preview = output / "preview.mp4"
                preview.write_bytes(b"previous preview")
                plan_path = output / "plan.json"
                protected = output / ("timing.MD" if role == "plan" else "01-PANEL_PREVIEW.MP4" if role == "clip" else "COMPARE.HTML")
                protected.write_bytes(b"protected input")
                alias = case_alias(self, protected)
                if role == "source":
                    source = protected
                elif role == "clip":
                    clip = protected
                elif role == "preview":
                    preview = protected
                else:
                    plan_path = protected
                plan = json.loads(json.dumps(self.plan))
                plan["video"] = str(source)
                plan["clips"][0]["file"] = str(clip)
                if role == "clip":
                    panel = output / "panel.mov"
                    panel.write_bytes(b"panel input")
                    plan["clips"] = [
                        {"id": "01", "title": "panel", "in": 2, "out": 3, "kind": "panel", "file": str(panel)},
                        {**plan["clips"][0], "id": "02", "in": 4, "out": 5},
                    ]
                plan_path.write_text(json.dumps(plan), encoding="utf-8")
                before = self.tree_state()
                def fake_probe(path):
                    return info(1 if Path(path) == clip or Path(path).suffix == ".mov" else 10, Path(path).suffix == ".mov")
                with patch.object(media, "probe", side_effect=fake_probe), \
                     patch.object(make_pages, "probe") as preview_probe, \
                     patch.object(make_pages, "run") as panel_encoder, \
                     patch.object(make_pages, "local_fonts") as copy_fonts, \
                     patch.object(media.tempfile, "mkstemp") as create_temporary:
                    with self.assertRaisesRegex(media.MediaError, "overwrite"):
                        make_pages.write_pages(plan_path, preview, font_mode="shared")
                for operation in [preview_probe, panel_encoder, copy_fonts, create_temporary]:
                    operation.assert_not_called()
                self.assertTrue(alias.samefile(protected))
                self.assertEqual(self.tree_state(), before)

    def test_inspection_report_case_alias_refuses_before_contact_or_encoder(self):
        source = self.output / "VIDEO.JSON"
        source.write_bytes(b"protected source")
        case_alias(self, source)
        contact = self.output / "contact.png"
        contact.write_bytes(b"previous contact")
        before = self.tree_state()
        with patch.dict(sys.modules, {"numpy": object()}), \
             patch.object(inspect_video, "probe") as source_probe, \
             patch.object(inspect_video, "run") as encoder, \
             patch.object(media.tempfile, "mkstemp") as create_temporary:
            with self.assertRaisesRegex(media.MediaError, "overwrite"):
                inspect_video.inspect_video(source, self.output)
        for operation in [source_probe, encoder, create_temporary]:
            operation.assert_not_called()
        self.assertEqual(self.tree_state(), before)

    def test_later_review_page_aliases_fail_before_any_output_or_font_changes(self):
        for filename in ["compare.html", "TIMING.md"]:
            for present in [True, False]:
                with self.subTest(filename=filename, target_present=present):
                    previous = {name: ("previous " + name).encode() for name in ["viewer.html", "compare.html", "TIMING.md"]}
                    for name, content in previous.items():
                        (self.output / name).write_bytes(content)
                    target = self.directory / f"target-{filename}-{present}"
                    if present:
                        target.write_bytes(b"target unchanged")
                    alias = self.output / filename
                    alias.unlink()
                    alias.symlink_to(target)
                    with patch.object(media, "probe") as source_probe, \
                         patch.object(make_pages, "run") as render, \
                         patch.object(make_pages, "local_fonts") as copy_fonts:
                        with self.assertRaisesRegex(media.MediaError, "symlink"):
                            make_pages.write_pages(self.plan_path, self.preview, font_mode="shared")
                    source_probe.assert_not_called()
                    render.assert_not_called()
                    copy_fonts.assert_not_called()
                    for name, content in previous.items():
                        if name != filename:
                            self.assertEqual((self.output / name).read_bytes(), content)
                    self.assertTrue(alias.is_symlink())
                    self.assertEqual(alias.readlink(), target)
                    if present:
                        self.assertEqual(target.read_bytes(), b"target unchanged")
                    else:
                        self.assertFalse(target.exists())
                    self.assertFalse((self.output / "assets").exists())
                    self.assertEqual(list(self.output.glob(".broll-*")), [])
                    alias.unlink()

    def test_nonregular_page_and_inspection_outputs_fail_before_any_write(self):
        for filename in ["compare.html", "TIMING.md", "video.json"]:
            with self.subTest(filename=filename):
                output = self.output / ("directory-" + filename)
                output.mkdir()
                preview = output / "preview.mp4"
                preview.write_bytes(b"previous preview")
                for name in ["viewer.html", "compare.html", "TIMING.md", "contact.png", "video.json"]:
                    (output / name).write_bytes(("previous " + name).encode())
                (output / filename).unlink()
                (output / filename).mkdir()
                (output / filename / "keep.txt").write_bytes(b"unrelated output-directory contents")
                asset = output / "assets" / "keep.bin"
                asset.parent.mkdir()
                asset.write_bytes(b"previous asset")
                before = self.tree_state()
                with patch.dict(sys.modules, {"numpy": object()}), \
                     patch.object(media, "probe") as source_probe, \
                     patch.object(inspect_video, "probe") as inspection_probe, \
                     patch.object(make_pages, "probe") as pages_probe, \
                     patch.object(inspect_video, "run") as inspect_encoder, \
                     patch.object(make_pages, "run") as panel_encoder, \
                     patch.object(make_pages, "local_fonts") as copy_fonts:
                    with self.assertRaises(media.MediaError):
                        if filename == "video.json":
                            inspect_video.inspect_video(self.source, output)
                        else:
                            make_pages.write_pages(self.plan_path, preview, font_mode="shared")
                for operation in [source_probe, inspection_probe, pages_probe, inspect_encoder, panel_encoder, copy_fonts]:
                    operation.assert_not_called()
                self.assertEqual(self.tree_state(), before)

    def test_later_nonregular_panel_preview_fails_before_other_outputs_change(self):
        self.plan["clips"] = [
            {"id": str(index), "title": "panel", "in": index * 2, "out": index * 2 + 1,
             "kind": "panel", "file": f"../../outputs/folder-routing/panel-{index}.mov"}
            for index in [1, 2]
        ]
        for index in [1, 2]:
            (self.output / f"panel-{index}.mov").write_bytes(b"panel input")
        self.write_plan()
        def panel_probe(path):
            return info(1 if Path(path).suffix == ".mov" else 10, Path(path).suffix == ".mov")
        for kind in ["directory", "fifo"]:
            with self.subTest(kind=kind):
                output = self.output / ("panel-" + kind)
                output.mkdir()
                preview = output / "preview.mp4"
                preview.write_bytes(b"previous preview")
                for name in ["viewer.html", "compare.html", "TIMING.md", "01-panel-1_preview.mp4"]:
                    (output / name).write_bytes(("previous " + name).encode())
                asset = output / "assets" / "keep.bin"
                asset.parent.mkdir()
                asset.write_bytes(b"previous asset")
                blocked = output / "02-panel-2_preview.mp4"
                if kind == "directory":
                    blocked.mkdir()
                    (blocked / "keep.txt").write_bytes(b"unrelated directory contents")
                else:
                    os.mkfifo(blocked)
                before = self.tree_state()
                with patch.object(media, "probe", side_effect=panel_probe), \
                     patch.object(make_pages, "probe", side_effect=panel_probe), \
                     patch.object(make_pages, "run") as render, \
                     patch.object(make_pages, "local_fonts") as copy_fonts:
                    with self.assertRaises(media.MediaError):
                        make_pages.write_pages(self.plan_path, preview, font_mode="shared")
                render.assert_not_called()
                copy_fonts.assert_not_called()
                self.assertEqual(self.tree_state(), before)

    def test_shared_font_conflicts_fail_before_panel_or_review_outputs_change(self):
        panel = self.output / "panel.mov"
        panel.write_bytes(b"panel input")
        self.plan["clips"][0].update(kind="panel", file="../../outputs/folder-routing/panel.mov")
        self.write_plan()
        def panel_probe(path):
            return info(1 if Path(path) == panel else 10, Path(path) == panel)
        cases = ["assets-link", "assets-file", "font-directory-link", "font-directory-file",
                 "font-link", "dangling-font-link", "different-notice", "font-directory", "font-fifo"]
        for conflict in cases:
            with self.subTest(conflict=conflict):
                output = self.output / conflict
                output.mkdir()
                preview = output / "preview.mp4"
                preview.write_bytes(b"previous preview")
                for name in ["viewer.html", "compare.html", "TIMING.md", "01-panel_preview.mp4"]:
                    (output / name).write_bytes(("previous " + name).encode())
                asset_dir = output / "assets" / "broll-me-fonts"
                target = self.directory / (conflict + "-target")
                if conflict in {"assets-link", "font-directory-link"}:
                    target.mkdir()
                    (target / "keep.bin").write_bytes(b"alias target unchanged")
                    alias = asset_dir.parent if conflict == "assets-link" else asset_dir
                    alias.parent.mkdir(parents=True, exist_ok=True)
                    alias.symlink_to(target, target_is_directory=True)
                elif conflict in {"assets-file", "font-directory-file"}:
                    blocked = asset_dir.parent if conflict == "assets-file" else asset_dir
                    blocked.parent.mkdir(parents=True, exist_ok=True)
                    blocked.write_bytes(b"unrelated directory-name file")
                else:
                    asset_dir.mkdir(parents=True)
                    (asset_dir.parent / "keep.bin").write_bytes(b"previous asset")
                    blocked = asset_dir / fonts.NOTICES[-1]
                    if conflict in {"font-link", "dangling-font-link"}:
                        if conflict == "font-link":
                            target.write_bytes(b"alias target unchanged")
                        blocked.symlink_to(target)
                    elif conflict == "different-notice":
                        blocked.write_bytes(b"unrelated notice")
                    elif conflict == "font-directory":
                        blocked.mkdir()
                        (blocked / "keep.bin").write_bytes(b"unrelated font-name directory")
                    else:
                        os.mkfifo(blocked)
                before = self.tree_state()
                with patch.object(media, "probe", side_effect=panel_probe), \
                     patch.object(make_pages, "probe", side_effect=panel_probe), \
                     patch.object(make_pages, "run") as render, \
                     patch.object(make_pages, "local_fonts") as copy_fonts:
                    with self.assertRaises(ValueError):
                        make_pages.write_pages(self.plan_path, preview, font_mode="shared")
                render.assert_not_called()
                copy_fonts.assert_not_called()
                self.assertEqual(self.tree_state(), before)

    def test_embedded_review_pages_ignore_unrelated_shared_font_conflicts(self):
        assets = self.output / "assets"
        assets.write_bytes(b"unrelated assets file")
        with patch.object(media, "probe", side_effect=self.fake_probe), \
             patch.object(make_pages, "probe", side_effect=self.fake_probe):
            pages = make_pages.write_pages(self.plan_path, self.preview, font_mode="embedded")
        self.assertTrue(all(page.is_file() for page in pages))
        self.assertIn("data:font/", pages[0].read_text())
        self.assertEqual(assets.read_bytes(), b"unrelated assets file")
        self.assertEqual(self.source.read_bytes(), b"source fixture")
        self.assertEqual(self.preview.read_bytes(), b"previous preview")

    def test_later_panel_preview_alias_fails_before_first_panel_or_font_changes(self):
        self.plan["clips"] = [
            {"id": str(index), "title": "panel", "in": index * 2, "out": index * 2 + 1,
             "kind": "panel", "file": f"../../outputs/folder-routing/panel-{index}.mov"}
            for index in [1, 2]
        ]
        for index in [1, 2]:
            (self.output / f"panel-{index}.mov").write_bytes(b"panel fixture")
        self.write_plan()
        previous = {name: ("previous " + name).encode() for name in ["viewer.html", "compare.html", "TIMING.md", "01-panel-1_preview.mp4"]}
        for name, content in previous.items():
            (self.output / name).write_bytes(content)
        font_asset = self.output / "assets" / "approved-font.bin"
        font_asset.parent.mkdir()
        font_asset.write_bytes(b"previous font asset")
        target = self.directory / "panel-target.mp4"
        target.write_bytes(b"target unchanged")
        alias = self.output / "02-panel-2_preview.mp4"
        alias.symlink_to(target)
        def panel_probe(path):
            return info(1 if Path(path).suffix == ".mov" else 10, Path(path).suffix == ".mov")
        with patch.object(media, "probe", side_effect=panel_probe), \
             patch.object(make_pages, "run") as render, \
             patch.object(make_pages, "local_fonts") as copy_fonts:
            with self.assertRaisesRegex(media.MediaError, "symlink"):
                make_pages.write_pages(self.plan_path, self.preview, font_mode="shared")
        render.assert_not_called()
        copy_fonts.assert_not_called()
        for name, content in previous.items():
            self.assertEqual((self.output / name).read_bytes(), content)
        self.assertTrue(alias.is_symlink())
        self.assertEqual(alias.readlink(), target)
        self.assertEqual(target.read_bytes(), b"target unchanged")
        self.assertEqual(font_asset.read_bytes(), b"previous font asset")
        self.assertEqual(list(font_asset.parent.iterdir()), [font_asset])
        self.assertEqual(list(self.output.glob(".broll-*")), [])

    def test_inspection_report_alias_fails_before_contact_or_encoder_changes(self):
        contact = self.output / "contact.png"
        contact.write_bytes(b"previous contact")
        target = self.directory / "report-target.json"
        target.write_bytes(b"target unchanged")
        alias = self.output / "video.json"
        alias.symlink_to(target)
        with patch.dict(sys.modules, {"numpy": object()}), \
             patch.object(inspect_video, "probe") as source_probe, \
             patch.object(inspect_video, "run") as render:
            with self.assertRaisesRegex(media.MediaError, "symlink"):
                inspect_video.inspect_video(self.source, self.output)
        source_probe.assert_not_called()
        render.assert_not_called()
        self.assertEqual(contact.read_bytes(), b"previous contact")
        self.assertTrue(alias.is_symlink())
        self.assertEqual(alias.readlink(), target)
        self.assertEqual(target.read_bytes(), b"target unchanged")
        self.assertEqual(self.source.read_bytes(), b"source fixture")
        self.assertEqual(list(self.output.glob(".broll-*")), [])

    def test_regular_panel_preview_and_review_pages_are_published(self):
        panel = self.output / "panel.mov"
        panel.write_bytes(b"panel fixture")
        self.plan["clips"][0].update(kind="panel", file="../../outputs/folder-routing/panel.mov")
        self.write_plan()
        def panel_probe(path):
            return info(1 if Path(path) == panel else 10, Path(path) == panel)
        def render_panel(command):
            Path(command[-1]).write_bytes(b"panel preview fixture")
        with patch.object(media, "probe", side_effect=panel_probe), \
             patch.object(make_pages, "probe", side_effect=panel_probe), \
             patch.object(make_pages, "run", side_effect=render_panel) as render:
            pages = make_pages.write_pages(self.plan_path, self.preview, font_mode="shared")
        render.assert_called_once()
        self.assertTrue(all(page.is_file() for page in pages))
        self.assertEqual((self.output / "01-panel_preview.mp4").read_bytes(), b"panel preview fixture")
        self.assertIn('"src": "01-panel_preview.mp4"', pages[0].read_text())
        self.assertTrue((self.output / "assets" / "broll-me-fonts" / fonts.NOTICES[0]).is_file())
        self.assertEqual(self.preview.read_bytes(), b"previous preview")
        self.assertEqual(panel.read_bytes(), b"panel fixture")

    def test_review_pages_and_shared_fonts_survive_work_directory_removal(self):
        with patch.object(media, "probe", side_effect=self.fake_probe), patch.object(make_pages, "probe", side_effect=self.fake_probe):
            pages = make_pages.write_pages(self.plan_path, self.preview, font_mode="shared")
        self.assertEqual(pages, [self.output / name for name in ["viewer.html", "compare.html", "TIMING.md"]])
        shutil.rmtree(self.directory / "works")
        viewer = pages[0].read_text(encoding="utf-8")
        comparison = pages[1].read_text(encoding="utf-8")
        clips = json.loads(viewer.split("const CLIPS=", 1)[1].split(";", 1)[0])
        self.assertEqual([clip["src"] for clip in clips], ["preview.mp4", "clip%20with%20spaces.mp4"])
        comparison_sources = re.findall(r'<video[^>]+src="([^"]+)"', comparison)
        self.assertEqual(comparison_sources, ["../../inputs/source.mp4", "preview.mp4", "../../inputs/source.mp4", "preview.mp4"])
        for source in [*(clip["src"] for clip in clips), *comparison_sources]:
            with self.subTest(source=source):
                self.assertTrue((self.output / unquote(source)).resolve().is_file())
        for page in [viewer, comparison]:
            self.assertNotIn("works/", page)
            font_urls = re.findall(r"url\('([^']+)'\)", page)
            self.assertEqual(len(font_urls), 3)
            for font_url in font_urls:
                self.assertTrue(font_url.startswith("assets/broll-me-fonts/"))
                self.assertTrue((self.output / font_url).is_file())
        for notice in ["OFL-Geist.txt", "OFL-NotoSansKR.txt"]:
            self.assertTrue((self.output / "assets" / "broll-me-fonts" / notice).is_file())
        self.assertEqual(self.source.read_bytes(), b"source fixture")
        self.assertEqual(self.preview.read_bytes(), b"previous preview")

    def test_bundle_page_failure_preserves_prior_outputs(self):
        viewer = self.output / "viewer.html"
        viewer.write_bytes(b"previous viewer")
        def fake_composite(plan, output):
            output.write_bytes(b"new preview fixture")
        with patch.object(media, "probe", side_effect=self.fake_probe), \
             patch.object(preview_bundle, "create_preview", side_effect=fake_composite), \
             patch.object(preview_bundle, "write_pages", side_effect=ValueError("missing font")):
            with self.assertRaisesRegex(ValueError, "missing font"):
                preview_bundle.create_bundle(self.plan_path, self.preview)
        self.assertEqual(self.preview.read_bytes(), b"previous preview")
        self.assertEqual(viewer.read_bytes(), b"previous viewer")
        self.assertEqual(list(self.output.parent.glob(".broll-preview-*")), [])

    def test_bundle_preview_case_aliases_refuse_before_directory_or_stage_writes(self):
        plan_path = self.work / "protected-plan.mp4"
        plan_path.write_text(json.dumps(self.plan), encoding="utf-8")
        for protected in [self.source, self.clip, plan_path]:
            with self.subTest(protected_input=protected.name):
                output = case_alias(self, protected)
                before = self.tree_state()
                with patch.object(media, "probe", side_effect=self.fake_probe), \
                     patch.object(Path, "mkdir") as create_directory, \
                     patch.object(preview_bundle.tempfile, "mkdtemp") as create_stage, \
                     patch.object(preview_bundle, "create_preview") as encoder, \
                     patch.object(preview_bundle, "write_pages") as pages:
                    with self.assertRaisesRegex(media.MediaError, "overwrite"):
                        preview_bundle.create_bundle(plan_path, output)
                for operation in [create_directory, create_stage, encoder, pages]:
                    operation.assert_not_called()
                self.assertEqual(self.tree_state(), before)

    def test_bundle_publication_case_alias_refuses_entire_set_before_backup(self):
        protected = self.output / "SOURCE.mp4"
        protected.write_bytes(b"protected source")
        alias = case_alias(self, protected)
        stage = self.directory / "staged-case-alias"
        stage.mkdir()
        (stage / "000-first.txt").write_bytes(b"new first output")
        (stage / alias.name).write_bytes(b"new preview fixture")
        prior = self.output / "000-first.txt"
        prior.write_bytes(b"previous first output")
        before = self.tree_state()
        with patch.object(Path, "mkdir") as create_directory, \
             patch.object(preview_bundle.os, "replace") as replace:
            with self.assertRaisesRegex(media.MediaError, "overwrite"):
                preview_bundle.publish_bundle(stage, self.output, protected=[protected])
        create_directory.assert_not_called()
        replace.assert_not_called()
        self.assertFalse((stage / ".previous").exists())
        self.assertEqual(self.tree_state(), before)

    def test_bundle_late_protected_identity_rolls_back_prior_publication(self):
        stage = self.directory / "staged-late-identity"
        stage.mkdir()
        (stage / "preview.mp4").write_bytes(b"new preview fixture")
        (stage / "source.mp4").write_bytes(b"must not replace protected input")
        late_output = self.output / "source.mp4"
        replace = preview_bundle.os.replace
        def insert_alias_after_first_publication(source, destination):
            result = replace(source, destination)
            if Path(source) == stage / "preview.mp4":
                os.link(self.source, late_output)
            return result
        with patch.object(preview_bundle.os, "replace", side_effect=insert_alias_after_first_publication):
            with self.assertRaisesRegex(media.MediaError, "prior files restored"):
                preview_bundle.publish_bundle(stage, self.output, protected=[self.source])
        self.assertEqual(self.preview.read_bytes(), b"previous preview")
        self.assertEqual(self.source.read_bytes(), b"source fixture")
        self.assertTrue(late_output.samefile(self.source))
        self.assertEqual((stage / "source.mp4").read_bytes(), b"must not replace protected input")
        self.assertFalse((stage / ".previous" / "source.mp4").exists())

    def test_bundle_success_keeps_final_relative_links(self):
        def fake_composite(plan, output):
            output.write_bytes(b"new preview fixture")
        with patch.object(media, "probe", side_effect=self.fake_probe), \
             patch.object(make_pages, "probe", side_effect=self.fake_probe), \
             patch.object(preview_bundle, "create_preview", side_effect=fake_composite):
            preview_bundle.create_bundle(self.plan_path, self.preview)
        viewer = (self.output / "viewer.html").read_text()
        comparison = (self.output / "compare.html").read_text()
        clips = json.loads(viewer.split("const CLIPS=", 1)[1].split(";", 1)[0])
        self.assertEqual([clip["src"] for clip in clips], ["preview.mp4", "clip%20with%20spaces.mp4"])
        self.assertIn('src="../../inputs/source.mp4"', comparison)
        self.assertNotIn(".broll-preview-", viewer + comparison)
        self.assertEqual(self.preview.read_bytes(), b"new preview fixture")
        self.assertEqual(self.source.read_bytes(), b"source fixture")
        self.assertEqual(list(self.output.parent.glob(".broll-preview-*")), [])

    def test_bundle_publication_failure_rolls_back_all_files(self):
        stage = self.directory / "staged"
        stage.mkdir()
        (stage / "preview.mp4").write_bytes(b"new preview fixture")
        (stage / "viewer.html").write_bytes(b"new viewer fixture")
        viewer = self.output / "viewer.html"
        viewer.write_bytes(b"previous viewer")
        replace = preview_bundle.os.replace
        def fail_viewer(source, destination):
            if Path(source) == stage / "viewer.html":
                raise OSError("injected publication failure")
            return replace(source, destination)
        with patch.object(preview_bundle.os, "replace", side_effect=fail_viewer):
            with self.assertRaisesRegex(media.MediaError, "prior files restored"):
                preview_bundle.publish_bundle(stage, self.output)
        self.assertEqual(self.preview.read_bytes(), b"previous preview")
        self.assertEqual(viewer.read_bytes(), b"previous viewer")

    def test_bundle_interruption_retains_recovery_files(self):
        def fake_composite(plan, output):
            output.write_bytes(b"new preview fixture")
        def interrupt_after_backup(stage, outdir, protected):
            backup = stage / ".previous" / "preview.mp4"
            backup.parent.mkdir()
            self.preview.replace(backup)
            raise KeyboardInterrupt()
        with patch.object(media, "probe", side_effect=self.fake_probe), \
             patch.object(preview_bundle, "create_preview", side_effect=fake_composite), \
             patch.object(preview_bundle, "write_pages"), \
             patch.object(preview_bundle, "publish_bundle", side_effect=interrupt_after_backup):
            with self.assertRaisesRegex(preview_bundle.RecoveryError, "recovery files retained"):
                preview_bundle.create_bundle(self.plan_path, self.preview)
        stages = list(self.output.parent.glob(".broll-preview-*"))
        self.assertEqual(len(stages), 1)
        self.assertEqual((stages[0] / ".previous" / "preview.mp4").read_bytes(), b"previous preview")

    def test_wrong_input_depth_fails_before_publishing_or_changing_media(self):
        self.plan["video"] = "../inputs/source.mp4"
        self.write_plan()
        with patch.object(media, "probe") as source_probe, patch.object(make_pages, "probe") as preview_probe:
            with self.assertRaisesRegex(media.MediaError, "Input file not found"):
                make_pages.write_pages(self.plan_path, self.preview, font_mode="shared")
        source_probe.assert_not_called()
        preview_probe.assert_not_called()
        for name in ["viewer.html", "compare.html", "TIMING.md", "assets"]:
            self.assertFalse((self.output / name).exists())
        self.assertEqual(self.source.read_bytes(), b"source fixture")
        self.assertEqual(self.clip.read_bytes(), b"clip fixture")
        self.assertEqual(self.preview.read_bytes(), b"previous preview")


class SourceTimelineTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which(media.binary("ffmpeg")) and shutil.which(media.binary("ffprobe")), "FFmpeg/FFprobe unavailable")
    def test_actual_offset_media_rejects_before_preview_or_source_changes(self):
        with tempfile.TemporaryDirectory(prefix="broll-offset-") as directory:
            directory = Path(directory)
            source = directory / "offset source.mp4"
            media.run([media.binary("ffmpeg"), "-v", "error", "-nostdin", "-y", "-f", "lavfi", "-i", "testsrc2=s=160x90:r=24:d=2", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2.5", "-filter_complex", "[0:v]setpts=PTS+0.5/TB[v]", "-map", "[v]", "-map", "1:a", "-fps_mode", "passthrough", "-c:v", "libx264", "-c:a", "aac", str(source)], timeout=30)
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            source_info = media.probe(source)
            self.assertAlmostEqual(float(source_info["stream"]["start_time"]), .5, places=3)
            self.assertAlmostEqual(float(source_info["audio"][0]["start_time"]), 0, places=3)
            plan = directory / "plan.json"
            plan.write_text(json.dumps({"video": source.name, "fps": source_info["fps"], "clips": []}), encoding="utf-8")
            preview = directory / "preview.mp4"
            with self.assertRaisesRegex(media.MediaError, "video must start at 0"):
                composite.create_preview(plan, preview)
            self.assertFalse(preview.exists())
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

    def test_nonzero_video_origin_is_not_silently_normalized(self):
        source = info(2)
        source["stream"]["start_time"] = "0.5"
        source["audio"] = [{"start_time": "0", "duration": "2.5"}]
        with self.assertRaisesRegex(media.MediaError, "video must start at 0"):
            media.validate_source_timeline(source)

    def test_audio_offset_or_longer_audio_requires_approval(self):
        for audio in [{"start_time": "0.5", "duration": "1.5"}, {"start_time": "0", "duration": "2.5"}, {"start_time": "-0.02", "duration": "2"}]:
            source = info(2)
            source["audio"] = [audio]
            with self.subTest(audio=audio), self.assertRaisesRegex(media.MediaError, "Ask for approval"):
                media.validate_source_timeline(source)

    def test_shorter_zero_start_audio_is_supported(self):
        source = info(2)
        source["audio"] = [{"start_time": "0", "duration": "1.5"}]
        media.validate_source_timeline(source)

    def test_missing_stream_timing_cannot_be_inferred_from_container(self):
        source = info(2)
        del source["stream"]["duration"]
        with self.assertRaisesRegex(media.MediaError, "Video duration is unavailable"):
            media.validate_source_timeline(source)


if __name__ == "__main__":
    unittest.main()
