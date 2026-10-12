"""Behavioral tests for curated archives and non-destructive project installation."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from install_skill import install
from package import build_package
from validate_package import collect_files, verify_archive


class SkillFixture:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="broll-package-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.skill = self.root / "broll-me"
        fixtures = {
            "SKILL.md": '---\nname: broll-me\ndescription: "Build palette-driven inserts."\nlicense: MIT\n---\n[engine](reference/engine-api.md)\n',
            "LICENSE": "Fixture license\n",
            "THIRD_PARTY_NOTICES.md": "Fixture notices\n",
            "engine/build.py": "# Fixture builder\n",
            "engine/motion.js": "// Fixture engine\n",
            "reference/engine-api.md": "Fixture API\n",
            "scripts/setup.sh": "#!/bin/sh\n",
            "agents/openai.yaml": 'interface:\n  display_name: "broll-me"\n',
        }
        for name, content in fixtures.items():
            self.write(name, content)

    def write(self, name, data):
        path = self.skill / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)
        return path


class PackageTests(SkillFixture, unittest.TestCase):
    def test_archives_match_source_and_roundtrip(self):
        with redirect_stdout(io.StringIO()):
            manifest = build_package(self.skill, self.root / "dist")
        self.assertEqual(manifest["packaging_backend"], "stdlib-curated")
        self.assertEqual((self.root / "dist/broll-me.skill").read_bytes(),
                         (self.root / "dist/broll-me.zip").read_bytes())
        self.assertEqual(manifest["archives"]["broll-me.skill"], manifest["archives"]["broll-me.zip"])
        verify_archive(self.root / "dist/broll-me.skill", collect_files(self.skill))

    def test_runtime_and_eval_artifacts_are_not_packaged(self):
        self.write("node_modules/demo/runtime.js", "ignored")
        self.write("evals/prompt.json", "{}")
        self.write("engine/__pycache__/artifact.pyc", "ignored")
        files = collect_files(self.skill)
        self.assertNotIn("node_modules/demo/runtime.js", files)
        self.assertNotIn("evals/prompt.json", files)
        self.assertNotIn("engine/__pycache__/artifact.pyc", files)

    def test_rejects_credential_paths_without_reading_values(self):
        path = self.write(".env", "sensitive value")
        with self.assertRaisesRegex(ValueError, "Forbidden credential"):
            collect_files(self.skill)
        self.assertEqual(path.read_text(), "sensitive value")

    def test_rejects_credential_content(self):
        self.write("reference/notes.md", "sk-" + "a" * 40)
        with self.assertRaisesRegex(ValueError, "Credential-like content"):
            collect_files(self.skill)

    def test_rejects_git_and_private_artwork(self):
        self.write(".git/config", "fixture")
        with self.assertRaisesRegex(ValueError, "Forbidden credential or repository"):
            collect_files(self.skill)
        (self.skill / ".git/config").unlink()
        (self.skill / ".git").rmdir()
        self.write("examples/private-logo.png", "fixture image")
        with self.assertRaisesRegex(ValueError, "private artwork excluded"):
            collect_files(self.skill)

    def test_rejects_outbound_source_symlink(self):
        outside = self.root / "outside.md"
        outside.write_text("fixture")
        (self.skill / "reference/linked.md").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "must not contain symlinks"):
            collect_files(self.skill)

    def test_rejects_internal_reference_escape_and_missing_reference(self):
        self.write("reference/bad.md", "[bad](../../outside.md)")
        with self.assertRaisesRegex(ValueError, "Reference escapes"):
            collect_files(self.skill)
        self.write("reference/bad.md", "[bad](missing.md)")
        with self.assertRaisesRegex(ValueError, "Missing internal reference"):
            collect_files(self.skill)

    def test_rejects_archive_addition_or_modified_bytes(self):
        files = collect_files(self.skill)
        archive = self.root / "unsafe.skill"
        with zipfile.ZipFile(archive, "w") as package:
            for name, data in files.items():
                package.writestr("broll-me/" + name, data)
            package.writestr("../escape.txt", "fixture")
        with self.assertRaisesRegex(ValueError, "file list differs"):
            verify_archive(archive, files)
        with zipfile.ZipFile(archive, "w") as package:
            for name, data in files.items():
                package.writestr("broll-me/" + name, b"changed" if name == "LICENSE" else data)
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            verify_archive(archive, files)

    def test_require_creator_does_not_silently_fallback(self):
        with self.assertRaisesRegex(ValueError, "requires a creator path"):
            build_package(self.skill, self.root / "dist", require_creator=True)
        self.assertFalse((self.root / "dist").exists())

    def test_rejects_host_specific_frontmatter(self):
        self.write("SKILL.md", '---\nname: broll-me\ndescription: "Fixture"\nmodel: claude-example\n---\n')
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            collect_files(self.skill)

    def test_portable_scalar_strings_and_flat_metadata_remain_supported(self):
        frontmatters = [
            "name: broll-me\ndescription: Build palette-driven inserts. # comment\nlicense: MIT\nmetadata: {} # empty map",
            "name: broll-me\ndescription: 'Build ''branded'' B-roll #1' # comment\nlicense: MIT\nmetadata:\n  owner: 'Scene team'\n  version: 1.25\n  enabled: true\n  optional: null\n  empty:\n  key_value: https://example.com:8443/demo#anchor",
            'metadata:\n  owner: "Scene \\"team\\""\nname: broll-me\ndescription: "Build palette-driven inserts."\nlicense: MIT',
        ]
        for frontmatter in frontmatters:
            with self.subTest(frontmatter=frontmatter):
                self.write("SKILL.md", f"---\n{frontmatter}\n---\n")
                self.assertIn("SKILL.md", collect_files(self.skill))

    def test_malformed_frontmatter_cannot_publish_with_either_backend(self):
        cases = [
            "name: broll-me\ndescription: 'Build branded B-roll\nlicense: MIT",
            "name: broll-me\nmetadata: {}\ndescription: Build B-roll\n  host_only: invalid nested scalar\nlicense: MIT",
        ]
        creator = self.root / "creator"
        (creator / "scripts").mkdir(parents=True)
        (creator / "scripts/package_skill.py").write_text("# Must not run for malformed input\n")
        output = self.root / "dist"
        output.mkdir()
        previous = {name: ("previous " + name).encode() for name in
                    ("broll-me.skill", "broll-me.zip", "package-manifest.json")}
        for name, content in previous.items():
            (output / name).write_bytes(content)
        for frontmatter in cases:
            for backend in (None, creator):
                with self.subTest(frontmatter=frontmatter, creator=backend):
                    self.write("SKILL.md", f"---\n{frontmatter}\n---\n")
                    with mock.patch("package.importlib.util.find_spec", return_value=object()) as discovery, \
                            mock.patch("package.subprocess.run") as run:
                        with self.assertRaises(ValueError):
                            build_package(self.skill, output, creator=backend)
                        discovery.assert_not_called()
                        run.assert_not_called()
                    self.assertEqual({path.name: path.read_bytes() for path in output.iterdir()}, previous)
                    absent = self.root / "not-created"
                    with self.assertRaises(ValueError):
                        build_package(self.skill, absent, creator=backend)
                    self.assertFalse(absent.exists())

    def test_portable_subset_rejects_ambiguous_types_and_unsupported_yaml(self):
        invalid = [
            "description: true", "description: null", "description: 42", "description: 2026-10-12",
            "description: [Build, B-roll]", "description: {text: Build}", "description: |\n  Build B-roll",
            "description: &shared Build B-roll", "description: *shared", "description: !!str Build B-roll",
            "description: 'Build' trailing", 'description: "Build" trailing',
            "description: Build: B-roll", "description: 'Build\tB-roll'",
            "description: Build B-roll\ndescription: Other", "description: Build B-roll\nlicense: false",
            "description: Build B-roll\nmetadata:\n  owner: Scene team\n  owner: Other team",
            "description: Build B-roll\nmetadata:\n   owner: Scene team",
            "description: Build B-roll\nmetadata:\n  owner:\n    team: Scene team",
            "description: Build B-roll\nmetadata: {owner: Scene team}",
            "description: Build B-roll\nmetadata:", "description: Build B-roll\nmetadata:\nlicense: MIT",
            "description: Build B-roll\nmetadata: {}\n  owner: Scene team",
            "description: Build B-roll\nmetadata:\n  true: invalid string key",
            'description: "Build\\tB-roll"',
            'description: "Build"\u00a0', "description: 'Build'\u2003", "description: 'Build'\u3000",
            "description: Build B-roll\n\u2003", "description: Build B-roll\n\u3000# invalid comment indentation",
            "description: Build B-roll\n\u00a0", "description: Build B-roll\n\u00a0# invalid comment indentation",
            "description: Build B-roll\nmetadata: {}\u00a0",
        ]
        for fields in invalid:
            with self.subTest(fields=fields):
                self.write("SKILL.md", f"---\nname: broll-me\n{fields}\n---\n")
                with self.assertRaises(ValueError):
                    collect_files(self.skill)
        for name in ("name:broll-me", "name: broll-me\u00a0"):
            with self.subTest(name=name):
                self.write("SKILL.md", f"---\n{name}\ndescription: Build B-roll\n---\n")
                with self.assertRaises(ValueError):
                    collect_files(self.skill)


class InstallTests(SkillFixture, unittest.TestCase):
    def test_dry_run_is_non_mutating(self):
        project = self.root / "project"
        project.mkdir()
        with redirect_stdout(io.StringIO()):
            targets = install(self.skill, project, dry_run=True)
        self.assertEqual(len(targets), 2)
        self.assertEqual(list(project.iterdir()), [])

    def test_install_is_idempotent_and_uses_relative_links(self):
        project = self.root / "project"
        project.mkdir()
        with redirect_stdout(io.StringIO()):
            targets = install(self.skill, project)
            again = install(self.skill, project)
        self.assertEqual(targets, again)
        for target in targets:
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), self.skill)
            self.assertFalse(Path(target.readlink()).is_absolute())

    def test_existing_path_preserved_and_other_host_not_partially_installed(self):
        project = self.root / "project"
        existing = project / ".claude/skills/broll-me"
        existing.mkdir(parents=True)
        marker = existing / "marker.txt"
        marker.write_text("user-owned")
        with self.assertRaises(FileExistsError):
            install(self.skill, project)
        self.assertEqual(marker.read_text(), "user-owned")
        self.assertFalse((project / ".agents").exists())

    def test_symlinked_parent_not_followed(self):
        project = self.root / "project"
        outside = self.root / "outside"
        project.mkdir()
        outside.mkdir()
        (project / ".agents").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinked discovery parent"):
            install(self.skill, project, host="codex")
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
