"""The executable profile fails clearly before any dependency installation."""
import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

DIRECTORY=Path(__file__).resolve().parents[1]/'skills/broll-me/scripts/runtime'
spec=importlib.util.spec_from_file_location('check_versions',DIRECTORY/'check_versions.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
spec=importlib.util.spec_from_file_location('broll_cli',DIRECTORY.parent/'broll.py')
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)


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


class CliTimeoutTests(unittest.TestCase):
    def environment(self):
        return {**os.environ, 'BROLL_TIMEOUT_MS': '1000'}

    def test_success_and_failure_keep_output_and_child_exit_code(self):
        diagnostics=io.StringIO()
        with contextlib.redirect_stderr(diagnostics):
            output=cli.execute([sys.executable,'-c','print("result")'],self.environment(),log_stdout=False)
            with self.assertRaises(cli.CommandFailure) as failed:
                cli.execute([sys.executable,'-c','import sys; print("detail",file=sys.stderr); sys.exit(7)'],self.environment())
        self.assertEqual(output,'result\n')
        self.assertEqual(failed.exception.code,7)
        self.assertEqual(diagnostics.getvalue(),'detail\n')

    def test_invalid_timeout_fails_before_starting_child(self):
        with patch.object(cli.subprocess,'Popen') as start:
            with self.assertRaisesRegex(cli.CommandFailure,'at least 1000'):
                cli.execute([sys.executable,'-c','pass'],{**self.environment(),'BROLL_TIMEOUT_MS':'999'})
            start.assert_not_called()

    @unittest.skipUnless(os.name=='posix','SIGTERM cleanup fixture requires POSIX')
    def test_timeout_allows_cooperative_cleanup_and_retains_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            marker=Path(directory)/'closed'
            driver='''import pathlib, signal, sys, time
def close(signum, frame):
    pathlib.Path(sys.argv[1]).write_text('closed')
    print('cleanup completed', file=sys.stderr, flush=True)
    raise SystemExit(0)
signal.signal(signal.SIGTERM, close)
print('started', flush=True)
time.sleep(10)
'''
            diagnostics=io.StringIO()
            with contextlib.redirect_stderr(diagnostics),patch.object(cli,'TIMEOUT_CLEANUP_GRACE_SECONDS',0.5):
                with self.assertRaises(cli.CommandFailure) as failed:
                    cli.execute([sys.executable,'-c',driver,marker],self.environment(),log_stdout=False)
            self.assertEqual(failed.exception.code,124)
            self.assertEqual(marker.read_text(),'closed')
            self.assertIn('cleanup completed',diagnostics.getvalue())
            self.assertIn('cleanup completed',str(failed.exception))
            self.assertIn('started',diagnostics.getvalue())
            self.assertNotIn('SIGKILL',diagnostics.getvalue())

    @unittest.skipUnless(os.name=='posix','Process-group containment requires POSIX')
    def test_timeout_kills_stubborn_descendant_and_does_not_wait_for_its_pipes(self):
        with tempfile.TemporaryDirectory() as directory:
            heartbeat=Path(directory)/'heartbeat'
            marker=Path(directory)/'parent-closed'
            descendant='''import pathlib, signal, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
while True:
    with pathlib.Path(sys.argv[1]).open('a') as stream:
        stream.write('alive\\n')
    time.sleep(0.05)
'''
            driver='''import pathlib, signal, subprocess, sys, time
subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]])
def close(signum, frame):
    pathlib.Path(sys.argv[3]).write_text('closed')
    print('parent cleanup completed', file=sys.stderr, flush=True)
    raise SystemExit(0)
signal.signal(signal.SIGTERM, close)
time.sleep(10)
'''
            diagnostics=io.StringIO()
            started=time.monotonic()
            with contextlib.redirect_stderr(diagnostics),patch.object(cli,'TIMEOUT_CLEANUP_GRACE_SECONDS',0.25):
                with self.assertRaises(cli.CommandFailure) as failed:
                    cli.execute([sys.executable,'-c',driver,descendant,heartbeat,marker],self.environment())
            self.assertLess(time.monotonic()-started,4)
            self.assertEqual(failed.exception.code,124)
            self.assertEqual(marker.read_text(),'closed')
            self.assertIn('parent cleanup completed',diagnostics.getvalue())
            self.assertIn('SIGKILL sent to owned process group',diagnostics.getvalue())
            before=heartbeat.read_bytes()
            self.assertTrue(before)
            time.sleep(0.15)
            self.assertEqual(heartbeat.read_bytes(),before)

    def test_main_timeout_keeps_one_json_stdout_error(self):
        stdout=io.StringIO()
        stderr=io.StringIO()
        def timeout_dispatch(args, runtime, environment):
            return cli.execute([sys.executable,'-c','import time; time.sleep(10)'],self.environment())
        with patch.object(cli,'dispatch',side_effect=timeout_dispatch),contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            result=cli.main(['doctor'])
        self.assertEqual(result,124)
        self.assertEqual(len(stdout.getvalue().splitlines()),1)
        self.assertEqual(json.loads(stdout.getvalue())['exit_code'],124)
        self.assertIn('requesting child cleanup',stderr.getvalue())
