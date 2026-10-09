#!/usr/bin/env python3
"""Build a Gemini-specific extension without changing Claude/Codex hook files."""
from pathlib import Path
import zipfile
from release_files import plugin_files
ROOT = Path(__file__).resolve().parents[1]
GEMINI = ROOT/'integrations/gemini'
DIST = ROOT/'distribution'


def build(destination=DIST/'gemini-extension.zip'):
    Path(destination).parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as out:
        for path, name in plugin_files():
            if name.split('/')[0] in ('.claude-plugin', '.codex-plugin', '.plugin') or name in ('hooks/hooks.json', 'hooks/capture.py'):
                continue
            out.write(path, name)
        out.write(GEMINI/'hooks.json', 'hooks/hooks.json')
        # Gemini runs slash commands from TOML files; Claude and Codex never see them.
        for command in sorted((GEMINI/'commands').glob('*.toml')):
            out.write(command, 'commands/' + command.name)
    return destination


if __name__ == '__main__':
    build()
    print('Built experimental Gemini extension ZIP; no installation or activation.')
