#!/usr/bin/env python3
"""Regenerate distribution copies from the single shared plugin source."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
PLUGIN=ROOT/'plugins/connected-knowledge'
DIST=ROOT/'distribution'; DIST.mkdir(exist_ok=True)
text='# Instruction bundle — not native plugin installation\n\nFollow the relevant workflows with supplied material. Actual scripts require the full package and a capable execution environment. This file alone grants no vault, source-account or scheduler access.\n'
for f in sorted((PLUGIN/'skills').rglob('*.md')):
    if 'templates' not in f.parts:
        text+='\n\n---\n\n## Resource: '+str(f.relative_to(PLUGIN))+'\n\n'+f.read_text()
(DIST/'instruction-bundle.md').write_text(text)
with zipfile.ZipFile(DIST/'claude-plugin.zip','w',zipfile.ZIP_DEFLATED) as z:
    for f in sorted(PLUGIN.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc': z.write(f,f.relative_to(PLUGIN))
files={str(f.relative_to(PLUGIN)):hashlib.sha256(f.read_bytes()).hexdigest() for f in PLUGIN.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc'}
(DIST/'plugin-sha256.json').write_text(json.dumps(files,indent=2)+'\n')
print('Rebuilt Claude ZIP, instruction bundle, and plugin file hashes.')
