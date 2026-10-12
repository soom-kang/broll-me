#!/usr/bin/env python3
"""One host-neutral entry point for the existing local B-roll tools."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

SKILL = Path(__file__).resolve().parents[1]
TIMEOUT_CLEANUP_GRACE_SECONDS = 5
TIMEOUT_REAP_SECONDS = 1


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


def timeout_output(error):
    """TimeoutExpired may retain bytes even when Popen uses text mode."""
    def decoded(value):
        return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else (value or '')
    return decoded(error.output), decoded(error.stderr)


def cancel_timed_out(process, *, owns_process_group):
    """Offer cleanup time, then contain descendants and bound pipe draining."""
    print(f'Timeout: requesting child cleanup; grace {TIMEOUT_CLEANUP_GRACE_SECONDS:g}s', file=sys.stderr)
    try:
        process.terminate()
    except ProcessLookupError:
        pass
    except OSError as error:
        print(f'Timeout: cleanup signal failed: {error}', file=sys.stderr)
    try:
        output = process.communicate(timeout=TIMEOUT_CLEANUP_GRACE_SECONDS)
    except subprocess.TimeoutExpired as error:
        output = timeout_output(error)
    # The direct child may have exited while descendants still hold its pipes
    # or run with their own output redirected. Only our isolated group is owned.
    if owns_process_group:
        try:
            os.killpg(process.pid, signal.SIGKILL)
            print('Timeout: SIGKILL sent to owned process group; cleanup may be incomplete', file=sys.stderr)
        except ProcessLookupError:
            pass
        except OSError as error:
            print(f'Timeout: owned process group could not be terminated: {error}', file=sys.stderr)
            if process.poll() is None:
                try:
                    process.kill()
                except OSError as child_error:
                    print(f'Timeout: child termination also failed: {child_error}', file=sys.stderr)
    elif process.poll() is None:
        try:
            process.kill()
        except OSError as error:
            print(f'Timeout: child could not be terminated: {error}', file=sys.stderr)
        print('Timeout: child forcibly terminated; descendant cleanup is not guaranteed on this platform', file=sys.stderr)
    try:
        return process.communicate(timeout=TIMEOUT_REAP_SECONDS)
    except subprocess.TimeoutExpired as error:
        output = timeout_output(error)
        print('Timeout: diagnostic pipes did not close; capture stopped with cleanup unconfirmed', file=sys.stderr)
        if owns_process_group:
            for stream in (process.stdout, process.stderr):
                if stream:
                    stream.close()
        # Windows communicate() can leave daemon pipe-reader threads blocked
        # in buffered reads. Synchronously closing their streams would wait for
        # those reads; retain their ownership and return the bounded failure.
        try:
            process.wait(timeout=TIMEOUT_REAP_SECONDS)
        except subprocess.TimeoutExpired:
            print('Timeout: child exit could not be confirmed within the reap deadline', file=sys.stderr)
        return output


def child_diagnostics(stdout, stderr, *, log_stdout):
    if stderr:
        print(stderr.rstrip(), file=sys.stderr)
    if log_stdout and stdout:
        print(stdout.rstrip(), file=sys.stderr)


def execute(command, environment, *, log_stdout=True):
    try:
        timeout = int(environment.get('BROLL_TIMEOUT_MS', '600000')) / 1000
        if timeout < 1:
            raise ValueError('BROLL_TIMEOUT_MS must be at least 1000')
        owns_process_group = os.name == 'posix'
        process = subprocess.Popen(list(map(str, command)), env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=owns_process_group)
    except (OSError, ValueError) as error:
        raise CommandFailure(str(error)) from error
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        stdout, stderr = cancel_timed_out(process, owns_process_group=owns_process_group)
        child_diagnostics(stdout, stderr, log_stdout=True)
        details = stderr.strip()[-4000:]
        message = f'{Path(str(command[0])).name} timed out after {timeout:g}s'
        if details:
            message += '\n' + details
        raise CommandFailure(message, 124) from error
    child_diagnostics(stdout, stderr, log_stdout=log_stdout)
    if process.returncode:
        raise CommandFailure((stderr or stdout or 'Command failed').strip()[-4000:], process.returncode)
    return stdout


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
