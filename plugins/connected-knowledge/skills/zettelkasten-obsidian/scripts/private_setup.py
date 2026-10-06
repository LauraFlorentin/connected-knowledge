#!/usr/bin/env python3
"""Prepare a permanent single-owner capture runtime. Preview by default."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import venv
import subprocess

SCRIPTS = Path(__file__).resolve().parent


def install_tunnel(runtime):
    """Download a verified official release, never execute unverified archive members."""
    import hashlib
    import io
    import platform
    import urllib.request
    import zipfile
    machine = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'amd64'}.get(platform.machine())
    operating = {'darwin': 'darwin', 'linux': 'linux'}.get(sys.platform)
    if not machine or not operating:
        raise ValueError('Unsupported tunnel-client platform')
    def get(url, limit):
        request = urllib.request.Request(url, headers={'User-Agent': 'connected-knowledge-setup'})
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read(limit + 1)
        if len(content) > limit:
            raise ValueError('Official download exceeds expected size')
        return content
    release = json.loads(get('https://api.github.com/repos/openai/tunnel-client/releases/latest', 1024*1024))
    assets = {asset['name']: asset['browser_download_url'] for asset in release['assets']}
    name = 'tunnel-client-' + release['tag_name'] + '-' + operating + '-' + machine + '.zip'
    checksum_name = 'SHA256SUMS.txt' if 'SHA256SUMS.txt' in assets else 'SHA256SUMS'
    if name not in assets or checksum_name not in assets:
        raise ValueError('Official release format changed; use the vendor download instructions')
    for url in (assets[name], assets[checksum_name]):
        if not url.startswith('https://github.com/openai/tunnel-client/releases/download/'):
            raise ValueError('Unexpected official release URL')
    sums = get(assets[checksum_name], 1024*1024).decode()
    hashes = {line.split()[-1].lstrip('*'): line.split()[0] for line in sums.splitlines() if len(line.split()) == 2}
    archive = get(assets[name], 128*1024*1024)
    if hashlib.sha256(archive).hexdigest() != hashes.get(name):
        raise ValueError('Official download checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        entries = [entry for entry in bundle.infolist() if Path(entry.filename).name == 'tunnel-client' and not entry.is_dir()]
        if len(entries) != 1 or entries[0].file_size > 128*1024*1024:
            raise ValueError('Unexpected official binary archive')
        content = bundle.read(entries[0])
    target = safe_path(str(runtime))/'bin/tunnel-client'
    if target.exists() or target.is_symlink():
        raise ValueError('Tunnel binary already installed; do not overwrite an active runtime')
    target.parent.mkdir(mode=0o700, exist_ok=True)
    target.write_bytes(content)
    target.chmod(0o700)
    return {'version': release['tag_name'], 'archive_sha256': hashlib.sha256(archive).hexdigest()}


def wizard():
    # Keep the earlier public entry point, with one guided installation flow.
    from install import wizard as guided_install
    result = guided_install()
    print(json.dumps(result, indent=2))
    if result.get('host_connection', {}).get('status') == 'pending':
        raise SystemExit(3)


def safe_path(value):
    if any(character in str(value) for character in ('\n', '\r', '\x00')):
        raise ValueError('Paths must not contain control characters')
    path = Path(value).expanduser()
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Choose absolute paths without symlinks')
    return path.resolve()


def setup(runtime, vault, tunnel, account, vocabulary='existing', template=None, apply=False):
    from private_capture import private_path, capture
    runtime, vault = private_path(str(runtime)), safe_path(str(vault))
    if not vault.is_dir():
        raise ValueError('Choose your existing vault; setup never creates a replacement')
    if runtime.is_relative_to(vault) or vault.is_relative_to(runtime):
        raise ValueError('Keep runtime storage separate from the vault')
    if not re.fullmatch(r'tunnel_[a-z0-9]{32}', tunnel):
        raise ValueError('Enter the tunnel ID from your own Platform account')
    if not account.strip() or len(account) > 128:
        raise ValueError('Choose a short non-secret account label')
    if vocabulary not in ('existing', 'default'):
        raise ValueError('Choose the property vocabulary from your vault guide')
    if template:
        template = safe_path(str(template))
        if not template.is_file() or not template.is_relative_to(vault):
            raise ValueError('Choose an existing Markdown template inside this vault')
        if template.suffix != '.md':
            raise ValueError('Choose a Markdown template')
    else:
        template = SCRIPTS.parent/'assets/templates'/('capture-' + vocabulary + '.md')
    if runtime.exists() and any(runtime.iterdir()):
        raise ValueError('Runtime destination must be empty; do not overwrite an existing installation')
    cfg = {'enabled': True, 'account': account, 'spool': str(runtime/'spool'),
           'destination': str(vault/'Inbox/ChatGPT Captures'), 'vocabulary': vocabulary,
           'template': str(template), 'readable_names': True}
    test = {'source': 'manual', 'conversation_id': 'setup-preview', 'capture_id': 'preview',
            'title': 'Setup preview', 'coverage': 'excerpt',
            'messages': [{'id': 'preview', 'role': 'user', 'text': 'Preview only; no note is saved.'}]}
    capture(cfg, test)  # Validate template without writing any source material.
    destination = Path(cfg['destination'])
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Choose a fresh capture folder; existing archives need a deliberate migration')
    result = {'mode': 'apply' if apply else 'preview', 'runtime': str(runtime),
              'destination': cfg['destination'], 'template': str(template),
              'tunnel_id': tunnel, 'next': 'install dependencies, add official tunnel-client, then connect'}
    if not apply:
        return result
    runtime.mkdir(parents=True, mode=0o700)
    (runtime/'scripts').mkdir(mode=0o700)
    for path in SCRIPTS.iterdir():
        if path.is_file() and (path.suffix == '.py' or path.name.startswith('requirements')):
            shutil.copy2(path, runtime/'scripts'/path.name)
    if not template.is_relative_to(vault):
        shutil.copy2(template, runtime/'capture-template.md')
        cfg['template'] = str(runtime/'capture-template.md')
    result['template'] = cfg['template']
    for name, data in [('capture-config.json', cfg), ('runtime.json', {'version': 1, 'tunnel_id': tunnel})]:
        target = runtime/name
        target.write_text(json.dumps(data, indent=2) + '\n')
        target.chmod(0o600)
    venv.EnvBuilder(with_pip=True).create(runtime/'venv')
    result['python'] = str(runtime/'venv/bin/python')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wizard', action='store_true')
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--vault', type=Path)
    parser.add_argument('--tunnel-id')
    parser.add_argument('--account')
    parser.add_argument('--vocabulary', choices=['existing', 'default'], default='existing')
    parser.add_argument('--template', type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--install-dependencies', action='store_true')
    args = parser.parse_args()
    if sys.platform not in ('darwin', 'linux') or sys.version_info < (3, 10):
        parser.error('This release requires macOS/Linux and Python 3.10 or later')
    if args.wizard:
        wizard()
        return
    if not all((args.runtime, args.vault, args.tunnel_id, args.account)):
        parser.error('Use --wizard or supply --runtime, --vault, --tunnel-id, and --account')
    if args.install_dependencies and not args.apply:
        parser.error('--install-dependencies requires --apply')
    result = setup(args.runtime, args.vault, args.tunnel_id, args.account, args.vocabulary, args.template, args.apply)
    if args.install_dependencies:
        subprocess.run([result['python'], '-m', 'pip', 'install', '-r',
                        str(args.runtime/'scripts/requirements-runtime.txt')], check=True)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
