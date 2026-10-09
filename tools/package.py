#!/usr/bin/env python3
"""Regenerate distribution copies from the single shared plugin source."""
from pathlib import Path
import hashlib,json,zipfile,shutil
from release_files import plugin_files
ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'distribution'; DIST.mkdir(exist_ok=True)
FILES=plugin_files()
text='# Instruction bundle — not native plugin installation\n\nFollow the relevant workflows with supplied material. Actual scripts require the full package and a capable execution environment. This file alone grants no vault, source-account or scheduler access.\n'
for f,name in FILES:
    if name.startswith('skills/') and f.suffix=='.md' and 'templates' not in f.parts:
        text+='\n\n---\n\n## Resource: '+name+'\n\n'+f.read_text()
(DIST/'instruction-bundle.md').write_text(text)
with zipfile.ZipFile(DIST/'claude-plugin.zip','w',zipfile.ZIP_DEFLATED) as z:
    for f,name in FILES: z.write(f,name)
files={name:hashlib.sha256(f.read_bytes()).hexdigest() for f,name in FILES}
shutil.copyfile(DIST/'claude-plugin.zip', DIST/'connected-knowledge.zip')
(DIST/'plugin-sha256.json').write_text(json.dumps(files,indent=2)+'\n')
print('Rebuilt portable/Claude ZIPs, instruction bundle, and plugin file hashes.')
