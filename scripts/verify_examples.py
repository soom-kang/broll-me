#!/usr/bin/env python3
"""Audit six example scenes across every preset, including chart/cursor tracks."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/broll-me'
WORK=ROOT/'.verification/examples'
PRESETS=['warm-orange','sage-cream','editorial-blue','midnight-cyan','kkumil-pink','onnimm-orange']
PYTHON=os.environ.get('BROLL_PYTHON','python3')
NODE=os.environ.get('BROLL_NODE','node')


def run(args):
    result=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=90)
    if result.returncode: raise RuntimeError(result.stderr[-4000:])


def case(fragment,preset):
    directory=WORK/fragment.stem/preset;directory.mkdir(parents=True,exist_ok=True)
    run([PYTHON,SKILL/'engine/build.py',directory,fragment,'--palette',preset])
    run([NODE,ROOT/'scripts/audit_scene.js',directory/fragment.name,directory/'audit.json'])
    result=json.loads((directory/'audit.json').read_text())
    colors=json.loads((SKILL/'palettes'/f'{preset}.json').read_text())['colors']
    assert result['palette']==colors and result['cssRoles']==colors
    return {'example':fragment.stem,'preset':preset,'audit':result}


def main():
    fragments=sorted((SKILL/'examples/opus-aoe2').glob('*.html'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda task:case(*task),[(fragment,preset) for fragment in fragments for preset in PRESETS]))
    for fragment in fragments:
        rows=[row for row in results if row['example']==fragment.stem]
        for row in rows:
            assert row['audit']['scene']==rows[0]['audit']['scene'] and row['audit']['geometry']==rows[0]['audit']['geometry'],row['example']
    report={'status':'passed','count':len(results),'scope':'Six example scenes × six presets; sampled geometry, beat/duration, CSS/JS roles and reverse-seek determinism. Full-length playback still needs human review.','results':results}
    (ROOT/'reports/example-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'passed','count':len(results)}))


if __name__=='__main__':main()
