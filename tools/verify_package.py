#!/usr/bin/env python3
"""Verify downloadable release bytes and execute extracted synthetic workflows."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT/'plugins/connected-knowledge'
with zipfile.ZipFile(ROOT/'distribution/claude-plugin.zip') as archive:
    names = archive.namelist()
    for name in names:
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Unsafe archive member')
        if archive.read(name) != (PLUGIN/name).read_bytes():
            raise ValueError('Package differs from source: ' + name)
    if any(Path(name).name in ('capture-config.json', 'runtime.json', '.env', 'health.url') for name in names):
        raise ValueError('Private runtime data in package')
    versions = {json.loads(archive.read(name))['version'] for name in
                ('plugin.json', '.claude-plugin/plugin.json', '.codex-plugin/plugin.json', 'gemini-extension.json')}
    if len(versions) != 1:
        raise ValueError('Manifest versions disagree')
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        plugin = root/'Extracted Plugin'
        archive.extractall(plugin)
        scripts = plugin/'skills/zettelkasten-obsidian/scripts'
        vault = root/'Fictional Vault'
        vault.mkdir()
        sys.path.insert(0, str(scripts))
        from private_setup import setup
        from private_capture import capture
        result = setup(root/'Runtime', vault, 'tunnel_00000000000000000000000000000000', 'fictional')
        assert result['mode'] == 'preview' and not (root/'Runtime').exists()
        cfg = {'enabled': True, 'account': 'fictional', 'spool': str(root/'spool'),
               'destination': str(vault/'Inbox/ChatGPT Captures'), 'vocabulary': 'existing',
               'template': str(plugin/'skills/zettelkasten-obsidian/assets/templates/capture-existing.md')}
        payload = {'source': 'chatgpt', 'conversation_id': 'fictional-chat', 'capture_id': 'selection',
                   'title': 'Fictional package trial', 'coverage': 'excerpt',
                   'messages': [{'id': 'm1', 'role': 'user', 'text': 'Fictional pears.'}]}
        assert capture(cfg, payload, True)['written'] == 1
        assert capture(cfg, payload, True)['written'] == 0
        note = next(Path(cfg['destination']).glob('*.md'))
        assert '> Fictional pears.' in note.read_text() and 'status: auto' in note.read_text()
        from vault_bridge import VaultBridge
        (vault/'Vault Guide.md').write_text('Keep the existing source archive. Use readable draft names.\n')
        cfg['vault_bridge'] = {'enabled': True, 'root': str(vault), 'guide': 'Vault Guide.md',
                               'templates': {}, 'note_folders': ['Inbox', 'Knowledge'],
                               'draft_folder': 'Knowledge'}
        bridge = VaultBridge(cfg)
        source = bridge.read_note(note.relative_to(vault).as_posix())
        draft = {'name': 'Fictional orchard.md',
                 'content': '# Fictional orchard\n\n[['+source['path']+']]\n',
                 'sources': [{'path': source['path'], 'sha256': source['sha256']}]}
        preview = bridge.preview([draft], 'Knowledge/Fictional orchard.md')
        assert preview['written'] == 0 and preview['can_apply'] is False
        assert not (vault/'Knowledge').exists()
        cfg['vault_bridge'].update(write_enabled=True, state_directory=str(root/'Bridge State'))
        bridge = VaultBridge(cfg)
        preview = bridge.preview([draft], 'Knowledge/Fictional orchard.md')
        saved = bridge.save([draft], 'Knowledge/Fictional orchard.md', preview['preview_id'])
        assert saved['status'] == 'saved' and saved['written'] == 1
        assert bridge.save([draft], 'Knowledge/Fictional orchard.md', preview['preview_id'])['status'] == 'unchanged'
        assert (vault/'Knowledge/Fictional orchard.md').read_text() == draft['content']
        note.write_text('Human edit')
        try:
            capture(cfg, payload, True)
        except ValueError:
            pass
        else:
            raise AssertionError('Human edit was not protected')
print(json.dumps({'version': versions.pop(), 'verified_entries': len(names),
                  'extracted_save_retry_edit_protection': 'pass', 'extracted_vault_preview': 'pass', 'extracted_linked_save_retry': 'pass'}))
