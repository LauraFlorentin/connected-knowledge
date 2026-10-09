#!/usr/bin/env python3
"""Verify downloadable release bytes and execute extracted synthetic workflows."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from release_files import doc_versions, is_private, plugin_files

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT/'plugins/connected-knowledge'
allowed = {name for _, name in plugin_files()}
with zipfile.ZipFile(ROOT/'distribution/gemini-extension.zip') as gemini:
    gemini_names = set(gemini.namelist())
    for command in ('ck-setup', 'ck-help', 'ck-add-session'):
        if 'commands/' + command + '.toml' not in gemini_names or 'skills/' + command + '/SKILL.md' not in gemini_names:
            raise ValueError('Gemini package lacks the ' + command + ' command')
    if 'hooks/capture.py' in gemini_names or any(is_private(n) for n in gemini_names):
        raise ValueError('Gemini package contains files it must not ship')
with zipfile.ZipFile(ROOT/'distribution/claude-plugin.zip') as archive:
    names = archive.namelist()
    for name in names:
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Unsafe archive member')
        if name not in allowed or is_private(name):
            raise ValueError('Package contains a file git does not accept or that looks private: ' + name)
        if archive.read(name) != (PLUGIN/name).read_bytes():
            raise ValueError('Package differs from source: ' + name)
    if any(Path(name).name in ('capture-config.json', 'runtime.json', '.env', 'health.url') for name in names):
        raise ValueError('Private runtime data in package')
    versions = {json.loads(archive.read(name))['version'] for name in
                ('plugin.json', '.claude-plugin/plugin.json', '.codex-plugin/plugin.json', 'gemini-extension.json')}
    if len(versions) != 1:
        raise ValueError('Manifest versions disagree')
    stated = {v for found in doc_versions().values() for v in found}
    if stated != versions or not all(doc_versions().values()):
        raise ValueError('Documentation states a different current version: ' + json.dumps(doc_versions()))
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        plugin = root/'Extracted Plugin'
        archive.extractall(plugin)
        scripts = plugin/'skills/zettelkasten-obsidian/scripts'
        vault = root/'Fictional Vault'
        vault.mkdir()
        sys.path.insert(0, str(scripts))
        from filesystem_setup import prepare as prepare_filesystem
        filesystem = prepare_filesystem('codex', [vault], root/'Filesystem Setup')
        assert filesystem['mode'] == 'preview' and not (root/'Filesystem Setup').exists()
        assert filesystem['activated'] is False
        filesystem = prepare_filesystem('codex', [vault], root/'Filesystem Setup', True)
        assert 'enabled = false' in (root/'Filesystem Setup/codex.fragment.toml').read_text()
        assert filesystem['activated'] is False and not list(vault.iterdir())
        from runtime_install import install
        managed = install({'runtime': str(root/'Managed Runtime'), 'filesystem': {
            'host': 'stdio', 'directories': [str(vault)]}})
        assert managed['mode'] == 'preview' and not (root/'Managed Runtime').exists()
        assert managed['private_connection'] is False and managed['starts_connection'] is False
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
        # 1.7.0: a new vault, one synthetic Claude Code session, the strict check.
        import ck_config, ck_sweep, starter_vault, vault_check
        new_vault = starter_vault.create(root/'New Vault', True, topics=['Fictional orchards'])
        transcripts = root/'home/.claude/projects/p'
        transcripts.mkdir(parents=True)
        project = root/'projects/orchard'
        project.mkdir(parents=True)
        rows = [{'type': 'user', 'uuid': 'u1', 'sessionId': 's1', 'cwd': str(project), 'timestamp': '2026-10-06T10:00:00Z',
                 'message': {'role': 'user', 'content': 'How many fictional pears? See [[x]] #tag'}},
                {'type': 'assistant', 'uuid': 'a1', 'sessionId': 's1', 'cwd': str(project), 'timestamp': '2026-10-06T10:01:00Z',
                 'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': '```dataviewjs\ndv.pages()\n```'}]}}]
        (transcripts/'s1.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        machine = ck_config.validate({'schema': 1, 'machine': 'test-mac', 'role': 'hub', 'vault': str(new_vault),
                                      'state': str(root/'state'), 'accounts': {'claude': 'fictional'},
                                      'capture': {'enabled': False, 'roots': [str(root/'projects')],
                                                  'transcript_roots': {'claude-code': [str(root/'home/.claude/projects')]}}})
        report = ck_sweep.capture_file(machine, 'claude-code', transcripts/'s1.jsonl',
                                       {'category': 'Work', 'topics': ['Fictional orchards']}, True)
        assert report['status'] == 'created', report
        assert ck_sweep.capture_file(machine, 'claude-code', transcripts/'s1.jsonl', None, True)['status'] == 'unchanged'
        checked = vault_check.check(new_vault, 'auto')
        assert (checked['errors'], checked['warnings']) == (0, 0), checked['findings']
        transcript = (new_vault/report['transcript']).read_text()
        assert '```text' in transcript and '\\[\\[x]]' in transcript and '\\#tag' in transcript
print(json.dumps({'version': versions.pop(), 'verified_entries': len(names), 'gemini_entries': len(gemini_names),
                  'extracted_save_retry_edit_protection': 'pass', 'extracted_vault_preview': 'pass',
                  'extracted_linked_save_retry': 'pass', 'extracted_unified_installer_preview': 'pass', 'extracted_filesystem_setup': 'pass',
                  'extracted_new_vault_capture_strict_check': 'pass', 'docs_version': 'pass', 'private_data_guard': 'pass'}))
