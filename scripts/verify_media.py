#!/usr/bin/env python3
"""Verify six palettes, codecs, timing, source preservation and media failure behavior.

Uses generated fixtures: it does not certify real speech alignment or human visual QA.
"""
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/broll-me'
WORK=ROOT/'.verification'
PYTHON=os.environ.get('BROLL_PYTHON',sys.executable)
NODE=os.environ.get('BROLL_NODE','node')
FFMPEG=os.environ.get('BROLL_FFMPEG','ffmpeg')
FFPROBE=os.environ.get('BROLL_FFPROBE','ffprobe')
PRESETS=['warm-orange','sage-cream','editorial-blue','midnight-cyan','kkumil-pink','onnimm-orange']
COMMANDS=[]

def run(command, *, failure=False):
    completed=subprocess.run(list(map(str,command)),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    COMMANDS.append({'command':list(map(str,command)),'exit_code':completed.returncode,'expected_failure':failure})
    if failure:
        if completed.returncode==0: raise AssertionError('Expected failure: '+repr(command))
    elif completed.returncode:
        raise RuntimeError(completed.stderr.decode(errors='replace')[-4500:] or completed.stdout.decode(errors='replace')[-4500:])
    return completed.stdout

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def probe(path): return json.loads(run([FFPROBE,'-v','error','-show_streams','-show_format','-of','json',path]))
def pcm_hash(path): return hashlib.sha256(run([FFMPEG,'-v','error','-i',path,'-map','0:a:0','-f','s16le','-'])).hexdigest()
def write_json(path,data): path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def palette_case(preset):
    directory=WORK/preset
    directory.mkdir(parents=True,exist_ok=True)
    run([PYTHON,SKILL/'engine/build.py',directory,SKILL/'examples/palette-demo.html','--palette',preset])
    html=directory/'palette-demo.html'
    run([NODE,ROOT/'scripts/audit_scene.js',html,directory/'audit.json'])
    run([NODE,SKILL/'engine/render.js',html,directory/'clip.mp4','30000/1001'])
    media=probe(directory/'clip.mp4')
    stream=next(s for s in media['streams'] if s['codec_type']=='video')
    assert stream['width']==640 and stream['height']==360
    assert Fraction(stream['r_frame_rate'])==Fraction(30000,1001)
    run([FFMPEG,'-v','error','-i',directory/'clip.mp4','-f','null','-'])
    return {'preset':preset,'audit':json.loads((directory/'audit.json').read_text()),'video':stream}

def main():
    WORK.mkdir(exist_ok=True)
    report={'fixture':'synthetic color source and sine audio; no real speech','checks':[],'failures':[]}
    try:
        source=WORK/'source sample;literal.mp4'
        run([FFMPEG,'-v','error','-y','-f','lavfi','-i','color=c=0x303944:s=640x360:r=30000/1001:d=6','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=6','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-t','6',source])
        before=digest(source)
        with ThreadPoolExecutor(max_workers=2) as pool: cases=list(pool.map(palette_case,PRESETS))
        reference=cases[0]['audit']
        for case in cases:
            audit=case['audit']
            assert audit['scene']==reference['scene'] and audit['geometry']==reference['geometry'],case['preset']
            assert audit['seekDeterministic'] and audit['koreanFontReady']
        report['checks'].append('Six presets render at rational FPS; geometry, duration and seek determinism match.')
        report['palettes']=cases
        panel=WORK/'panel';panel.mkdir(exist_ok=True)
        run([PYTHON,SKILL/'engine/build.py',panel,SKILL/'examples/panel-demo.html','--palette','onnimm-orange'])
        run([NODE,ROOT/'scripts/audit_scene.js',panel/'panel-demo.html',panel/'audit.json'])
        run([NODE,SKILL/'engine/render.js',panel/'panel-demo.html',panel/'panel.mov','30000/1001'])
        alpha=next(s for s in probe(panel/'panel.mov')['streams'] if s['codec_type']=='video')
        assert alpha['codec_name']=='prores' and 'a' in alpha['pix_fmt']
        alpha_bytes=run([FFMPEG,'-v','error','-ss','0.85','-i',panel/'panel.mov','-frames:v','1','-vf','alphaextract','-pix_fmt','gray','-f','rawvideo','-'])
        assert min(alpha_bytes)==0 and max(alpha_bytes)>0
        report['checks'].append('Transparent panel exports ProRes 4444 with transparent and opaque pixels.')
        plan={'title':'Literal <script> /*CLIPS*/[] metadata','video':source.name,'fps':'30000/1001','palette':'onnimm-orange','clips':[{'id':'01','title':'Panel <img src=x onerror=alert(1)>','line':'꾸밀걸 <script>alert(1)</script> Use /*FONT_CSS*/ here','in':1,'out':5,'kind':'panel','file':'panel/panel.mov'}],'notes':['Illustrative fixture only.']}
        write_json(WORK/'plan.json',plan)
        preview=WORK/'preview.mp4'
        run([PYTHON,SKILL/'scripts/composite.py',WORK/'plan.json',preview])
        run([PYTHON,SKILL/'scripts/make_pages.py',WORK/'plan.json',preview])
        for page in ['viewer.html','compare.html']:
            run([NODE,'-e', "const fs=require('fs'),vm=require('vm');const text=fs.readFileSync(process.argv[1],'utf8');for(const match of text.matchAll(/<script>([\\s\\S]*?)<\\/script>/g)) new vm.Script(match[1]);",WORK/page])
        video=next(s for s in probe(preview)['streams'] if s['codec_type']=='video')
        srcvideo=next(s for s in probe(source)['streams'] if s['codec_type']=='video')
        assert abs(float(video['duration'])-float(srcvideo['duration']))<=1/float(Fraction('30000/1001'))+0.002
        assert pcm_hash(source)==pcm_hash(preview),'Source PCM differs from preview'
        assert digest(source)==before,'Source was overwritten'
        def frame_at(second):
            return run([FFMPEG,'-v','error','-ss',str(second),'-i',preview,'-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-'])
        early,late=frame_at(2.5),frame_at(4.5)
        assert len(early)==len(late) and sum(abs(a-b) for a,b in zip(early,late))/len(early)<1.0,'Last-frame hold disappears before the long slot ends'
        run([FFMPEG,'-v','error','-i',preview,'-f','null','-'])
        report['checks'].append('Long-slot preview keeps source duration/FPS/audio and preserves source bytes.')
        silent=WORK/'portrait.mp4'
        run([FFMPEG,'-v','error','-y','-f','lavfi','-i','color=c=0x303944:s=360x640:r=25:d=3','-c:v','libx264','-pix_fmt','yuv420p',silent])
        fragment=(SKILL/'examples/palette-demo.html').read_text().replace('W:640','W:360').replace('H:360','H:640').replace('W: 640','W: 360').replace('H: 360','H: 640')
        fragment=fragment.replace('w:512','w:280').replace('left:-224px','left:-120px').replace('font-size:31px','font-size:24px').replace('.demo-dot{','.demo-dot{display:none;')
        (WORK/'portrait-scene.html').write_text(fragment)
        portrait=WORK/'portrait';portrait.mkdir(exist_ok=True)
        run([PYTHON,SKILL/'engine/build.py',portrait,WORK/'portrait-scene.html','--palette','kkumil-pink'])
        run([NODE,SKILL/'engine/render.js',portrait/'portrait-scene.html',portrait/'clip.mp4','25'])
        pvideo=next(s for s in probe(portrait/'clip.mp4')['streams'] if s['codec_type']=='video')
        assert (pvideo['width'],pvideo['height'])==(360,640)
        silent_plan={'title':'Silent portrait','video':silent.name,'fps':'25','clips':[{'id':'01','title':'Pink','line':'꾸밀걸','in':0.5,'out':2.5,'kind':'full','file':'portrait/clip.mp4'}],'notes':[]}
        write_json(WORK/'silent-plan.json',silent_plan)
        run([PYTHON,SKILL/'scripts/composite.py',WORK/'silent-plan.json',WORK/'silent-preview.mp4'])
        assert not any(s['codec_type']=='audio' for s in probe(WORK/'silent-preview.mp4')['streams'])
        report['checks'].append('Portrait 360x640 at 25 FPS renders; silent insertion needs no audio stream.')
        bad=dict(plan);bad['clips']=[dict(plan['clips'][0],out=99)]
        write_json(WORK/'bad-plan.json',bad)
        run([PYTHON,SKILL/'scripts/composite.py',WORK/'bad-plan.json',WORK/'bad-preview.mp4'],failure=True)
        run([PYTHON,SKILL/'engine/build.py',WORK/'invalid',SKILL/'examples/palette-demo.html','--palette','unknown'],failure=True)
        run([NODE,SKILL/'engine/render.js',WORK/'missing.html',WORK/'missing.mp4'],failure=True)
        custom=json.loads((SKILL/'palettes/kkumil-pink.json').read_text());custom['id']='custom-pink'
        write_json(WORK/'custom.json',custom)
        run([PYTHON,SKILL/'engine/build.py',WORK/'custom',SKILL/'examples/palette-demo.html','--palette-file',WORK/'custom.json'])
        custom['colors']['ink']='#FFFFFF';write_json(WORK/'bad-custom.json',custom)
        run([PYTHON,SKILL/'engine/build.py',WORK/'bad-custom',SKILL/'examples/palette-demo.html','--palette-file',WORK/'bad-custom.json'],failure=True)
        report['checks'].append('Custom palettes work; unknown/low-contrast palette, missing input and invalid slot fail.')
        # Curated contact sheet; source label metadata is never passed through a shell.
        command=[FFMPEG,'-v','error','-y']
        for preset in PRESETS: command+=['-i',WORK/preset/'audit.png']
        command+=['-filter_complex','[0:v][1:v][2:v][3:v][4:v][5:v]xstack=inputs=6:layout=0_0|w0_0|w0+w1_0|0_h0|w0_h0|w0+w1_h0[out]','-map','[out]','-frames:v','1',WORK/'palette-gallery.png']
        run(command)
        report['status']='passed'
    except Exception as exc:
        report['status']='failed';report['failures'].append(str(exc));raise
    finally:
        report['commands']=COMMANDS
        write_json(ROOT/'reports/media-validation.json',report)
    print(json.dumps({'status':report['status'],'checks':report['checks']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
