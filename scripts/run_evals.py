#!/usr/bin/env python3
"""Run fresh, bounded host evaluations; preserve historical iterations and fixture provenance."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / 'skills/broll-me-workspace'
PRESETS = {1: 'midnight-cyan', 2: 'kkumil-pink', 3: 'onnimm-orange'}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reserve_iteration(workspace: Path, number: int | None = None) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    if number is not None and number < 1:
        raise ValueError('Iteration must be positive')
    if number is None:
        existing = [int(m[1]) for path in workspace.iterdir()
                    if (m := re.fullmatch(r'iteration-(\d+)', path.name))]
        number = max(existing, default=0) + 1
    directory = workspace / f'iteration-{number}'
    directory.mkdir(exist_ok=False)
    return directory


def capture_outputs(source: Path, directory: Path, run_id: str,
                    excluded_hashes: set[str] | None = None) -> dict:
    """Copy only this sandbox's output files; no merging with an earlier run."""
    target = directory / 'outputs'
    target.mkdir(exist_ok=False)
    files, excluded = {}, []
    excluded_hashes = excluded_hashes or set()
    if source.is_symlink():
        raise ValueError('Evaluation output root must not be symlinked')
    for path in sorted(source.rglob('*')) if source.exists() else []:
        relative = path.relative_to(source)
        if path.is_symlink():
            raise ValueError(f'Generated output symlink rejected: {relative}')
        if any(part in {'node_modules', '.venv', 'browsers', 'inputs', '__pycache__'} for part in relative.parts):
            continue
        if not path.is_file():
            continue
        data = path.read_bytes()
        checksum = hashlib.sha256(data).hexdigest()
        if checksum in excluded_hashes:
            excluded.append(relative.as_posix())
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        files['outputs/' + relative.as_posix()] = {'sha256': checksum, 'bytes': len(data)}
    manifest = {'schema_version': 1, 'run_id': run_id, 'files': files,
                'excluded_fixture_copies': excluded,
                'captured_at': datetime.now(timezone.utc).isoformat()}
    write_json(directory / 'artifact-manifest.json', manifest)
    return manifest


def launch_host(command, prompt, sandbox, environment, timeout):
    """Bound the entire launched process group, including tool children on timeout."""
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, cwd=sandbox,
                               env=environment, start_new_session=(os.name == 'posix'))
    try:
        raw, stderr = process.communicate(prompt, timeout=timeout)
        return raw, stderr, process.returncode
    except subprocess.TimeoutExpired:
        if os.name == 'posix':
            try: os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
        else:
            process.terminate()
        try:
            raw, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == 'posix':
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            else:
                process.kill()
            raw, stderr = process.communicate()
        return raw or '', stderr or '', 124


def execution_status(code: int, raw: str, stderr: str) -> tuple[str, str | None]:
    if code == 124:
        return 'timeout', 'Host exceeded the bounded timeout'
    text = (raw + '\n' + stderr).lower()
    auth = any(marker in text for marker in ['not logged in', 'authentication failed', 'authentication error',
                                             'auth_error', 'invalid api key', 'oauth token has expired', 'please run /login'])
    unavailable = any(marker in text for marker in ['runtime virtualenv missing', 'missing executable:',
                                                    'cannot find module', 'chromium is missing', 'playwright version mismatch',
                                                    'numpy version mismatch', 'browser executable not found'])
    is_error = False
    try: is_error = bool(json.loads(raw).get('is_error'))
    except (ValueError, AttributeError): pass
    if auth and (code != 0 or is_error):
        return 'blocked', 'Host authentication unavailable; credentials unchanged'
    if unavailable and (code != 0 or is_error):
        return 'blocked', 'Required execution environment unavailable'
    return ('completed', None) if code == 0 and not is_error else ('failed', 'Host execution failed')


def owned_command_status(records: list) -> tuple[str, str | None]:
    """Classify actual CLI failures even when the host itself exits successfully."""
    for record in records:
        code = record.get('exit_code', 0)
        if code == 124:
            return 'timeout', 'A host CLI command exceeded its bounded timeout'
        if not code:
            continue
        if record.get('command') == 'doctor':
            return 'blocked', 'Read-only runtime doctor failed; execution environment unavailable'
        detail = json.dumps(record.get('result', {})) + str(record.get('stderr', ''))
        markers = ['machport', 'operation not permitted', 'permission denied', 'failed to launch',
                   'browser has been closed', 'chromium is missing', 'cannot find module',
                   'missing executable', 'runtime virtualenv missing', 'sandbox initialization']
        if any(marker in detail.lower() for marker in markers):
            return 'blocked', 'A required runtime/browser command was blocked by the execution environment'
        return 'failed', 'A host CLI command failed; see owned commands.jsonl'
    return 'completed', None


INVOKER = '''import hashlib, json, os, pathlib, subprocess, sys, time
outputs = pathlib.Path('outputs'); outputs.mkdir(exist_ok=True)
command = [os.environ['BROLL_PYTHON'], str(pathlib.Path(os.environ['BROLL_EVAL_SKILL'])/'scripts/broll.py'), '--runtime', os.environ['BROLL_RUNTIME'], *sys.argv[1:]]
scene_digest = None
if '--scene' in sys.argv:
    scene_path = pathlib.Path(sys.argv[sys.argv.index('--scene')+1])
    if scene_path.is_file(): scene_digest = hashlib.sha256(scene_path.read_bytes()).hexdigest()
started = time.monotonic()
result = subprocess.run(command, capture_output=True, text=True)
try: payload = json.loads(result.stdout)
except ValueError: payload = {'status': 'unparsed', 'stdout': result.stdout}
record = {'command': sys.argv[1] if len(sys.argv)>1 else None, 'args':sys.argv[1:], 'exit_code': result.returncode, 'result': payload, 'stderr':result.stderr, 'scene_sha256':scene_digest, 'elapsed_seconds':time.monotonic()-started}
with (outputs/'commands.jsonl').open('a') as log: log.write(json.dumps(record, ensure_ascii=False)+'\\n')
if result.stdout: print(result.stdout, end='')
if result.stderr: print(result.stderr, end='', file=sys.stderr)
raise SystemExit(result.returncode)
'''


def stage_fixtures(sandbox: Path, args, case_id: int) -> dict:
    inputs = sandbox / 'inputs'
    provided = {'source-video': args.source_video, 'srt': args.srt, 'vtt': args.vtt}
    records = {}
    for key, supplied in provided.items():
        if supplied is None:
            continue
        original = Path(supplied).expanduser().resolve(strict=True)
        if not original.is_file():
            raise ValueError(f'Fixture is not a file: {original}')
        inputs.mkdir(exist_ok=True)
        destination = inputs / (('source' if key == 'source-video' else 'transcript') + original.suffix)
        shutil.copyfile(original, destination)
        records[key] = {'original_path': str(original), 'sandbox_path': str(destination),
                        'sha256': digest(destination), 'bytes': destination.stat().st_size}
    transcript_key = 'vtt' if case_id == 3 else 'srt'
    if args.boundary == 'end-to-end' and not {'source-video', transcript_key} <= records.keys():
        raise ValueError(f'End-to-end eval {case_id} requires actual --source-video and --{transcript_key} files')
    return records


def make_prompt(provider, case, configuration, args, sandbox, skill, fixtures, boundary):
    mention = '$broll-me' if provider == 'codex' else '/broll-me'
    common = f'''This is an approved, bounded local evaluation. Use only the supplied skill.
Invoke {mention} (or explicitly read {skill}/SKILL.md if project discovery is unavailable; report that limitation).
Request: {case['prompt']}
Use {args.python} as Python. Write all deliverables under {sandbox}/outputs.
Do not install dependencies, use network, read credentials/settings/history, send messages,
modify the supplied skill, or write outside this sandbox. The supplied runtime is read-only reusable infrastructure.
The creative plan and specified palettes are already approved; do not reopen approval.
Create a simple readable Korean card morph: 640x360, duration 1s, treatment {'panel bg:null' if case['id']==3 else 'full-frame'}, palette {PRESETS[case['id']]}.
Never invent numeric results or imply real speech alignment. Stop on a missing environment and report the actual error.
'''
    if boundary != 'end-to-end':
        return common + f'''Boundary: author/build only. No source video was supplied or claimed inspected.
Do not render, inspect a fictitious source, or install a browser.
Read the engine API, write outputs/clip.html and build outputs/built/clip.html.
For eval 1 also build warm-orange into outputs/warm-built/ using the same fragment.
Write outputs/summary.md with actual results. Do not claim the end-to-end CLI ran.
'''
    transcript = fixtures['vtt' if case['id']==3 else 'srt']['sandbox_path']
    source = fixtures['source-video']['sandbox_path']
    warm = '''Also build outputs/warm-built/clip.html from exactly the same outputs/clip.json using --palette warm-orange,
check it, render outputs/warm-clip.mp4 and create outputs/warm-beats.png. Do not duplicate the cyan build as warm.
''' if case['id'] == 1 else ''
    clip = 'clip.mov' if case['id'] == 3 else 'clip.mp4'
    return common + f'''Boundary: actual-fixture CLI end-to-end; the following files exist and were copied into this sandbox:
video: {source}
transcript: {transcript}
Use the current shared SceneSpec schema and author outputs/clip.json (one spec, reused for both palettes).
Run every CLI command through: {shlex.quote(args.python)} {shlex.quote(str(sandbox/'invoke.py'))} COMMAND ARGS
The helper calls the copied skill/scripts/broll.py with this absolute runtime and records real stdout/exit codes to outputs/commands.jsonl.
Required sequence:
1. doctor (read-only); if unavailable, stop and write outputs/run-status.json as {{"status":"blocked","reason":"environment","message":"actual error"}}.
2. inspect the actual video into outputs/inspection; words the actual transcript; retain words output in outputs/words.json.
3. build outputs/built --scene outputs/clip.json --palette {PRESETS[case['id']]} --font-mode shared; check outputs/built/clip.html.
4. render outputs/built/clip.html outputs/{clip} --fps 30000/1001 --quality final; beats outputs/built/clip.html outputs/beats.png 0.1 0.5 0.85.
{warm}5. Write outputs/plan.json with video={json.dumps(source)}, fps="30000/1001", and clips=[{{"id":"01","title":"한국어 키워드","line":"provided fixture transcript","file":"{clip}","kind":"{'panel' if case['id']==3 else 'full'}","in":1,"out":3}}].
The clip duration is 1s and the approved slot intentionally holds the last frame.
6. preview outputs/plan.json outputs/preview.mp4 --font-mode shared, producing TIMING.md, viewer.html, compare.html.
Keep rendered files as your own outputs; the reviewer will never rerender them as host evidence.
Write outputs/summary.md with commands, actual outputs, limitations, and any failure. Do not merely provide instructions.
'''


def run_case(provider, case, configuration, args):
    run_id = str(uuid.uuid4())
    directory = args.iteration_dir / provider / f"eval-{case['id']}-{case['name']}" / configuration / ('run-' + run_id)
    directory.mkdir(parents=True, exist_ok=False)
    sandbox = Path(tempfile.mkdtemp(prefix=f'broll-eval-{provider}-{case["id"]}-')).resolve()
    source = ROOT / 'skills/broll-me'
    skill = sandbox / 'skill' / 'broll-me'
    started = time.monotonic()
    code, raw, stderr, fixtures, manifest = 1, '', '', {}, None
    boundary = args.boundary
    try:
        shutil.copytree(source, skill, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (sandbox / 'outputs').mkdir()
        fixtures = stage_fixtures(sandbox, args, case['id'])
        if configuration == 'with_skill':
            for host_path in ['.agents/skills', '.claude/skills']:
                destination = sandbox / host_path / 'broll-me'
                destination.parent.mkdir(parents=True)
                destination.symlink_to(os.path.relpath(skill, destination.parent), target_is_directory=True)
        (sandbox / 'invoke.py').write_text(INVOKER)
        prompt = make_prompt(provider, case, configuration, args, sandbox, skill, fixtures, boundary)
        (directory / 'prompt.txt').write_text(prompt)
        write_json(directory / 'eval_metadata.json', {'eval_id':case['id'], 'eval_name':case['name'], 'prompt':case['prompt'], 'assertions':[]})
        if provider == 'codex':
            command = ['codex','exec','--ephemeral','--skip-git-repo-check','--sandbox','workspace-write','--json','-C',str(sandbox),'-']
        else:
            command = ['claude','-p','--output-format','json','--tools','Read,Write,Edit,Bash','--allowedTools','Read,Write,Edit,Bash','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--no-session-persistence','--setting-sources','']
        environment = os.environ.copy()
        environment.update({'BROLL_RUNTIME': str(args.runtime), 'BROLL_NODE': args.node,
                            'BROLL_PYTHON': args.python, 'BROLL_EVAL_SKILL': str(skill)})
        environment['NODE_PATH'] = str(args.runtime / 'node_modules') + (os.pathsep + environment['NODE_PATH'] if environment.get('NODE_PATH') else '')
        if (args.runtime/'browsers').is_dir(): environment.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(args.runtime/'browsers'))
        raw, stderr, code = launch_host(command, prompt, sandbox, environment, args.timeout)
        status, reason = execution_status(code, raw, stderr)
    except (OSError, ValueError) as exc:
        command, status, reason = [], 'blocked', f'Evaluation environment unavailable: {exc}'
        stderr = str(exc)
    try:
        manifest = capture_outputs(sandbox/'outputs', directory, run_id, {record['sha256'] for record in fixtures.values()})
        owned = manifest['files']
        if status == 'completed' and 'outputs/commands.jsonl' in owned:
            records = [json.loads(line) for line in (directory/'outputs/commands.jsonl').read_text().splitlines() if line.strip()]
            status, reason = owned_command_status(records)
        if status == 'completed' and 'outputs/run-status.json' in owned:
            value = json.loads((directory/'outputs/run-status.json').read_text())
            if value.get('status') == 'blocked' and value.get('reason') == 'environment':
                status, reason = 'blocked', 'Host reported an unavailable environment; see owned run-status.json'
            elif value.get('status') in {'failed','timeout'}:
                status, reason = value['status'], value.get('message', 'Host reported failure')
    except (OSError, ValueError) as exc:
        status, reason = 'failed', f'Artifact capture failed: {exc}'
    elapsed = time.monotonic() - started
    tokens = None
    for line in raw.splitlines():
        try:
            usage = json.loads(line).get('usage', {})
            if usage: tokens = usage.get('input_tokens',0) + usage.get('output_tokens',0)
        except (ValueError, AttributeError): pass
    (directory/'events.jsonl').write_text(raw)
    (directory/'stderr.txt').write_text(stderr)
    write_json(directory/'timing.json', {'total_tokens':tokens, 'duration_ms':round(elapsed*1000), 'total_duration_seconds':elapsed})
    result = {'schema_version':1, 'run_id':run_id, 'iteration':int(args.iteration_dir.name.split('-')[-1]),
              'provider':provider, 'configuration':configuration, 'eval_id':case['id'], 'eval_name':case['name'],
              'exit_code':code, 'status':status, 'reason':reason, 'elapsed_seconds':elapsed,
              'sandbox':str(sandbox), 'directory':str(directory), 'boundary':boundary,
              'fixtures':fixtures, 'command':command, 'artifact_manifest_sha256':digest(directory/'artifact-manifest.json') if manifest else None}
    write_json(directory/'execution.json', result)
    print(json.dumps({key:result[key] for key in ['run_id','iteration','provider','configuration','eval_id','exit_code','status','reason']},ensure_ascii=False),flush=True)
    return result


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--provider', choices=['codex','claude','both'], default='both')
    cli.add_argument('--python', default=os.environ.get('BROLL_PYTHON','python3'))
    cli.add_argument('--node', default=os.environ.get('BROLL_NODE','node'))
    cli.add_argument('--runtime', type=Path, default=Path(os.environ.get('BROLL_RUNTIME',ROOT/'.runtime/motion')))
    cli.add_argument('--source-video', type=Path); cli.add_argument('--srt', type=Path); cli.add_argument('--vtt', type=Path)
    cli.add_argument('--boundary', choices=['auto','end-to-end','author-build'], default='auto')
    cli.add_argument('--workspace', type=Path, default=WORKSPACE)
    cli.add_argument('--iteration', type=int)
    cli.add_argument('--eval-ids', nargs='+', type=int)
    cli.add_argument('--configuration', choices=['with_skill'], default='with_skill')
    cli.add_argument('--timeout', type=int, default=360); cli.add_argument('--workers', type=int, default=2)
    return cli


def main(argv=None):
    cli = parser(); args = cli.parse_args(argv)
    try:
        if args.timeout < 1 or args.workers < 1: raise ValueError('Timeout and workers must be positive')
        cases = json.loads((ROOT/'evals/evals.json').read_text())['evals']
        if args.eval_ids:
            unknown = set(args.eval_ids) - {case['id'] for case in cases}
            if unknown: raise ValueError(f'Unknown evaluation ids: {sorted(unknown)}')
            cases = [case for case in cases if case['id'] in args.eval_ids]
        args.runtime = args.runtime.expanduser().resolve()
        supplied = any(value is not None for value in [args.source_video,args.srt,args.vtt])
        if args.boundary == 'auto': args.boundary = 'end-to-end' if supplied else 'author-build'
        if args.boundary == 'end-to-end':
            required = [('source-video',args.source_video)]
            if any(case['id'] != 3 for case in cases): required.append(('srt',args.srt))
            if any(case['id'] == 3 for case in cases): required.append(('vtt',args.vtt))
            for name, value in required:
                if value is None or not value.expanduser().is_file(): raise ValueError(f'Actual --{name} fixture file required')
        args.iteration_dir = reserve_iteration(args.workspace.expanduser().resolve(), args.iteration)
    except (OSError, ValueError) as exc:
        cli.error(str(exc))
    providers = ['codex','claude'] if args.provider == 'both' else [args.provider]
    configurations = [args.configuration]
    write_json(args.iteration_dir/'iteration.json', {'schema_version':1,'iteration':int(args.iteration_dir.name.split('-')[-1]),
               'created_at':datetime.now(timezone.utc).isoformat(),'providers':providers,'configurations':configurations,
               'eval_ids':[case['id'] for case in cases],'boundary':args.boundary,'timeout_seconds':args.timeout})
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_case,provider,case,configuration,args) for provider in providers for case in cases for configuration in configurations]
        results = [future.result() for future in futures]
    write_json(args.iteration_dir/'model-evaluations.json',results)
    write_json(ROOT/'reports'/f'model-evaluations-{args.iteration_dir.name}.json',results)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
