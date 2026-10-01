"""The executable profile fails clearly before any dependency installation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

DIRECTORY=Path(__file__).resolve().parents[1]/'skills/broll-me/scripts/runtime'
spec=importlib.util.spec_from_file_location('check_versions',DIRECTORY/'check_versions.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)


class RuntimeProfileTests(unittest.TestCase):
    def test_matching_versions_and_argv_execution(self):
        def execute(command,**options):
            self.assertNotIn('shell',options)
            return subprocess.CompletedProcess(command,0, {'node path':'v24.21.0\n','ffmpeg path':'ffmpeg version 9.0.2 Copyright','ffprobe path':'ffprobe version 9.0.2 Copyright'}[command[0]],'')
        with patch.object(checker.platform,'python_version',return_value='3.12.14'),patch.object(checker.subprocess,'run',side_effect=execute):
            actual=checker.check(DIRECTORY/'versions.json','node path','ffmpeg path','ffprobe path')
        self.assertEqual(actual,{key:json.loads((DIRECTORY/'versions.json').read_text())[key] for key in ['python','node','ffmpeg','ffprobe']})

    def test_version_mismatch_is_actionable(self):
        with patch.object(checker.platform,'python_version',return_value='3.14.0'),patch.object(checker.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'9.0.2','')):
            with self.assertRaisesRegex(ValueError,'Pinned runtime mismatch.*BROLL_NODE/BROLL_PYTHON'):
                checker.check(DIRECTORY/'versions.json','node','ffmpeg','ffprobe')

    def test_unknown_version_fails(self):
        with patch.object(checker.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'unknown','')):
            with self.assertRaisesRegex(ValueError,'Cannot identify node version'):
                checker.check(DIRECTORY/'versions.json','node','ffmpeg','ffprobe')
