"""Focused evidence isolation, availability status and palette-switch regressions."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


runner, reviewer = module('run_evals'), module('review_evals')


class EvaluationEvidenceTests(unittest.TestCase):
    def test_fresh_iteration_never_reuses_historical_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            previous = runner.reserve_iteration(workspace, 1)
            evidence = previous / 'old.json'
            evidence.write_text('historical success')
            self.assertEqual(runner.reserve_iteration(workspace).name, 'iteration-2')
            with self.assertRaises(FileExistsError): runner.reserve_iteration(workspace, 1)
            self.assertEqual(evidence.read_text(), 'historical success')

    def test_capture_manifest_owns_only_current_files_and_exact_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, run = root / 'sandbox-outputs', root / 'run-new'
            source.mkdir(); run.mkdir()
            (source / 'built').mkdir()
            (source / 'built/clip.html').write_text('current')
            (source / 'source.mp4').write_bytes(b'fixture')
            manifest = runner.capture_outputs(source, run, 'fresh', {hashlib.sha256(b'fixture').hexdigest()})
            self.assertEqual(set(manifest['files']), {'outputs/built/clip.html'})
            (run / 'outputs/stale-success.mp4').write_bytes(b'unowned')
            execution = {'run_id':'fresh', 'artifact_manifest_sha256':runner.digest(run / 'artifact-manifest.json')}
            self.assertEqual(reviewer.manifest_files(run, execution), {'outputs/built/clip.html':b'current'})
            (run / 'outputs/built/clip.html').write_text('changed')
            with self.assertRaises(ValueError): reviewer.manifest_files(run, execution)

    def test_previous_success_cannot_grade_failed_new_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old, new = root / 'run-old', root / 'run-new'
            (old / 'outputs/built').mkdir(parents=True); new.mkdir()
            (old / 'outputs/built/clip.html').write_text('successful old clip')
            previous_digest = runner.digest(old / 'outputs/built/clip.html')
            runner.write_json(new / 'execution.json', {'eval_id':1,'eval_name':'palette-switch',
                'configuration':'with_skill','run_id':'new','status':'failed','exit_code':1,'reason':'new command failed'})
            with patch.object(reviewer,'audit_html',side_effect=AssertionError('must not audit stale success')):
                grade = reviewer.grade(new)
            self.assertIsNone(grade['result']['pass_rate'])
            self.assertEqual(grade['status'],'failed')
            self.assertEqual(runner.digest(old / 'outputs/built/clip.html'), previous_digest)

    def test_completed_new_run_does_not_discover_unowned_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            source = run / 'sandbox-outputs'; source.mkdir()
            runner.capture_outputs(source, run, 'new')
            (run / 'outputs/built').mkdir()
            (run / 'outputs/built/clip.html').write_text('unowned old success')
            execution = {'eval_id':1,'eval_name':'palette-switch','configuration':'with_skill',
                'run_id':'new','provider':'codex','status':'completed','exit_code':0,
                'boundary':'author-build','artifact_manifest_sha256':runner.digest(run / 'artifact-manifest.json')}
            runner.write_json(run / 'execution.json',execution); runner.write_json(run / 'timing.json',{})
            with patch.object(reviewer,'audit_html',side_effect=AssertionError('must not audit unowned HTML')):
                grade = reviewer.grade(run)
            self.assertEqual(grade['result']['pass_rate'],0)
            self.assertEqual(grade['status'],'evaluated')

    def test_availability_failure_has_no_quality_score_and_timeout_is_distinct(self):
        self.assertEqual(runner.execution_status(124,'','')[0],'timeout')
        self.assertEqual(runner.execution_status(1,'','ordinary build failure')[0],'failed')
        self.assertEqual(runner.execution_status(1,'','Authentication failed')[0],'blocked')
        self.assertEqual(runner.owned_command_status([{'command':'doctor','exit_code':1,'result':{'message':'MachPort failed'}}])[0],'blocked')
        self.assertEqual(runner.owned_command_status([{'command':'render','exit_code':124}])[0],'timeout')

    def test_duplicated_cyan_is_rejected_before_scene_invariants(self):
        cyan = json.loads((reviewer.SKILL / 'palettes/midnight-cyan.json').read_text())
        warm = json.loads((reviewer.SKILL / 'palettes/warm-orange.json').read_text())
        def audit(palette):
            return {'palette':palette['colors'],'cssRoles':palette['colors'],
                'scene':{'T':1},'geometry':[], 'W':640,'H':360,'T':1,'alpha':False}
        content = '<h1>한국어 키워드</h1>'.encode()
        commands = [{'command':'build','exit_code':0,'scene_sha256':'same'}] * 2
        self.assertTrue(reviewer.palette_switch_matches(cyan,audit(cyan),warm,audit(warm),content,content,commands))
        self.assertFalse(reviewer.palette_switch_matches(cyan,audit(cyan),cyan,audit(cyan),content,content,commands))
        self.assertFalse(reviewer.palette_switch_matches(cyan,audit(cyan),warm,audit(cyan),content,content,commands))


if __name__ == '__main__': unittest.main()
