#!/usr/bin/env python3
"""Choose the plugin files a release may contain.

Only files git would accept (tracked, or untracked but not ignored) are packaged,
so anything listed in .gitignore can never reach a release ZIP. Private-looking
names and symlinks stop the build instead of being skipped silently.
"""
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT/'plugins/connected-knowledge'

# Never shipped, even if committed by mistake: account exports, transcripts,
# private runtime state and credentials.
PRIVATE_PATTERNS = (
    'private-data', '.env', '.env.*', '*.jsonl',
    'conversations.json', 'capture-config.json', 'runtime.json', 'health.url',
    'config.local.json', '*.pem', '*.key', 'id_rsa*', 'id_ed25519*',
)


# Places that state the current release; each must equal the manifest version.
VERSION_MARKERS = {
    'README.md': r'Version \*\*(\d+\.\d+\.\d+)\*\*',
    'START-HERE.md': r'\A# Connected Knowledge — (\d+\.\d+\.\d+)',
    'docs/INSTALL.md': r'Package documentation updated \S+ for (\d+\.\d+\.\d+)|^## Updating to (\d+\.\d+\.\d+)',
    'docs/RELEASE-NOTES.md': r'\A# Release notes\n\n## (\d+\.\d+\.\d+)',
    'docs/VALIDATION.md': r'\A# Validation and limits[^\n]*\n\n## (\d+\.\d+\.\d+)',
}


def manifest_version():
    import json
    return json.loads((PLUGIN/'.claude-plugin/plugin.json').read_text())['version']


def doc_versions():
    """Return {file: [versions stated as current]}; an empty list means the marker is missing."""
    import re
    found = {}
    for name, pattern in VERSION_MARKERS.items():
        text = (ROOT/name).read_text(encoding='utf-8')
        found[name] = [v for match in re.finditer(pattern, text, re.M) for v in match.groups() if v]
    return found


def is_private(relative):
    return any(fnmatch(part, pattern) for part in PurePosixPath(relative).parts
               for pattern in PRIVATE_PATTERNS)


def plugin_files():
    """Return (path, plugin-relative name) pairs, sorted by name."""
    listing = subprocess.run(
        ['git', '-C', str(ROOT), 'ls-files', '-z', '--cached', '--others', '--exclude-standard',
         '--', 'plugins/connected-knowledge'], capture_output=True, check=True).stdout.decode()
    files = []
    for name in sorted(set(listing.split('\0')) - {''}):
        path = ROOT/name
        if path.is_symlink():
            raise SystemExit('Refusing to package a symlink: ' + name)
        if not path.is_file():
            continue  # deleted in the working tree but still in the index
        relative = path.relative_to(PLUGIN).as_posix()
        if is_private(relative):
            raise SystemExit('Refusing to package a private-looking file: ' + relative)
        files.append((path, relative))
    return files
