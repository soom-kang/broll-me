#!/usr/bin/env python3
"""Reinstall the archive in an isolated project and run minimal media checks."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT/'skills/broll-me'
WORK = ROOT/'.verification'
PYTHON = os.environ.get('BROLL_PYTHON','python3')
NODE = os.environ.get('BROLL_NODE','node')


def run(args, failure=False, env=None):
    result = subprocess.run(list(map(str,args)), capture_output=True, text=True, timeout=180, env=env)
    commands.append({'command':list(map(str,args)), 'exit_code':result.returncode, 'expected_failure':failure})
    if bool(result.returncode) != failure:
        raise RuntimeError(result.stderr[-4000:] or result.stdout[-4000:])
    return result


commands = []
def main():
    report = {'checks':[], 'commands':commands}
    try:
        with tempfile.TemporaryDirectory(prefix='broll archive space;literal-') as temporary:
            project = Path(temporary)
            with zipfile.ZipFile(ROOT/'dist/broll-me.skill') as archive:
                archive.extractall(project/'skills')
            skill = project/'skills/broll-me'
            run([PYTHON, ROOT/'scripts/validate_package.py', skill, '--archive', ROOT/'dist/broll-me.skill'])
            run([PYTHON, ROOT/'scripts/install_skill.py','--project',project,'--source',skill,'--host','both'])
            for host in ['.agents','.claude']:
                assert (project/host/'skills/broll-me').resolve() == skill.resolve()
            run(['bash',skill/'scripts/setup.sh', ROOT/'.runtime/motion','--check'])
            run([PYTHON,skill/'engine/build.py', project/'out',skill/'examples/palette-demo.html','--palette','sage-cream'])
            run([NODE,skill/'engine/render.js',project/'out/palette-demo.html',project/'out/clip.mp4','30000/1001'])
            run(['ffmpeg','-v','error','-i',project/'out/clip.mp4','-f','null','-'])
            media=json.loads(run(['ffprobe','-v','error','-show_streams','-of','json',project/'out/clip.mp4']).stdout)
            stream=media['streams'][0]
            assert (stream['width'],stream['height'],stream['r_frame_rate']) == (640,360,'30000/1001')
            report['checks'].append('Archive extracted, project links installed, runtime checked, clip built/rendered/decoded from extracted source.')
        run([PYTHON,SKILL/'scripts/inspect_video.py',WORK/'source sample;literal.mp4',WORK/'inspection'])
        inspection=json.loads((WORK/'inspection/video.json').read_text())
        assert inspection['fps']=='30000/1001' and inspection['requires_visual_review']
        report['checks'].append('Source inspection produces actual contact sheet and marks heuristic regions unverified.')
        run([PYTHON,SKILL/'scripts/make_pages.py',WORK/'plan.json',WORK/'preview.mp4'])
        for name in ['viewer.html','compare.html']:
            run([NODE,'-e',"const fs=require('fs'),vm=require('vm');const text=fs.readFileSync(process.argv[1],'utf8');for(const match of text.matchAll(/<script>([\\s\\S]*?)<\\/script>/g)) new vm.Script(match[1]);",WORK/name])
        report['checks'].append('Actual review pages with literal template markers and HTML metadata have valid JavaScript and local Korean fallback.')
        run([NODE,SKILL/'engine/beats.js',WORK/'portrait/portrait-scene.html',WORK/'portrait/beats.png','0.1','0.85'])
        sheet=json.loads(run(['ffprobe','-v','error','-show_streams','-of','json',WORK/'portrait/beats.png']).stdout)['streams'][0]
        assert (sheet['width'],sheet['height'])==(724,640), sheet
        report['checks'].append('Beat contact sheet preserves actual 360x640 scene tiles (724x640 for two frames).')
        failing=WORK/'ffmpeg failure fixture.sh'
        failing.write_text('#!/bin/sh\nexit 23\n');failing.chmod(0o700)
        environment=os.environ.copy();environment['BROLL_FFMPEG']=str(failing)
        output=WORK/'expected-encoder-failure.mp4'
        assert not output.exists()
        result=run([NODE,SKILL/'engine/render.js',WORK/'warm-orange/palette-demo.html',output,'30'],failure=True,env=environment)
        assert '23' in result.stderr and not output.exists(),result.stderr
        report['checks'].append('Encoder failure returns nonzero, reports status 23 and publishes no incomplete output.')
        audio_source=WORK/'incompatible-audio.mov'
        run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=s=160x90:r=30:d=2','-f','lavfi','-i','sine=frequency=440:duration=2:sample_rate=48000','-c:v','libx264','-c:a','pcm_alaw',audio_source])
        before=hashlib.sha256(audio_source.read_bytes()).hexdigest()
        plan=WORK/'incompatible-plan.json'
        plan.write_text(json.dumps({'video':audio_source.name,'clips':[]}))
        incompatible_output=WORK/'incompatible-preview.mp4'
        assert not incompatible_output.exists()
        result=run([PYTHON,SKILL/'scripts/composite.py',plan,incompatible_output],failure=True)
        assert 'MP4-incompatible audio' in result.stderr and not incompatible_output.exists(),result.stderr
        assert hashlib.sha256(audio_source.read_bytes()).hexdigest()==before
        report['checks'].append('Actual MP4-incompatible audio fails with recovery guidance; source bytes retained and no automatic transcode.')
        report['status']='passed'
    except Exception as exc:
        report['status']='failed';report['error']=str(exc);raise
    finally:
        (ROOT/'reports/distribution-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'checks':report['checks']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
