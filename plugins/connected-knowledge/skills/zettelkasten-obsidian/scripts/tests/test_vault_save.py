import asyncio
import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_vault_bridge import fixture, proposal, snapshot
from private_capture import capture
from vault_bridge import BridgeError, VaultBridge
from vault_save import PrivateStore, write_note
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class VaultSaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.vault, self.config = fixture(self.root)
        self.config['vault_bridge'].update(write_enabled=True, state_directory=str(self.root / 'state'))
        self.bridge = VaultBridge(self.config)

    def save(self, drafts, entry='Knowledge/Orchard.md'):
        preview = self.bridge.preview(drafts, entry)
        return self.bridge.save(drafts, entry, preview['preview_id']), preview

    def test_exact_save_readback_and_repeat_receipt(self):
        drafts = proposal(self.bridge)
        result, preview = self.save(drafts)
        self.assertTrue(preview['can_apply'])
        self.assertEqual(result['status'], 'saved')
        self.assertEqual(result['written'], 1)
        self.assertEqual((self.vault / 'Knowledge/Orchard.md').read_text(), drafts[0]['content'])
        retry = self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        self.assertEqual(retry['status'], 'unchanged')
        self.assertEqual(retry['written'], 0)
        self.assertEqual(result['notes'], retry['notes'])
        self.assertFalse(list(self.vault.rglob('.ck-*')))
        self.assertEqual(len(list((self.vault / 'Knowledge').glob('*.md'))), 1)

    def test_preview_is_still_read_only_even_with_writes_enabled(self):
        before = snapshot(self.root)
        self.bridge.preview(proposal(self.bridge), 'Knowledge/Orchard.md')
        self.assertEqual(before, snapshot(self.root))
        self.assertFalse((self.root / 'state').exists())

    def test_preview_changes_block_all_note_writes(self):
        for change in ('draft', 'source', 'guide', 'target', 'scope'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                vault, cfg = fixture(root)
                cfg['vault_bridge'].update(write_enabled=True, state_directory=str(root / 'state'))
                bridge = VaultBridge(cfg)
                drafts = proposal(bridge)
                preview = bridge.preview(drafts, 'Knowledge/Orchard.md')
                if change == 'draft':
                    drafts[0]['content'] += '\nUnreviewed addition'
                elif change == 'source':
                    (vault / 'Sources/Selected chat.md').write_text('Changed source')
                elif change == 'guide':
                    (vault / 'Vault Guide.md').write_text('Changed conventions')
                elif change == 'target':
                    (vault / 'Knowledge').mkdir()
                    (vault / 'Knowledge/Orchard.md').write_text('Human note at the proposed name')
                else:
                    cfg['vault_bridge']['identity_fields'] = ['note_id']
                    bridge = VaultBridge(cfg)
                before = snapshot(vault)
                with self.assertRaises(BridgeError):
                    bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
                self.assertEqual(before, snapshot(vault))

    def test_updates_preserve_record_identity_and_original_bytes(self):
        drafts = proposal(self.bridge)
        drafts[0]['content'] = '---\nid: stable-idea\ntype: idea\n---\n' + drafts[0]['content']
        first, _ = self.save(drafts)
        before = (self.vault / 'Knowledge/Orchard.md').read_bytes()
        drafts[0]['expected_sha256'] = self.bridge.read_note('Knowledge/Orchard.md')['sha256']
        drafts[0]['content'] += '\nAn explicitly proposed revision.\n'
        second, preview = self.save(drafts)
        self.assertEqual(first['notes'][0]['record_id'], second['notes'][0]['record_id'])
        journal = json.loads((self.root / 'state' / (preview['preview_id'] + '.json')).read_text())
        self.assertEqual(base64.b64decode(journal['targets'][0]['before_bytes']), before)
        self.assertIn('id: stable-idea', (self.vault / 'Knowledge/Orchard.md').read_text())

    def test_identity_changes_and_duplicates_are_rejected(self):
        drafts = proposal(self.bridge)
        drafts[0]['content'] = '---\nid: stable-idea\n---\n' + drafts[0]['content']
        self.save(drafts)
        drafts[0]['expected_sha256'] = self.bridge.read_note('Knowledge/Orchard.md')['sha256']
        drafts[0]['content'] = drafts[0]['content'].replace('id: stable-idea', 'id: new-identity')
        with self.assertRaisesRegex(BridgeError, 'note_identity_changed'):
            self.save(drafts)
        duplicate = proposal(self.bridge)
        duplicate[0]['name'] = 'Duplicate.md'
        duplicate[0]['content'] = '---\nid: stable-idea\n---\n' + duplicate[0]['content'] + '\nDifferent text'
        with self.assertRaisesRegex(BridgeError, 'duplicate_note_identity'):
            self.save(duplicate, 'Knowledge/Duplicate.md')

    def test_repeat_does_not_overwrite_human_edits(self):
        drafts = proposal(self.bridge)
        _, preview = self.save(drafts)
        target = self.vault / 'Knowledge/Orchard.md'
        target.write_text('Human changes after save')
        with self.assertRaisesRegex(BridgeError, 'saved_note_changed'):
            self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        self.assertEqual(target.read_text(), 'Human changes after save')

    def test_interrupted_batch_resumes_without_duplicate_writes(self):
        drafts = proposal(self.bridge)
        drafts[0]['content'] += '\n[[Knowledge/Pollination.md]]\n'
        second = deepcopy(drafts[0])
        second['name'] = 'Pollination.md'
        second['content'] = second['content'].replace('# Orchard', '# Pollination')
        drafts.append(second)
        preview = self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        calls = 0
        def interrupted(bridge, item):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('Synthetic storage failure')
            write_note(bridge, item)
        with patch('vault_save.write_note', side_effect=interrupted):
            first = self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        self.assertEqual(first['status'], 'incomplete')
        self.assertEqual(first['written'], 1)
        self.assertEqual([n['state'] for n in first['notes']], ['saved', 'pending_or_changed'])
        resumed = self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        self.assertEqual(resumed['status'], 'saved')
        self.assertEqual(resumed['written'], 1)
        self.assertEqual(first['notes'][0]['record_id'], resumed['notes'][0]['record_id'])
        self.assertEqual(self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])['written'], 0)

    def test_crash_after_file_write_before_ledger_recovers(self):
        drafts = proposal(self.bridge)
        preview = self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        def crashed(bridge, item):
            write_note(bridge, item)
            raise SystemExit('Simulated process death')
        with patch('vault_save.write_note', side_effect=crashed):
            with self.assertRaises(SystemExit):
                self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        result = self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        self.assertEqual(result['status'], 'unchanged')
        self.assertEqual(result['written'], 0)
        self.assertEqual(len(json.loads((self.root / 'state/notes.json').read_text())['notes']), 1)

    def test_process_death_after_atomic_link_is_recoverable(self):
        drafts = proposal(self.bridge)
        preview = self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        payload = self.root / 'request.json'
        payload.write_text(json.dumps({'config': self.config, 'notes': drafts, 'preview': preview['preview_id']}))
        scripts = Path(__file__).resolve().parents[1]
        code = '''import json, os, sys
sys.path.insert(0, sys.argv[1])
from vault_bridge import VaultBridge
import vault_save
request = json.load(open(sys.argv[2]))
real_link = vault_save.os.link
def crash(*args, **kwargs):
    real_link(*args, **kwargs)
    os._exit(73)
vault_save.os.link = crash
VaultBridge(request['config']).save(request['notes'], 'Knowledge/Orchard.md', request['preview'])
'''
        result = subprocess.run([sys.executable, '-c', code, str(scripts), str(payload)], capture_output=True)
        self.assertEqual(result.returncode, 73, result.stderr)
        self.assertEqual((self.vault / 'Knowledge/Orchard.md').stat().st_nlink, 2)
        resumed = self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        self.assertEqual(resumed['status'], 'unchanged')
        self.assertEqual((self.vault / 'Knowledge/Orchard.md').stat().st_nlink, 1)
        self.assertFalse(list(self.vault.rglob('.ck-*')))

    def test_recovery_protects_new_human_edit(self):
        drafts = proposal(self.bridge)
        preview = self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        def crashed(bridge, item):
            write_note(bridge, item)
            raise SystemExit()
        with patch('vault_save.write_note', side_effect=crashed):
            with self.assertRaises(SystemExit):
                self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        target = self.vault / 'Knowledge/Orchard.md'
        target.write_text('Human edit during interruption')
        resumed = self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        self.assertEqual(resumed['status'], 'incomplete')
        self.assertEqual(resumed['code'], 'target_changed')
        self.assertEqual(target.read_text(), 'Human edit during interruption')

    def test_captured_original_integrity_and_coverage(self):
        payload = {'source': 'chatgpt', 'conversation_id': 'fictional', 'capture_id': 'selection',
                   'title': 'Pears', 'coverage': 'summary',
                   'messages': [{'id': 'm1', 'role': 'assistant', 'text': 'A fictional summary.'}]}
        capture(self.config, payload, True)
        note = next(Path(self.config['destination']).glob('*.md'))
        source = self.bridge.read_note(note.relative_to(self.vault).as_posix())
        drafts = [{'name': 'Orchard.md', 'content': '# Orchard\n[[' + source['path'] + ']]\n',
                   'sources': [{'path': source['path'], 'sha256': source['sha256']}]}]
        preview = self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        self.assertEqual(preview['sources'][0]['coverage_label'], 'summary')
        self.assertEqual(preview['sources'][0]['original_verification'], 'verified')
        raw = next((Path(self.config['destination']) / 'originals').glob('*.json'))
        before = raw.read_bytes()
        result = self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        self.assertEqual(result['status'], 'saved')
        self.assertEqual(before, raw.read_bytes())
        raw.write_text('Corrupted preserved original')
        with self.assertRaisesRegex(BridgeError, 'capture_original_changed'):
            self.bridge.preview(drafts, 'Knowledge/Orchard.md')

    def test_disabled_saving_and_private_state_boundaries(self):
        drafts = proposal(self.bridge)
        preview = self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        cfg = deepcopy(self.config)
        cfg['vault_bridge']['write_enabled'] = False
        with self.assertRaisesRegex(BridgeError, 'writes_disabled'):
            VaultBridge(cfg).save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        cfg['vault_bridge']['write_enabled'] = True
        cfg['vault_bridge']['state_directory'] = str(self.vault / 'State')
        with self.assertRaisesRegex(BridgeError, 'invalid_save_state'):
            VaultBridge(cfg).save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        (self.root / 'state').mkdir()
        (self.root / 'state/personal.txt').write_text('Occupied storage')
        with self.assertRaisesRegex(BridgeError, 'save_state_not_empty'):
            self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        self.assertEqual((self.root / 'state/personal.txt').read_text(), 'Occupied storage')
        self.assertEqual({p.name for p in (self.root / 'state').iterdir()}, {'personal.txt'})

    def test_output_directory_symlink_swap_cannot_write_outside_vault(self):
        drafts = proposal(self.bridge)
        preview = self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        outside = self.root / 'Outside'
        outside.mkdir()
        def redirected(bridge, item):
            (self.vault / 'Knowledge').symlink_to(outside, target_is_directory=True)
            write_note(bridge, item)
        with patch('vault_save.write_note', side_effect=redirected):
            result = self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(list(outside.iterdir()), [])

    def test_new_target_created_during_write_is_preserved(self):
        drafts = proposal(self.bridge)
        preview = self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        target = self.vault / 'Knowledge/Orchard.md'
        original = os.link
        def raced(*args, **kwargs):
            target.write_text('Concurrent human note')
            return original(*args, **kwargs)
        with patch('vault_save.os.link', side_effect=raced):
            result = self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['written'], 0)
        self.assertEqual(target.read_text(), 'Concurrent human note')

    def test_configured_custom_identity_and_file_mode_are_preserved(self):
        self.config['vault_bridge']['identity_fields'] = ['idea_id']
        self.bridge = VaultBridge(self.config)
        drafts = proposal(self.bridge)
        drafts[0]['content'] = '---\nidea_id: idea-42\n---\n' + drafts[0]['content']
        self.save(drafts)
        target = self.vault / 'Knowledge/Orchard.md'
        target.chmod(0o640)
        drafts[0]['expected_sha256'] = self.bridge.read_note('Knowledge/Orchard.md')['sha256']
        drafts[0]['content'] += '\nAn approved addition.\n'
        self.save(drafts)
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)
        drafts[0]['expected_sha256'] = self.bridge.read_note('Knowledge/Orchard.md')['sha256']
        drafts[0]['content'] = drafts[0]['content'].replace('idea_id: idea-42', 'idea_id: other')
        with self.assertRaisesRegex(BridgeError, 'note_identity_changed'):
            self.save(drafts)

    def test_completed_journal_tampering_is_rejected(self):
        drafts = proposal(self.bridge)
        _, preview = self.save(drafts)
        journal_path = self.root / 'state' / (preview['preview_id'] + '.json')
        journal = json.loads(journal_path.read_text())
        journal['report']['snapshots']['Vault Guide.md'] = '0' * 64
        journal_path.write_text(json.dumps(journal))
        with self.assertRaisesRegex(BridgeError, 'invalid_save_state'):
            self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])

    def test_source_change_mid_batch_reports_saved_and_pending_notes(self):
        drafts = proposal(self.bridge)
        second = deepcopy(drafts[0])
        second['name'] = 'Second.md'
        second['content'] = second['content'].replace('# Orchard', '# Second')
        drafts[0]['content'] += '\n[[Knowledge/Second.md]]\n'
        drafts.append(second)
        preview = self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        def changed(bridge, item):
            write_note(bridge, item)
            (self.vault / 'Sources/Selected chat.md').write_text('Source revised during save')
        with patch('vault_save.write_note', side_effect=changed):
            result = self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['code'], 'source_or_convention_changed')
        self.assertEqual(result['written'], 1)
        self.assertEqual([n['state'] for n in result['notes']], ['saved', 'pending_or_changed'])
        self.assertFalse((self.vault / 'Knowledge/Second.md').exists())

    def test_deleted_managed_note_is_not_silently_recreated(self):
        drafts = proposal(self.bridge)
        self.save(drafts)
        (self.vault / 'Knowledge/Orchard.md').unlink()
        with self.assertRaisesRegex(BridgeError, 'saved_note_changed'):
            self.save(drafts)
        drafts[0]['content'] += '\nA new proposal after deletion.\n'
        with self.assertRaisesRegex(BridgeError, 'managed_note_missing'):
            self.save(drafts)
        self.assertFalse((self.vault / 'Knowledge/Orchard.md').exists())

    def test_concurrent_save_lock(self):
        drafts = proposal(self.bridge)
        preview = self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        with PrivateStore(self.bridge).locked():
            with self.assertRaisesRegex(BridgeError, 'save_busy'):
                self.bridge.save(drafts, 'Knowledge/Orchard.md', preview['preview_id'])
        self.assertFalse((self.vault / 'Knowledge').exists())

    def test_stdio_preview_save_retry_and_write_revocation(self):
        async def exercise():
            cfg = self.root / 'config.json'
            cfg.write_text(json.dumps(self.config))
            script = Path(__file__).resolve().parents[1] / 'capture_mcp.py'
            params = StdioServerParameters(command=sys.executable, args=[str(script)],
                                           env=dict(os.environ, CONNECTED_KNOWLEDGE_PRIVATE_CONFIG=str(cfg)))
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = {t.name: t for t in (await session.list_tools()).tools}
                    self.assertIn('save_linked_notes', tools)
                    self.assertTrue(tools['save_linked_notes'].annotations.destructiveHint)
                    self.assertTrue(tools['save_linked_notes'].annotations.idempotentHint)
                    self.assertNotIn('root', tools['save_linked_notes'].inputSchema['properties'])
                    async def call(name, args):
                        result = await session.call_tool(name, args)
                        self.assertFalse(result.isError, result.content)
                        return json.loads(result.content[0].text)
                    args = {'notes': proposal(self.bridge), 'entry_point': 'Knowledge/Orchard.md'}
                    preview = await call('preview_linked_notes', args)
                    args['preview_id'] = preview['preview_id']
                    self.assertEqual((await call('save_linked_notes', args))['status'], 'saved')
                    self.assertEqual((await call('save_linked_notes', args))['status'], 'unchanged')
                    self.config['vault_bridge']['write_enabled'] = False
                    cfg.write_text(json.dumps(self.config))
                    self.assertEqual((await call('save_linked_notes', args))['code'], 'writes_disabled')
                    self.assertEqual((await call('read_vault_note', {'note_ref': 'Knowledge/Orchard.md'}))['status'], 'read')
        asyncio.run(exercise())


if __name__ == '__main__':
    unittest.main()
