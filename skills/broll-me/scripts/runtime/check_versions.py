"""Check the pinned executable profile without installing or modifying anything."""
import json
from pathlib import Path
import platform
import re
import subprocess
import sys


def check(profile_path, node, ffmpeg, ffprobe):
    profile = json.loads(Path(profile_path).read_text())
    actual = {'python': platform.python_version()}
    for name, executable, arguments in [('node',node,['--version']),('ffmpeg',ffmpeg,['-version']),('ffprobe',ffprobe,['-version'])]:
        result = subprocess.run([executable,*arguments],capture_output=True,text=True,timeout=15,check=True)
        match = re.search(r'\b(\d+\.\d+\.\d+)\b',result.stdout.lstrip('v'))
        if not match:
            raise ValueError(f'Cannot identify {name} version')
        actual[name] = match[1]
    mismatches = [f'{name}={version} (expected {profile[name]})' for name,version in actual.items() if profile[name] != version]
    if mismatches:
        raise ValueError('Pinned runtime mismatch: '+', '.join(mismatches)+'. Select matching executables using BROLL_NODE/BROLL_PYTHON/BROLL_FFMPEG/BROLL_FFPROBE; setup does not install system binaries.')
    return actual


if __name__ == '__main__':
    try:
        if len(sys.argv) != 5:
            raise ValueError('Usage: check_versions.py versions.json node ffmpeg ffprobe')
        print(json.dumps({'status':'passed','versions':check(*sys.argv[1:])}))
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
