#!/usr/bin/env python3
"""Run/status the private connection; credentials stay in memory or OS keyring."""
import argparse
import getpass
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import urllib.request

SERVICE = 'connected-knowledge-private-tunnel'


def credential(runtime, store=False):
    import keyring
    from keyring.backends.fail import Keyring as FailKeyring
    backend = keyring.get_keyring()
    if isinstance(backend, FailKeyring):
        if store:
            raise ValueError('No OS credential store available; use foreground connection without saving the key')
        if not sys.stdin.isatty():
            raise ValueError('An OS credential store is required for unattended startup')
        return getpass.getpass('Restricted tunnel runtime key (hidden, not saved): ')
    # Reject plaintext/file backends. Optional third-party backends are not trusted here.
    if not type(backend).__module__.startswith(('keyring.backends.macOS', 'keyring.backends.SecretService', 'keyring.backends.kwallet')):
        if store:
            raise ValueError('Unsupported credential backend; use the OS keyring')
        if not sys.stdin.isatty():
            raise ValueError('An OS credential store is required for unattended startup')
        return getpass.getpass('Restricted tunnel runtime key (hidden, not saved): ')
    key = keyring.get_password(SERVICE, str(runtime))
    if store:
        key = getpass.getpass('Restricted tunnel runtime key (hidden; save in OS keyring): ')
        if not key.strip():
            raise ValueError('A runtime key is required')
        keyring.set_password(SERVICE, str(runtime), key)
    elif not key:
        if not sys.stdin.isatty():
            raise ValueError('Save a key in the OS keyring before unattended startup')
        key = getpass.getpass('Restricted tunnel runtime key (hidden, not saved): ')
    return key


def status(runtime):
    result = {'state': 'offline', 'live': False, 'ready': False}
    health = runtime/'health.url'
    if not health.exists():
        return result
    url = health.read_text().strip()
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.path not in ('', '/'):
        raise ValueError('Invalid local health address')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for route, key in [('healthz', 'live'), ('readyz', 'ready')]:
        try:
            with opener.open(url.rstrip('/') + '/' + route, timeout=2) as response:
                result[key] = response.status == 200
        except (OSError, urllib.error.URLError):
            pass
    result['state'] = 'ready' if result['ready'] else 'starting' if result['live'] else 'offline'
    return result


def run(runtime, store=False):
    from install_support import runtime_lock
    with runtime_lock(runtime, shared=True):
        if (runtime/'install-pending.json').exists():
            raise ValueError('Finish the interrupted runtime installation before connecting')
        return _run(runtime, store)


def _run(runtime, store=False):
    if status(runtime)['live']:
        raise ValueError('Connection already running; refusing a duplicate')
    settings = json.loads((runtime/'runtime.json').read_text())
    binary = runtime/'bin/tunnel-client'
    if (runtime/'install-current.json').exists():
        from runtime_install import current
        managed = current(runtime)
        binary = runtime/'releases'/managed['generation']/'bin/tunnel-client'
    if not binary.is_file() or binary.is_symlink():
        raise ValueError('Install the official tunnel-client before connecting')
    key = credential(runtime, store)
    env = dict(os.environ, CONTROL_PLANE_API_KEY=key,
               CONNECTED_KNOWLEDGE_PRIVATE_CONFIG=str(runtime/'capture-config.json'),
               TUNNEL_CLIENT_PROFILE_DIR=str(runtime/'profiles'),
               HEALTH_URL_FILE=str(runtime/'health.url'))
    profile = runtime/'profiles/private.yaml'
    if not profile.exists():
        # A wrapper argv avoids shell quoting and supports paths containing spaces.
        launcher = runtime/'server.sh'
        import shlex
        python = str(runtime/'venv/bin/python') if (runtime/'install-current.json').exists() else sys.executable
        launcher.write_text('#!/bin/sh\nexec ' + shlex.quote(python) + ' '
                            + shlex.quote(str(runtime/'scripts/capture_mcp.py')) + '\n')
        launcher.chmod(0o700)
        subprocess.run([str(binary), 'init', '--sample', 'sample_mcp_stdio_local',
                        '--profile', 'private', '--tunnel-id', settings['tunnel_id'],
                        '--mcp-command', shlex.quote(str(launcher)), '--health-listen-addr', '127.0.0.1:0'],
                       env=env, check=True)
    subprocess.run([str(binary), 'doctor', '--profile', 'private'], env=env, check=True)
    process = subprocess.Popen([str(binary), 'run', '--profile', 'private'], env=env)
    def stop(signum, frame):
        process.terminate()
    previous = {s: signal.signal(s, stop) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        return process.wait()
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def startup(runtime, apply=False):
    """Generate an opt-in user startup file; never changes unrelated services."""
    import plistlib
    python = runtime/'venv/bin/python'
    argv = [str(python), str(runtime/'scripts/private_runtime.py'), 'run', '--runtime', str(runtime)]
    label = 'com.connected-knowledge.private-capture'
    if sys.platform == 'darwin':
        path = Path.home()/'Library/LaunchAgents'/(label+'.plist')
        data = plistlib.dumps({'Label': label, 'ProgramArguments': argv, 'RunAtLoad': True,
                              'KeepAlive': {'SuccessfulExit': False}, 'ThrottleInterval': 30,
                              'StandardOutPath': str(runtime/'service.log'),
                              'StandardErrorPath': str(runtime/'service-error.log')})
        activate = ['launchctl', 'bootstrap', 'gui/'+str(os.getuid()), str(path)]
    elif sys.platform == 'linux':
        path = Path.home()/'.config/systemd/user/connected-knowledge-private.service'
        # systemd argument escaping is distinct from shell quoting.
        quote = lambda value: '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'
        data = ('[Unit]\nDescription=Connected Knowledge private connection\n'
                '[Service]\nExecStart=' + ' '.join(map(quote, argv)) + '\nRestart=on-failure\nRestartSec=30\n'
                '[Install]\nWantedBy=default.target\n').encode()
        activate = ['systemctl', '--user', 'enable', '--now', path.name]
    else:
        raise ValueError('Startup supported only on macOS/Linux')
    if path.exists() or path.is_symlink():
        raise ValueError('Startup file already exists; inspect it before changing it')
    if apply:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o600)
    import shlex
    return {'mode': 'apply' if apply else 'preview', 'file': str(path),
            'activation_argv': activate, 'activation_command': shlex.join(activate),
            'note': 'Save the key in the OS keyring first. Startup is after user login.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['run', 'status', 'store-key', 'startup'])
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    from private_setup import safe_path
    runtime = safe_path(str(args.runtime))
    if args.command == 'run':
        return run(runtime)
    if args.command == 'store-key':
        credential(runtime, store=True)
        print('Key stored in the OS keyring; no key was written to plugin configuration.')
    else:
        print(json.dumps(status(runtime) if args.command == 'status' else startup(runtime, args.apply), indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        # Never echo exception text that might contain keys, arguments, or source content.
        print(json.dumps({'status': 'error', 'error_type': type(exc).__name__,
                          'hint': 'Check runtime configuration, dependencies, OS keyring, and tunnel permissions.'}))
        sys.exit(1)
