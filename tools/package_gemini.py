#!/usr/bin/env python3
"""Build a Gemini-specific extension without changing Claude/Codex hook files."""
from pathlib import Path
import zipfile
ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT/'plugins/connected-knowledge'
DIST = ROOT/'distribution'
DIST.mkdir(exist_ok=True)
with zipfile.ZipFile(DIST/'gemini-extension.zip', 'w', zipfile.ZIP_DEFLATED) as out:
    for path in sorted(PLUGIN.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        name = path.relative_to(PLUGIN)
        if name.parts[0] in ('.claude-plugin', '.codex-plugin', '.plugin') or str(name) in ('hooks/hooks.json', 'hooks/capture.py'):
            continue
        out.write(path, name)
    out.write(ROOT/'integrations/gemini/hooks.json', 'hooks/hooks.json')
print('Built development Gemini extension ZIP; no installation or activation.')
