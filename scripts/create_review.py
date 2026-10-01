#!/usr/bin/env python3
"""Use skill-creator's viewer, then safely embed HTML scene source in its JSON."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def protect_embedded_json(page):
    match=re.search(r'const EMBEDDED_DATA = (.+?);\n',page)
    if not match:
        raise ValueError('skill-creator viewer embedded JSON marker not found')
    data=json.loads(match[1])
    safe=json.dumps(data,ensure_ascii=True).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
    assert json.loads(safe)==data
    return page[:match.start(1)]+safe+page[match.end(1):]


def viewer_benchmark(benchmark):
    """Keep unavailable runs out of quality tables; preserve the original report."""
    data = json.loads(json.dumps(benchmark))
    data['runs'] = [run for run in data.get('runs', [])
                    if run.get('result', {}).get('pass_rate') is not None]
    for config, metrics in data.get('run_summary', {}).items():
        if config == 'delta' or not isinstance(metrics, dict):
            continue
        for name, stat in metrics.items():
            if isinstance(stat, dict) and stat.get('mean') is None:
                metrics[name] = None
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--creator',type=Path,required=True)
    parser.add_argument('--workspace',type=Path,default=ROOT/'skills/broll-me-workspace/iteration-2')
    parser.add_argument('--output',type=Path,default=ROOT/'reports/review.html')
    parser.add_argument('--benchmark',type=Path,default=ROOT/'skills/broll-me-workspace/iteration-2/claude/benchmark.json')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='broll-review-') as temporary:
        benchmark = Path(temporary) / 'benchmark.json'
        benchmark.write_text(json.dumps(viewer_benchmark(json.loads(args.benchmark.read_text()))))
        subprocess.run([sys.executable,str(args.creator/'eval-viewer/generate_review.py'),str(args.workspace),
            '--skill-name','broll-me','--benchmark',str(benchmark),'--static',str(args.output)],check=True)
    page=protect_embedded_json(args.output.read_text())
    args.output.write_text(page)
    print('Embedded HTML source safely escaped; original skill-creator viewer preserved.')


if __name__=='__main__':main()
