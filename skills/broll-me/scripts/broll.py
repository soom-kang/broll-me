#!/usr/bin/env python3
"""One host-neutral entry point for the existing local B-roll tools."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

SKILL = Path(__file__).resolve().parents[1]


class CommandFailure(Exception):
    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code if code > 0 else 128 - code


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CommandFailure(message, 2)


def runtime_environment(runtime):
    environment = os.environ.copy()
    environment['BROLL_RUNTIME'] = str(runtime)
    python = runtime / '.venv/bin/python'
    environment.setdefault('BROLL_PYTHON', str(python) if python.is_file() else sys.executable)
    environment.setdefault('BROLL_NODE', 'node')
    modules = runtime / 'node_modules'
    environment['NODE_PATH'] = str(modules) + (os.pathsep + environment['NODE_PATH'] if environment.get('NODE_PATH') else '')
    if (runtime / 'browsers').is_dir():
        environment.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(runtime / 'browsers'))
    return environment


def execute(command, environment, *, log_stdout=True):
    try:
        timeout = int(environment.get('BROLL_TIMEOUT_MS', '600000')) / 1000
        if timeout < 1:
            raise ValueError('BROLL_TIMEOUT_MS must be at least 1000')
        result = subprocess.run(list(map(str, command)), env=environment,
                                capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise CommandFailure(f'{Path(str(command[0])).name} timed out after {timeout:g}s', 124) from error
    except (OSError, ValueError) as error:
        raise CommandFailure(str(error)) from error
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if log_stdout and result.stdout:
        print(result.stdout.rstrip(), file=sys.stderr)
    if result.returncode:
        raise CommandFailure((result.stderr or result.stdout or 'Command failed').strip()[-4000:], result.returncode)
    return result.stdout


def parsed_output(text):
    try:
        return json.loads(text)
    except ValueError:
        for line in reversed(text.splitlines()):
            try:
                return json.loads(line)
            except ValueError:
                pass
    return None


def parser():
    cli = Parser(description=__doc__)
    cli.add_argument('--runtime', type=Path, default=None)
    commands = cli.add_subparsers(dest='command', required=True, parser_class=Parser)
    commands.add_parser('doctor', help='Check the pinned runtime and launch the selected browser; no installs.')
    inspect = commands.add_parser('inspect')
    inspect.add_argument('video', type=Path); inspect.add_argument('out_dir', type=Path)
    words = commands.add_parser('words')
    words.add_argument('transcript', type=Path)
    build = commands.add_parser('build')
    build.add_argument('out_dir', type=Path); build.add_argument('fragments', nargs='*', type=Path)
    build.add_argument('--scene', type=Path)
    palettes = build.add_mutually_exclusive_group()
    palettes.add_argument('--palette'); palettes.add_argument('--palette-file', type=Path)
    build.add_argument('--font-mode', choices=['shared', 'embedded'], default='shared')
    check = commands.add_parser('check')
    check.add_argument('html', type=Path)
    beats = commands.add_parser('beats')
    beats.add_argument('html', type=Path); beats.add_argument('output', type=Path)
    beats.add_argument('times', nargs='+', type=float)
    render = commands.add_parser('render')
    render.add_argument('html', type=Path); render.add_argument('output', type=Path)
    render.add_argument('--fps', default='30')
    render.add_argument('--quality', choices=['final', 'draft'], default='final')
    preview = commands.add_parser('preview')
    preview.add_argument('plan', type=Path); preview.add_argument('output', type=Path)
    preview.add_argument('--font-mode', choices=['shared', 'embedded'], default='shared')
    return cli


def dispatch(args, runtime, environment):
    python, node = environment['BROLL_PYTHON'], environment['BROLL_NODE']
    script = lambda name: SKILL / 'scripts' / name
    engine = lambda name: SKILL / 'engine' / name
    if args.command == 'doctor':
        output = execute(['bash', script('setup.sh'), runtime, '--check'], environment)
        return {'runtime': str(runtime), 'python': python, 'node': node,
                'browser': parsed_output(output), 'ready': True}
    if args.command == 'inspect':
        output = execute([python, script('inspect_video.py'), args.video, args.out_dir], environment)
        return {'video': parsed_output(output), 'outputs': [str((args.out_dir / name).resolve()) for name in ['video.json', 'contact.png']]}
    if args.command == 'words':
        output = execute([python, script('words.py'), args.transcript], environment, log_stdout=False)
        return {'estimated': True, 'text': output.rstrip()}
    if args.command == 'build':
        if bool(args.scene) == bool(args.fragments):
            raise CommandFailure('Provide either --scene SPEC.json or HTML fragments, exclusively', 2)
        command = [python, engine('build.py'), args.out_dir, *args.fragments, '--font-mode', args.font_mode]
        sources = args.fragments
        if args.scene:
            command += ['--scene', args.scene]; sources = [args.scene]
        if args.palette is not None: command += ['--palette', args.palette]
        if args.palette_file is not None: command += ['--palette-file', args.palette_file]
        execute(command, environment)
        return {'font_mode': args.font_mode, 'outputs': [str((args.out_dir / (source.stem + '.html')).resolve()) for source in sources],
                'palette': str((args.out_dir / 'palette.resolved.json').resolve())}
    if args.command == 'check':
        return parsed_output(execute([node, engine('check.js'), args.html], environment))
    if args.command == 'beats':
        return parsed_output(execute([node, engine('beats.js'), args.html, args.output, *args.times], environment))
    if args.command == 'render':
        return parsed_output(execute([node, engine('render.js'), args.html, args.output, args.fps, '--quality', args.quality], environment))
    if args.command == 'preview':
        execute([python, script('preview_bundle.py'), args.plan, args.output, '--font-mode', args.font_mode], environment)
        return {'font_mode': args.font_mode, 'outputs': [str(args.output.resolve()),
                *[str((args.output.parent / name).resolve()) for name in ['viewer.html', 'compare.html', 'TIMING.md']]]}
    raise CommandFailure('Unknown command', 2)


def main(argv=None):
    command = None
    try:
        args = parser().parse_args(argv)
        command = args.command
        runtime = (args.runtime or Path(os.environ.get('BROLL_RUNTIME', './motion'))).expanduser().resolve()
        result = dispatch(args, runtime, runtime_environment(runtime))
        print(json.dumps({'status': 'completed', 'command': command, 'result': result}, ensure_ascii=False))
        return 0
    except CommandFailure as error:
        print(json.dumps({'status': 'error', 'command': command, 'exit_code': error.code, 'message': str(error)}, ensure_ascii=False))
        return error.code
    except (OSError, ValueError) as error:
        print(json.dumps({'status': 'error', 'command': command, 'exit_code': 1, 'message': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
