"""Install dependencies in an unpublished runtime generation, never globally."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import posixpath
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import venv

NODE_VERSION = '24.21.0'


def download(url, limit):
    request = urllib.request.Request(url, headers={'User-Agent': 'connected-knowledge-installer'})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Official download exceeds size limit')
    return data


def unpack_node(data, destination, prefix):
    """Extract only validated Node members; create internal symlinks last."""
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        members = archive.getmembers()
        if len(members) > 20000 or sum(m.size for m in members) > 512 * 1024 * 1024:
            raise ValueError('Node archive exceeds extraction limits')
        names = set()
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or not name.parts or name.parts[0] != prefix:
                raise ValueError('Unsafe Node archive path')
            if str(name) in names:
                raise ValueError('Duplicate Node archive member')
            names.add(str(name))
            if not (member.isdir() or member.isfile() or member.issym()):
                raise ValueError('Unsupported Node archive member')
            if member.issym():
                resolved = posixpath.normpath(posixpath.join(str(name.parent), member.linkname))
                if member.linkname.startswith('/') or not resolved.startswith(prefix + '/'):
                    raise ValueError('Node symlink escapes installation')
        for member in sorted(members, key=lambda m: m.issym()):
            relative = PurePosixPath(member.name).parts[1:]
            if not relative:
                continue
            target = destination.joinpath(*relative)
            if any(p.is_symlink() for p in (target, *target.parents)):
                raise ValueError('Node extraction redirected by a symlink')
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if member.isdir():
                target.mkdir(exist_ok=True, mode=0o700)
            elif member.issym():
                target.symlink_to(member.linkname)
            else:
                with target.open('xb') as stream:
                    shutil.copyfileobj(archive.extractfile(member), stream)
                target.chmod(0o700 if member.mode & 0o111 else 0o600)
        for member in members:
            if member.issym():
                target = destination.joinpath(*PurePosixPath(member.name).parts[1:])
                if not target.resolve().is_relative_to(destination.resolve()):
                    raise ValueError('Node symlink chain escapes installation')


def install_node(destination):
    operating = {'darwin': 'darwin', 'linux': 'linux'}.get(sys.platform)
    arch = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'x64', 'AMD64': 'x64'}.get(platform.machine())
    if not operating or not arch:
        raise ValueError('Managed Node supports macOS/Linux on arm64 or x64')
    prefix = f'node-v{NODE_VERSION}-{operating}-{arch}'
    name = prefix + '.tar.gz'
    base = f'https://nodejs.org/dist/v{NODE_VERSION}/'
    sums = download(base + 'SHASUMS256.txt', 1024 * 1024).decode()
    hashes = {line.split()[-1].lstrip('*'): line.split()[0] for line in sums.splitlines() if len(line.split()) == 2}
    data = download(base + name, 128 * 1024 * 1024)
    sha = hashlib.sha256(data).hexdigest()
    if sha != hashes.get(name):
        raise ValueError('Official Node checksum mismatch')
    destination.mkdir(mode=0o700)
    unpack_node(data, destination, prefix)
    return {'version': NODE_VERSION, 'archive_sha256': sha}


def build(generation, private, filesystem):
    minimum = (768 if filesystem else 384) * 1024 * 1024
    if shutil.disk_usage(generation).free < minimum:
        raise ValueError('Not enough free disk space. Free at least ' + str(minimum // (1024 * 1024))
                         + ' MiB, then rerun this setup. The previous runtime remains selected.')
    venv.EnvBuilder(with_pip=True).create(generation/'venv')
    python = generation/'venv/bin/python'
    subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '--no-cache-dir',
                    '-r', str(generation/'scripts/requirements-runtime.txt')], check=True)
    subprocess.run([str(python), '-m', 'pip', 'check'], check=True)
    receipt = {'python': subprocess.check_output([str(python), '--version'], text=True).strip()}
    if private:
        from private_setup import install_tunnel
        receipt['tunnel'] = install_tunnel(generation)
        subprocess.run([str(generation/'bin/tunnel-client'), '--version'], check=True)
    if filesystem:
        receipt['node'] = install_node(generation/'node')
        node = generation/'node/bin/node'
        npm = generation/'node/lib/node_modules/npm/bin/npm-cli.js'
        environment = {**os.environ, 'PATH': str(node.parent) + os.pathsep + os.environ.get('PATH', ''),
                       'npm_config_cache': str(generation/'npm-cache')}
        subprocess.run([str(node), str(npm), 'install', '--prefix', str(generation/'filesystem'),
                        '--ignore-scripts', '--no-audit', '--no-fund', '--save-exact',
                        '@modelcontextprotocol/server-filesystem@' + filesystem['version']],
                       env=environment, check=True)
        lock = generation/'filesystem/package-lock.json'
        receipt['filesystem_lock_sha256'] = hashlib.sha256(lock.read_bytes()).hexdigest()
        subprocess.run([str(node), '--version'], check=True)
    return receipt
