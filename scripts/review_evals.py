#!/usr/bin/env python3
"""Grade only fresh manifest-owned host artifacts; audit/decode existing media, never rerender it."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/broll-me'
WORKSPACE = ROOT / 'skills/broll-me-workspace'
PRESETS = {1: 'midnight-cyan', 2: 'kkumil-pink', 3: 'onnimm-orange'}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def manifest_files(directory: Path, execution: dict) -> dict[str, bytes]:
    """Do not discover candidate evidence via glob or unowned file existence."""
    path = directory / 'artifact-manifest.json'
    if path.is_symlink(): raise ValueError('Artifact manifest must not be symlinked')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != execution.get('artifact_manifest_sha256'):
        raise ValueError('Artifact manifest digest mismatch')
    manifest = json.loads(raw)
    if manifest.get('run_id') != execution.get('run_id') or manifest.get('schema_version') != 1:
        raise ValueError('Manifest is not owned by this run UUID')
    files = {}
    for name, metadata in manifest.get('files', {}).items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name or not relative.parts or relative.parts[0] != 'outputs':
            raise ValueError(f'Unsafe manifest path: {name}')
        candidate = directory / name
        parents = [candidate, *(directory / PurePosixPath(*relative.parts[:index]) for index in range(1,len(relative.parts)))]
        if directory.is_symlink() or any(parent.is_symlink() for parent in parents):
            raise ValueError(f'Symlinked artifact path: {name}')
        candidate.resolve().relative_to(directory.resolve())
        data = candidate.read_bytes()
        if len(data) != metadata.get('bytes') or hashlib.sha256(data).hexdigest() != metadata.get('sha256'):
            raise ValueError(f'Manifest artifact changed: {name}')
        files[name] = data
    return files


def parsed_json(files, name):
    try: return json.loads(files['outputs/' + name])
    except (KeyError, ValueError): return None


def command_path(value, execution):
    path = Path(value)
    return (path if path.is_absolute() else Path(execution['sandbox']) / path).resolve()


def is_environment_error(message):
    markers = ['machport', 'operation not permitted', 'permission denied', 'failed to launch',
               'browser has been closed', 'executable doesn\'t exist', 'cannot find module',
               'browser executable not found', 'missing executable']
    return any(marker in str(message).lower() for marker in markers)


def run_command(args, *, binary=False):
    result = subprocess.run(list(map(str,args)), capture_output=True, text=not binary, timeout=180)
    if result.returncode:
        error = result.stderr.decode(errors='replace') if binary else result.stderr
        raise RuntimeError(error[-3000:] or 'Local artifact audit failed')
    return result.stdout


def audit_html(html, directory, name):
    """Inspect the supplied HTML; no render.js or beats.js is called by the reviewer."""
    target = directory / 'harness-audit' / (name + '.json')
    run_command([os.environ.get('BROLL_NODE','node'),ROOT/'scripts/audit_scene.js',html,target])
    return json.loads(target.read_text())


def probe_existing(path):
    return json.loads(run_command([os.environ.get('BROLL_FFPROBE','ffprobe'),'-v','error','-show_streams','-show_format','-of','json',path]))


def verify_existing_media(path, panel=False, duration=1.0):
    info = probe_existing(path)
    video = next(stream for stream in info['streams'] if stream['codec_type'] == 'video')
    correct = ((video['width'],video['height']) == (640,360)
               and Fraction(video['r_frame_rate']) == Fraction(30000,1001)
               and abs(float(video.get('duration',info['format']['duration']))-duration) <= float(Fraction(1001,30000)) + .005)
    if panel: correct = correct and video['codec_name'] == 'prores' and 'a' in video.get('pix_fmt','')
    run_command([os.environ.get('BROLL_FFMPEG','ffmpeg'),'-v','error','-i',path,'-f','null','-'])
    return correct, {'width':video['width'],'height':video['height'],'fps':video['r_frame_rate'],
                     'duration':video.get('duration',info['format']['duration']),'codec':video['codec_name'],'pix_fmt':video.get('pix_fmt')}


def palette_matches(snapshot, audit, wanted):
    return bool(snapshot and audit and snapshot.get('id') == wanted['id']
                and snapshot.get('colors') == wanted['colors']
                and audit.get('palette') == wanted['colors'] and audit.get('cssRoles') == wanted['colors'])


class ContentParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.hidden = 0; self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in {'script','style'}: self.hidden += 1
    def handle_endtag(self, tag):
        if tag in {'script','style'}: self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden and data.strip(): self.parts.append(data.strip())


def text_content(raw):
    parser = ContentParser(); parser.feed(raw.decode()); return parser.parts


def palette_switch_matches(main_snapshot, main_audit, warm_snapshot, warm_audit,
                           main_html: bytes, warm_html: bytes, commands: list | None = None):
    cyan = json.loads((SKILL/'palettes/midnight-cyan.json').read_text())
    warm = json.loads((SKILL/'palettes/warm-orange.json').read_text())
    palettes = palette_matches(main_snapshot,main_audit,cyan) and palette_matches(warm_snapshot,warm_audit,warm)
    invariants = bool(main_audit and warm_audit and all(main_audit.get(key) == warm_audit.get(key)
                      for key in ['scene','geometry','W','H','T','alpha']) and text_content(main_html) == text_content(warm_html))
    same_spec = True
    if commands is not None:
        builds = [record for record in commands if record.get('command') == 'build' and record.get('exit_code') == 0]
        scene_digests = [record.get('scene_sha256') for record in builds]
        same_spec = len(builds) >= 2 and all(scene_digests) and len(set(scene_digests)) == 1
    return bool(palettes and invariants and same_spec)


def not_scored(directory, execution, reason, status=None):
    value = {'expectations':[], 'summary':{'passed':0,'failed':0,'total':0,'pass_rate':None},
             'status':status or execution.get('status'),'notes':[reason,'No quality score assigned; existing historical outputs were not consulted.']}
    write(directory/'grading.json',value)
    return {'eval_id':execution['eval_id'],'eval_name':execution.get('eval_name',str(execution['eval_id'])),
            'configuration':execution['configuration'],'run_number':1,'run_id':execution.get('run_id'),
            'status':value['status'],'result':{**value['summary'],'time_seconds':execution.get('elapsed_seconds'),
                                            'tokens':None,'tool_calls':None,'errors':None},
            'expectations':[],'notes':value['notes']}


def grade(directory):
    execution = json.loads((directory/'execution.json').read_text())
    if execution['status'] != 'completed' or execution.get('exit_code') != 0:
        return not_scored(directory,execution,execution.get('reason') or f"Host status: {execution['status']}")
    try: files = manifest_files(directory,execution)
    except (OSError, ValueError, KeyError) as exc:
        return not_scored(directory,execution,f'Current-run evidence unavailable: {exc}','evidence-invalid')
    eval_id = execution['eval_id']; e2e = execution['boundary'] == 'end-to-end'
    expectations, notes, audit = [], [], None
    def expect(text, passed, evidence):
        expectations.append({'text':text,'passed':bool(passed),'evidence':evidence})
    compiled = 'outputs/built/clip.html' in files
    expect('Host supplies current-run compiled scene HTML.',compiled,'Evidence: manifest-owned outputs/built/clip.html only')
    error = None
    if compiled:
        try: audit = audit_html(directory/'outputs/built/clip.html',directory,'main')
        except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired) as exc: error = str(exc)
        if error and is_environment_error(error):
            return not_scored(directory,execution,'Reviewer environment could not audit existing host HTML: '+error,'blocked')
    wanted = json.loads((SKILL/'palettes'/f'{PRESETS[eval_id]}.json').read_text())
    snapshot = parsed_json(files,'built/palette.resolved.json')
    expect('Requested palette matches the owned snapshot and actual CSS/JS.',palette_matches(snapshot,audit,wanted),
           f"requested={wanted['id']}; snapshot={None if not snapshot else snapshot.get('id')}; audit error={error}")
    shape_ok = audit and (audit.get('W'),audit.get('H'),audit.get('T'),audit.get('alpha')) == (640,360,1,eval_id==3)
    expect('Scene dimensions, duration and treatment match the approved fixture.',shape_ok,
           f"scene={None if not audit else {key:audit.get(key) for key in ['W','H','T','alpha']}}")
    expect('Korean font, error-free local resources and deterministic seek pass.',
           audit and audit.get('koreanFontReady') and audit.get('seekDeterministic') and not audit.get('errors') and not audit.get('remoteRequests'),
           f"local HTML audit only; fonts={None if not audit else audit.get('loadedFonts')}; error={error}")
    commands = []
    if 'outputs/commands.jsonl' in files:
        try: commands = [json.loads(line) for line in files['outputs/commands.jsonl'].decode().splitlines() if line.strip()]
        except ValueError: notes.append('Invalid owned command log')
    if e2e:
        required = {'doctor','inspect','words','build','check','render','preview','beats'}
        completed = {record.get('command') for record in commands if record.get('exit_code') == 0
                     and isinstance(record.get('result'),dict) and record['result'].get('status') == 'completed'}
        expect('Host executed the shared CLI end-to-end on supplied fixture files.',required <= completed,
               f"successful owned CLI commands={sorted(completed)}; required={sorted(required)}")
        inspect_calls = [record for record in commands if record.get('command') == 'inspect' and record.get('exit_code') == 0]
        fixture = execution.get('fixtures',{}).get('source-video',{})
        source = Path(fixture['sandbox_path']) if fixture.get('sandbox_path') else None
        source_ok = bool(source and source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == fixture.get('sha256'))
        inspected_actual = bool(inspect_calls and source and len(inspect_calls[-1].get('args',[])) > 1
                                and command_path(inspect_calls[-1]['args'][1],execution) == source.resolve())
        video_info = parsed_json(files,'inspection/video.json')
        expect('Provided source bytes are preserved and actually inspected.',source_ok and inspected_actual and video_info is not None,
               f"actual supplied source={bool(fixture)}; preserved={source_ok}; inspect path matches={inspected_actual}; owned video.json={video_info is not None}")
        transcript = execution.get('fixtures',{}).get('vtt' if eval_id == 3 else 'srt',{})
        transcript_path = Path(transcript['sandbox_path']) if transcript.get('sandbox_path') else None
        words_calls = [record for record in commands if record.get('command') == 'words' and record.get('exit_code') == 0]
        transcript_ok = bool(transcript_path and transcript_path.is_file()
                             and hashlib.sha256(transcript_path.read_bytes()).hexdigest() == transcript.get('sha256')
                             and words_calls and len(words_calls[-1].get('args',[])) > 1
                             and command_path(words_calls[-1]['args'][1],execution) == transcript_path.resolve())
        expect('Host used the actual supplied transcript bytes.',transcript_ok and 'outputs/words.json' in files,
               f"provided transcript={bool(transcript)}; preserved and passed to words={transcript_ok}; owned words.json={'outputs/words.json' in files}")
        clip_name = 'clip.mov' if eval_id == 3 else 'clip.mp4'
        media_ok, media_info = False, None
        if 'outputs/' + clip_name in files:
            try: media_ok,media_info = verify_existing_media(directory/'outputs'/clip_name,panel=eval_id==3)
            except (OSError,RuntimeError,ValueError,StopIteration,KeyError,subprocess.TimeoutExpired) as exc: notes.append('Host clip audit: '+str(exc))
        expect('Existing host-rendered clip decodes with required codec, dimensions and rational FPS.',media_ok,
               f"manifest-owned file={clip_name}; existing media={media_info}; no reviewer render occurred")
        preview_ok, preview_info, source_meta = False, None, None
        if source_ok and 'outputs/preview.mp4' in files:
            try:
                source_meta = probe_existing(source)
                video_stream = next(stream for stream in source_meta['streams'] if stream['codec_type']=='video')
                duration = float(video_stream.get('duration',source_meta['format']['duration']))
                preview_ok,preview_info = verify_existing_media(directory/'outputs/preview.mp4',duration=duration)
                preview_ok = preview_ok and video_info and (video_info.get('width'),video_info.get('height'),Fraction(video_info.get('fps','0'))) == (video_stream['width'],video_stream['height'],Fraction(video_stream['r_frame_rate']))
                if any(stream['codec_type']=='audio' for stream in source_meta['streams']):
                    audio = lambda path: hashlib.sha256(run_command([os.environ.get('BROLL_FFMPEG','ffmpeg'),'-v','error','-i',path,'-map','0:a:0','-f','s16le','-'],binary=True)).hexdigest()
                    preview_ok = preview_ok and audio(source) == audio(directory/'outputs/preview.mp4')
            except (OSError,RuntimeError,ValueError,StopIteration,KeyError,subprocess.TimeoutExpired) as exc: notes.append('Host preview audit: '+str(exc))
        pages = all('outputs/'+name in files for name in ['plan.json','TIMING.md','viewer.html','compare.html','beats.png'])
        plan = parsed_json(files,'plan.json')
        plan_ok = False
        if plan and source and isinstance(plan.get('clips'),list) and len(plan['clips']) == 1:
            try:
                item = plan['clips'][0]
                plan_ok = (command_path(plan['video'],{**execution,'sandbox':str(directory/'outputs')}) == source.resolve()
                           and Fraction(plan['fps']) == Fraction(30000,1001)
                           and (item.get('id'),item.get('file'),item.get('kind'),item.get('in'),item.get('out'))
                           == ('01',clip_name,'panel' if eval_id==3 else 'full',1,3))
            except (ValueError,KeyError,TypeError): pass
        expect('Host preview preserves source duration/audio and supplies the approved insertion deliverables.',preview_ok and pages and plan_ok,
               f"existing preview={preview_info}; owned plan/TIMING/pages/beats={pages}; slot/source/fps={plan_ok}; no reviewer render occurred")
    else:
        notes.append('Author/build boundary only; no host-rendering, fixture-inspection or audio-preservation score assigned.')
    if eval_id == 1:
        warm_audit = None
        warm_html = files.get('outputs/warm-built/clip.html',b'')
        if warm_html:
            try: warm_audit = audit_html(directory/'outputs/warm-built/clip.html',directory,'warm')
            except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired) as exc: notes.append('Warm HTML audit: '+str(exc))
        switch = palette_switch_matches(snapshot,audit,parsed_json(files,'warm-built/palette.resolved.json'),warm_audit,
                                        files.get('outputs/built/clip.html',b''),warm_html,commands if e2e else None)
        expect('Warm-orange and midnight-cyan both resolve while the same scene/content/timing remains.',switch,
               f"warm snapshot/CSS/JS verified first; same SceneSpec digest required={e2e}; invariants verified only after both palettes pass")
        if e2e:
            warm_media = False
            if 'outputs/warm-clip.mp4' in files:
                try: warm_media,_ = verify_existing_media(directory/'outputs/warm-clip.mp4')
                except (OSError,RuntimeError,ValueError,StopIteration,KeyError,subprocess.TimeoutExpired) as exc: notes.append('Warm host clip audit: '+str(exc))
            expect('Both palette variants were rendered by the host.',warm_media and 'outputs/warm-beats.png' in files,
                   f"owned warm-clip.mp4 decode={warm_media}; owned warm-beats.png={'outputs/warm-beats.png' in files}")
    timing = json.loads((directory/'timing.json').read_text())
    passed = sum(row['passed'] for row in expectations)
    summary = {'passed':passed,'failed':len(expectations)-passed,'total':len(expectations),'pass_rate':passed/len(expectations)}
    notes += ['Only this run UUID and its SHA-256-owned artifacts were graded.',
              'The reviewer audits/decode existing host outputs, never rerenders them as host evidence.',
              'Synthetic fixture coverage does not establish real speech alignment or human visual approval.']
    write(directory/'grading.json',{'expectations':expectations,'summary':summary,'status':'evaluated','notes':notes})
    (directory/'evaluation.md').write_text(f"Host: {execution['provider']}\nRun: {execution['run_id']}\nBoundary: {execution['boundary']}\nAssertions: {passed}/{len(expectations)}\n\n"+'\n'.join(notes)+'\n')
    return {'eval_id':eval_id,'eval_name':execution.get('eval_name',str(eval_id)), 'configuration':execution['configuration'],
            'run_number':1,'run_id':execution['run_id'],'status':'evaluated',
            'result':{**summary,'time_seconds':execution.get('elapsed_seconds'),'tokens':timing.get('total_tokens'),'tool_calls':None,'errors':None},
            'expectations':expectations,'notes':notes}


def metrics(rows):
    summary = {}
    for name in ['pass_rate','time_seconds','tokens']:
        numbers = [row['result'][name] for row in rows if row['result'].get('pass_rate') is not None and row['result'].get(name) is not None]
        summary[name] = {'mean':statistics.mean(numbers),'stddev':statistics.pstdev(numbers),'min':min(numbers),'max':max(numbers)} if numbers else {'mean':None,'stddev':None,'min':None,'max':None}
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,default=WORKSPACE); parser.add_argument('--iteration',type=int)
    args = parser.parse_args(argv)
    candidates = [path for path in args.workspace.glob('iteration-*') if (path/'iteration.json').is_file()]
    if args.iteration is None:
        if not candidates: parser.error('No fresh manifest-based iteration exists; historical results are unchanged')
        iteration = max(candidates,key=lambda path:int(path.name.split('-')[-1]))
    else: iteration = args.workspace / f'iteration-{args.iteration}'
    if not (iteration/'iteration.json').is_file(): parser.error('Legacy or missing iteration; historical grading will not be overwritten')
    metadata = json.loads((iteration/'iteration.json').read_text())
    combined = []
    for provider in metadata['providers']:
        paths = sorted((iteration/provider).glob('eval-*/*/run-*/execution.json'))
        with ThreadPoolExecutor(max_workers=2) as pool: runs = list(pool.map(grade,[path.parent for path in paths]))
        benchmark = {'metadata':{'skill_name':'broll-me','skill_path':str(SKILL),'executor_model':provider,
                     'timestamp':datetime.now(timezone.utc).isoformat(),'iteration':metadata['iteration'],
                     'evals_run':metadata['eval_ids'],'runs_per_configuration':1,'scope':metadata['boundary'],
                     'status_counts':{name:sum(row['status']==name for row in runs) for name in ['evaluated','blocked','timeout','failed','evidence-invalid']},
                     'blocked_runs':sum(row['status']=='blocked' for row in runs)},'runs':runs,'run_summary':{}}
        benchmark['run_summary']['with_skill'] = metrics([row for row in runs if row['configuration']=='with_skill'])
        write(iteration/provider/'benchmark.json',benchmark); combined.append(benchmark)
    write(iteration/'model-benchmarks.json',combined)
    write(ROOT/'reports'/f'model-benchmarks-{iteration.name}.json',combined)
    print(json.dumps([{'provider':value['metadata']['executor_model'],'statuses':value['metadata']['status_counts'],'summary':value['run_summary']} for value in combined],ensure_ascii=False,indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
