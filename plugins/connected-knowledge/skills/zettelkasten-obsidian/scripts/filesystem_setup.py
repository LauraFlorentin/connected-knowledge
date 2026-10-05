#!/usr/bin/env python3
"""Prepare optional Filesystem MCP settings; never install or activate a connection."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys

TESTED_VERSION = '2026.8.31'
PACKAGE = '@modelcontextprotocol/server-filesystem'
HOSTS = ('codex', 'claude-desktop', 'stdio')
DEFAULT_NAME = 'connected-knowledge-filesystem'
PLUGIN = Path(__file__).resolve().parents[3]


def absolute_path(value):
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise ValueError('Select an absolute path')
    if any(ord(c) < 32 or ord(c) == 127 for c in str(value)):
        raise ValueError('Paths cannot contain control characters')
    path = Path(value).expanduser()
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Use an absolute path without parent traversal')
    return path


def selected_directories(values):
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= 16:
        raise ValueError('Select between one and sixteen existing folders')
    selected = []
    home = Path.home().resolve()
    for value in values:
        path = absolute_path(value)
        if not path.is_dir():
            raise ValueError('Selected folder is unavailable: ' + str(path))
        # Display and launch with canonical paths so aliases cannot hide scope.
        path = path.resolve(strict=True)
        if path == home or home.is_relative_to(path) or path == Path(path.anchor):
            raise ValueError('Select specific folders, not a home directory or its ancestors')
        if path in selected:
            continue
        if any(path.is_relative_to(p) or p.is_relative_to(path) for p in selected):
            raise ValueError('Selected folders overlap; choose the intended scope explicitly')
        selected.append(path)
    return selected


def output_path(value, directories):
    path = absolute_path(value)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('Symlink output paths are unsupported; use the real destination')
    path = path.resolve()
    if path.exists():
        raise ValueError('Setup destination already exists; preserve it and select a new folder')
    if not path.parent.is_dir():
        raise ValueError('Setup destination needs an existing parent directory')
    protected = [*directories, PLUGIN]
    protected += [p for p in PLUGIN.parents
                  if (p/'.git').exists() or (p/'tools/package.py').is_file()]
    if any(path == p or path.is_relative_to(p) or p.is_relative_to(path) for p in protected):
        raise ValueError('Keep private setup outside selected folders and plugin repositories')
    return path


def connection_plan(host, directories, version=TESTED_VERSION, name=DEFAULT_NAME, npx=None):
    if os.name == 'nt':
        raise ValueError('This setup helper supports macOS/Linux; see upstream Windows instructions')
    if host not in HOSTS:
        raise ValueError('Choose codex, claude-desktop or stdio')
    if not isinstance(version, str) or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise ValueError('Use an exact stable package version, for example ' + TESTED_VERSION)
    if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', name):
        raise ValueError('Connection name must use lowercase letters, numbers, underscores or hyphens')
    folders = selected_directories(directories)
    command = shutil.which('npx') or 'npx'
    if npx is not None:
        launcher = absolute_path(npx)
        if not launcher.is_file() or not os.access(launcher, os.X_OK):
            raise ValueError('Select an executable npx path')
        command = str(launcher)
    connection = {'command': command,
                  'args': ['-y', '--ignore-scripts', PACKAGE + '@' + version, *map(str, folders)]}
    if host == 'codex':
        filename = 'codex.fragment.toml'
        config = ('[mcp_servers.' + name + ']\ncommand = ' + json.dumps(command, ensure_ascii=False)
                  + '\nargs = ' + json.dumps(connection['args'], ensure_ascii=False)
                  + '\nstartup_timeout_sec = 60\nenabled = false\n')
    elif host == 'claude-desktop':
        filename = 'claude-desktop.fragment.json'
        config = json.dumps({'mcpServers': {name: connection}}, indent=2, ensure_ascii=False) + '\n'
    else:
        filename = 'stdio.fragment.json'
        config = json.dumps(connection, indent=2, ensure_ascii=False) + '\n'
    return {'mode': 'preview', 'host': host, 'name': name, 'package': PACKAGE,
            'package_version': version, 'tested_version': version == TESTED_VERSION,
            'directories': list(map(str, folders)), 'connection': connection,
            'config_filename': filename, 'config_fragment': config,
            'access': 'read/write; client Roots may replace these folders',
            'activated': False, 'scope_verified': False,
            'next_step': 'Reuse an existing connection when its effective scope already matches. '
                         'Otherwise review and add the selected settings in your host, then check '
                         'list_allowed_directories before reading or writing files.'}


def setup_notes(plan):
    instructions = {
        'codex': 'Review the named table in codex.fragment.toml against your existing '
                 '~/.codex/config.toml. Merge only this table; preserve other settings and '
                 'reuse an existing suitable connection. The fragment is disabled. When '
                 'activation is authorized, set enabled = true and restart the host.',
        'claude-desktop': 'Review claude-desktop.fragment.json against your existing '
                          'claude_desktop_config.json. Merge only the named mcpServers entry; '
                          'preserve other settings and reuse an existing suitable connection. '
                          'Adding this entry and restarting Claude Desktop activates it.',
        'stdio': 'stdio.fragment.json supplies a command and separate arguments for a local '
                 'stdio-capable host. It is not a complete host configuration. Use the host\'s '
                 'current setup instructions and preserve any existing connections.'}
    return ('# Optional Filesystem connection\n\n'
            'These files are a private setup plan. No server has been installed, started or '
            'connected. No vault content or host configuration was changed.\n\n'
            + instructions[plan['host']] + '\n\n'
            'The machine running the host needs Node.js and npx available in its environment. '
            'The first authorized launch downloads the pinned npm package and its dependencies; '
            'installation scripts are disabled. The top-level package is pinned; transitive '
            'dependency resolution can change. This is not a bundled or offline runtime.\n\n'
            'Requested folders (canonical paths):\n\n```json\n'
            + json.dumps(plan['directories'], indent=2, ensure_ascii=False) + '\n```\n\n'
            'This connection has write tools. Client-provided MCP Roots replace the startup '
            'folders. Inspect list_allowed_directories after connecting and after Roots change. '
            'If scope differs from the user\'s selection, correct it before accessing files. '
            'Validate one harmless selected file and read back any authorized test write.\n\n'
            'General file tools do not enforce Connected Knowledge\'s original-source, '
            'duplicate, identity or revision checks. Follow the existing vault guide and '
            'templates, preview changes, preserve sources and human edits, and verify the '
            'saved files. Existing task authorization applies.\n\n'
            'Local settings do not establish ChatGPT web/mobile access. This setup does not '
            'create a tunnel or reuse capture credentials. To disconnect, disable or remove '
            'only this named host entry and restart; keep your notes and unrelated settings.\n')


def prepare(host, directories, output=None, apply=False, **options):
    plan = connection_plan(host, directories, **options)
    destination = output_path(output, list(map(Path, plan['directories']))) if output else None
    if apply and destination is None:
        raise ValueError('--apply requires a fresh private --output folder')
    if destination:
        plan['output'] = str(destination)
    if not apply:
        return plan
    # Exclusive creation preserves earlier and interrupted setups. No live config is edited.
    destination.mkdir(mode=0o700)
    plan['mode'] = 'prepared'
    files = {'setup.json': json.dumps(plan, indent=2, ensure_ascii=False) + '\n',
             plan['config_filename']: plan['config_fragment'], 'SETUP.md': setup_notes(plan)}
    for name, content in files.items():
        fd = os.open(destination/name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(content)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wizard', action='store_true')
    parser.add_argument('--host', choices=HOSTS)
    parser.add_argument('--directory', action='append', help='Existing folder; repeat for separate scopes')
    parser.add_argument('--version', default=TESTED_VERSION, help='Exact stable upstream package version')
    parser.add_argument('--name', default=DEFAULT_NAME)
    parser.add_argument('--npx', help='Absolute npx executable if the host cannot find it')
    parser.add_argument('--output', help='Fresh private folder outside the selected folders and plugin')
    parser.add_argument('--apply', action='store_true', help='Save setup files only; never activate a connection')
    args = parser.parse_args()
    try:
        if args.wizard:
            print('Optional Filesystem MCP setup. Selected folders allow reading and writing.')
            print('Reuse a suitable existing connection. This helper only prepares settings.')
            args.host = args.host or input('Local host: codex, claude-desktop, or stdio [stdio]: ').strip() or 'stdio'
            if not args.directory:
                args.directory = []
                while True:
                    value = input('Existing absolute folder path [blank when done]: ').strip()
                    if not value:
                        break
                    args.directory.append(value)
        result = prepare(args.host, args.directory, args.output, args.apply,
                         version=args.version, name=args.name, npx=args.npx)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (ValueError, OSError, EOFError) as exc:
        print('Filesystem setup: ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
