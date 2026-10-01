"""Small regressions for SceneSpec inputs, escaping and portable fonts."""
import copy
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "broll-me"
sys.path.insert(0, str(SKILL / "engine"))
from build import build_scene
from fonts import font_css
from scene_templates import compile_scene, validate_scene


class TemplateTests(unittest.TestCase):
    def test_defaults_and_content_contract(self):
        valid = {"schema_version": 1, "template": "card", "title": "Title", "body": "Body"}
        spec = validate_scene(valid)
        self.assertEqual((spec["width"], spec["height"], spec["duration"], spec["center"]),
                         (1920, 1080, 6, [960, 540]))
        failures = []
        for field in ("schema_version", "template", "title", "body"):
            bad = copy.deepcopy(valid); del bad[field]; failures.append(bad)
        failures.extend([{**valid, "width": 641}, {**valid, "duration": float("nan")},
                         {**valid, "palette": "midnight-cyan"},
                         {"schema_version": 1, "template": "terminal", "title": "T", "lines": []},
                         {"schema_version": 1, "template": "chart", "title": "T", "bars": [{"label": "L", "value": -1}]}])
        for bad in failures:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_scene(bad)
        for path in (SKILL / "examples" / "scenes").glob("*.json"):
            fragment = compile_scene(json.loads(path.read_text()))
            self.assertIn("data-broll-text", fragment)
            self.assertIn("M.scene", fragment)
            if path.stem == "panel": self.assertIn("bg:null", fragment)

    def test_html_and_script_text_is_escaped_without_changing_content(self):
        text = '</script><img src=x onerror="alert(1)"> & 한글'
        spec = {"schema_version": 1, "template": "terminal", "title": text, "lines": [text]}
        fragment = compile_scene(spec)
        self.assertIn("&lt;/script&gt;", fragment)
        self.assertIn("\\u003c/script\\u003e", fragment)
        self.assertEqual(fragment.count("<script>"), 1)
        with tempfile.TemporaryDirectory() as folder:
            source = pathlib.Path(folder) / "input.json"
            source.write_text(json.dumps(spec))
            output = build_scene(source, pathlib.Path(folder) / "out" / "scene.html", font_mode="shared")
            html = output.read_text()
            self.assertIn("&lt;/script&gt;", html)
            self.assertNotIn("&amp;lt;/script", html)
            self.assertNotIn("data:font", html)

    def test_shared_font_assets_reused_and_conflicts_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            css = font_css(root, "shared")
            assets = root / "assets" / "broll-me-fonts"
            self.assertEqual(len(list(assets.iterdir())), 5)
            font = assets / "NotoSansKR.ttf"
            stamp = font.stat().st_mtime_ns
            self.assertEqual(font_css(root, "shared"), css)
            self.assertEqual(font.stat().st_mtime_ns, stamp)
            self.assertIn("assets/broll-me-fonts/NotoSansKR.ttf", css)
            font.write_text("user-owned asset")
            with self.assertRaisesRegex(ValueError, "differs"):
                font_css(root, "shared")
            self.assertEqual(font.read_text(), "user-owned asset")
            font.unlink(); font.symlink_to(SKILL / "engine" / "fonts" / "NotoSansKR.ttf")
            with self.assertRaisesRegex(ValueError, "symlink"):
                font_css(root, "shared")


if __name__ == "__main__":
    unittest.main()
