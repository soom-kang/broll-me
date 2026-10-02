"""Regression coverage for subtitle, insertion, and review-page contracts."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import shutil
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
import words


def info(duration=10, alpha=False):
    return {"width": 320, "height": 180, "duration": duration, "fps": "30000/1001", "rate": Fraction(30000, 1001), "audio": [], "stream": {"pix_fmt": "yuva444p10le" if alpha else "yuv420p", "start_time": "0", "duration": str(duration)}}


class SubtitleTests(unittest.TestCase):
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


class ReviewAndLayoutTests(unittest.TestCase):
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

    def test_plan_resolves_inputs_and_outputs_from_work_directory(self):
        with patch.object(media, "probe", side_effect=self.fake_probe):
            _, source, _, clips = media.load_plan(self.plan_path)
        self.assertEqual(source, self.source.resolve())
        self.assertEqual(clips[0]["path"], self.clip.resolve())
        self.assertEqual(self.source.read_bytes(), b"source fixture")

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
