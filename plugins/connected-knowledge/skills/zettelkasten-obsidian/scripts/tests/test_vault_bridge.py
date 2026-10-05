import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vault_bridge import BridgeError, VaultBridge
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def fixture(root):
    vault = root / 'Vault'
    for folder in ('Sources', 'Notes', 'Templates', 'Private'):
        (vault / folder).mkdir(parents=True)
    (vault / 'Vault Guide.md').write_text('Use type/status and readable filenames. Preserve existing identities.\n')
    (vault / 'Templates/Idea.md').write_text('---\ntype: idea\nstatus: auto\n---\n# {{title}}\n<% do_not_execute() %>\n')
    (vault / 'Sources/Selected chat.md').write_text('# Orchard chat\n\nCoverage: excerpt\n\nPears need a pollinator.\n')
    (vault / 'Notes/Pears.md').write_text('# Pears\n\nAn existing idea about pollination.\n')
    (vault / 'Private/Secret.md').write_text('Unselected private apples.\n')
    config = {'enabled': True, 'account': 'synthetic', 'spool': str(root / 'spool'),
              'destination': str(vault / 'Sources/Captures'),
              'vault_bridge': {'enabled': True, 'root': str(vault), 'guide': 'Vault Guide.md',
                               'templates': {'idea': 'Templates/Idea.md'},
                               'note_folders': ['Sources', 'Notes', 'Knowledge'], 'draft_folder': 'Knowledge'}}
    return vault, config


def proposal(bridge):
    doc = bridge.read_note('Sources/Selected chat.md')
    return [{'name': 'Orchard.md', 'content': '# Orchard\n\nA proposed summary.\n\n[[Sources/Selected chat.md|Selected source]]\n',
             'sources': [{'path': doc['path'], 'sha256': doc['sha256']}]}]


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


class VaultBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.vault, self.config = fixture(self.root)
        self.bridge = VaultBridge(self.config)

    def test_conventions_search_read_and_preview_never_write(self):
        before = snapshot(self.root)
        conventions = self.bridge.conventions()
        self.assertIn('<% do_not_execute() %>', conventions['templates']['idea']['content'])
        self.assertFalse(conventions['can_save_developed_notes'])
        results = self.bridge.search('pears')
        self.assertEqual({x['path'] for x in results['results']}, {'Notes/Pears.md', 'Sources/Selected chat.md'})
        self.assertEqual(self.bridge.search('private apples')['matching_notes'], 0)
        drafts = proposal(self.bridge)
        result = self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        self.assertEqual(result['items'][0]['content'], drafts[0]['content'])
        self.assertEqual(result['sources'][0]['coverage_label'], 'excerpt')
        self.assertEqual(result['written'], 0)
        self.assertFalse(result['can_apply'])
        self.assertEqual(result['items'][0]['action'], 'create')
        self.assertEqual(result['preview_id'], self.bridge.preview(drafts, 'Knowledge/Orchard.md')['preview_id'])
        self.assertEqual(before, snapshot(self.root))
        self.assertFalse((self.vault / 'Knowledge').exists())

    def test_disabled_and_independent_capture_state(self):
        cfg = deepcopy(self.config)
        cfg['enabled'] = False
        self.assertEqual(VaultBridge(cfg).read_note('Notes/Pears.md')['status'], 'read')
        cfg['vault_bridge']['enabled'] = False
        with self.assertRaisesRegex(BridgeError, 'bridge_disabled'):
            VaultBridge(cfg)

    def test_paths_hidden_files_and_unselected_scope(self):
        for ref in ('../Private/Secret.md', '/etc/passwd', 'Notes/../Private/Secret.md',
                    'Private/Secret.md', 'Notes/.secret.md', 'Notes\\Pears.md',
                    'Notes/%2e%2e/Secret.md', 'Vault Guide.md', 'Templates/Idea.md'):
            with self.subTest(ref=ref), self.assertRaises((BridgeError, OSError)):
                self.bridge.read_note(ref)

    def test_symlink_files_directories_and_hardlinks_are_not_read(self):
        (self.vault / 'Notes/Escape.md').symlink_to(self.vault / 'Private/Secret.md')
        (self.vault / 'Notes/Escape').symlink_to(self.vault / 'Private', target_is_directory=True)
        os.link(self.vault / 'Private/Secret.md', self.vault / 'Notes/Hard.md')
        for ref in ('Notes/Escape.md', 'Notes/Escape/Secret.md', 'Notes/Hard.md'):
            with self.subTest(ref=ref), self.assertRaises((BridgeError, OSError)):
                self.bridge.read_note(ref)
        result = self.bridge.search('private apples')
        self.assertEqual(result['matching_notes'], 0)
        self.assertEqual(result['skipped_notes'], 1)

    def test_root_symlink_and_archive_output_rejected(self):
        cfg = deepcopy(self.config)
        (self.root / 'Alias').symlink_to(self.vault, target_is_directory=True)
        cfg['vault_bridge']['root'] = str(self.root / 'Alias')
        with self.assertRaises(ValueError):
            VaultBridge(cfg)
        cfg = deepcopy(self.config)
        cfg['vault_bridge']['draft_folder'] = 'Sources'
        with self.assertRaisesRegex(BridgeError, 'invalid_configuration'):
            VaultBridge(cfg)
        cfg['vault_bridge']['draft_folder'] = 'Private'
        with self.assertRaisesRegex(BridgeError, 'invalid_configuration'):
            VaultBridge(cfg)

    def test_changed_source_rejected(self):
        drafts = proposal(self.bridge)
        (self.vault / 'Sources/Selected chat.md').write_text('Human source revision')
        with self.assertRaisesRegex(BridgeError, 'source_changed'):
            self.bridge.preview(drafts, 'Knowledge/Orchard.md')

    def test_changed_source_during_preview_rejected(self):
        drafts = proposal(self.bridge)
        original = self.bridge.document
        def changed(path):
            result = original(path)
            if str(path) == 'Sources/Selected chat.md':
                (self.vault / path).write_text('Concurrent human revision')
            return result
        with patch.object(self.bridge, 'document', side_effect=changed):
            with self.assertRaisesRegex(BridgeError, 'note_changed'):
                self.bridge.preview(drafts, 'Knowledge/Orchard.md')

    def test_occupied_target_and_expected_hash(self):
        (self.vault / 'Knowledge').mkdir()
        target = self.vault / 'Knowledge/Orchard.md'
        target.write_text('Existing human note\n')
        drafts = proposal(self.bridge)
        result = self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        self.assertEqual(result['conflicts'], 1)
        drafts[0]['expected_sha256'] = self.bridge.read_note('Knowledge/Orchard.md')['sha256']
        result = self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        self.assertEqual(result['items'][0]['action'], 'update')
        self.assertIn('-Existing human note', result['items'][0]['diff'])
        target.write_text('Later human change\n')
        self.assertEqual(self.bridge.preview(drafts, 'Knowledge/Orchard.md')['conflicts'], 1)
        self.assertEqual(target.read_text(), 'Later human change\n')

    def test_draft_names_collisions_and_missing_sources(self):
        for name in ('../Escape.md', 'Sub/Note.md', '/Note.md', '.hidden.md', 'not-markdown.txt'):
            drafts = proposal(self.bridge)
            drafts[0]['name'] = name
            with self.subTest(name=name), self.assertRaises(BridgeError):
                self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        drafts = proposal(self.bridge)
        drafts.append(deepcopy(drafts[0]))
        drafts[1]['name'] = 'orchard.md'
        with self.assertRaisesRegex(BridgeError, 'duplicate_target'):
            self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        drafts = proposal(self.bridge)
        drafts[0]['sources'] = []
        with self.assertRaisesRegex(BridgeError, 'sources_required'):
            self.bridge.preview(drafts, 'Knowledge/Orchard.md')

    def test_sources_must_be_linked_and_missing_targets_block_preview(self):
        drafts = proposal(self.bridge)
        drafts[0]['content'] = '# Orchard\nNo source link.'
        with self.assertRaisesRegex(BridgeError, 'source_link_required'):
            self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        for link in ('[[Missing]]', '[[Private/Secret.md]]', '[Escape](../../Private/Secret.md)'):
            drafts = proposal(self.bridge)
            drafts[0]['content'] += link
            with self.subTest(link=link), self.assertRaisesRegex(BridgeError, 'missing_or_outside_link'):
                self.bridge.preview(drafts, 'Knowledge/Orchard.md')

    def test_ambiguous_short_names_require_explicit_target(self):
        (self.vault / 'Sources/Pears.md').write_text('Another pear note')
        drafts = proposal(self.bridge)
        drafts[0]['content'] += '\n[[Pears]]'
        with self.assertRaisesRegex(BridgeError, 'ambiguous_link'):
            self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        drafts[0]['content'] = drafts[0]['content'].replace('[[Pears]]', '[[Notes/Pears.md]]')
        self.assertEqual(self.bridge.preview(drafts, 'Knowledge/Orchard.md')['conflicts'], 0)

    def test_linked_drafts_and_disconnected_entry_point(self):
        drafts = proposal(self.bridge)
        second = deepcopy(drafts[0])
        second['name'] = 'Pollination.md'
        drafts.append(second)
        with self.assertRaisesRegex(BridgeError, 'entry_point_disconnected'):
            self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        drafts[0]['content'] += '\n[[Knowledge/Pollination.md]]'
        self.assertEqual(len(self.bridge.preview(drafts, 'Knowledge/Orchard.md')['items']), 2)
        with self.assertRaisesRegex(BridgeError, 'entry_point_disconnected'):
            self.bridge.preview(drafts, 'Notes/Pears.md')

    def test_relative_markdown_external_links_and_anchor_limits(self):
        drafts = proposal(self.bridge)
        drafts[0]['content'] = '# Orchard\n[Source](../Sources/Selected%20chat.md)\n'
        drafts[0]['content'] += '[[Notes/Pears.md#Pollination]]\n[Web](https://example.com)\n'
        result = self.bridge.preview(drafts, 'Knowledge/Orchard.md')
        self.assertEqual(len(result['external_links']), 1)
        self.assertEqual(len(result['unchecked_links']), 1)
        self.assertFalse(result['external_links'][0]['verified'])

    def test_existing_special_filenames_remain_searchable(self):
        (self.vault / 'Notes/100% yield [draft].md').write_text('# Yield\nPears and apples.\n')
        results = self.bridge.search('apples')
        self.assertEqual(results['results'][0]['path'], 'Notes/100% yield [draft].md')
        self.assertIn('Pears', self.bridge.read_note(results['results'][0]['path'])['content'])

    def test_existing_markdown_entry_point(self):
        (self.vault / 'Notes/Orchard map.md').write_text('# Orchard map\n[Summary](../Knowledge/Orchard.md)\n')
        result = self.bridge.preview(proposal(self.bridge), 'Notes/Orchard map.md')
        self.assertEqual(result['entry_point'], 'Notes/Orchard map.md')
        self.assertIn('Notes/Orchard map.md', result['snapshots'])

    def test_search_bounds_and_oversized_notes(self):
        for query, limit in (('', 10), ('pears', 0), ('pears', 21), ('p' * 257, 1)):
            with self.subTest(query=query), self.assertRaisesRegex(BridgeError, 'invalid_search'):
                self.bridge.search(query, limit)
        with patch('vault_bridge.MAX_FILES', 1):
            with self.assertRaisesRegex(BridgeError, 'scope_too_large'):
                self.bridge.search('pears')
        with patch('vault_bridge.MAX_ENTRIES', 1):
            with self.assertRaisesRegex(BridgeError, 'scope_too_large'):
                self.bridge.search('pears')
        with patch('vault_bridge.MAX_BYTES', 20):
            with self.assertRaisesRegex(BridgeError, 'note_too_large'):
                self.bridge.read_note('Sources/Selected chat.md')
        self.assertTrue(self.bridge.search('pears', 1)['truncated'])

    def test_stdio_opt_in_schema_preview_and_runtime_revocation(self):
        async def exercise():
            cfg = self.root / 'config.json'
            cfg.write_text(json.dumps(self.config))
            script = Path(__file__).resolve().parents[1] / 'capture_mcp.py'
            params = StdioServerParameters(command=sys.executable, args=[str(script)],
                                           env=dict(os.environ, CONNECTED_KNOWLEDGE_PRIVATE_CONFIG=str(cfg)))
            before = snapshot(self.vault)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listing = {t.name: t for t in (await session.list_tools()).tools}
                    self.assertEqual(set(listing), {'save_selected_capture', 'read_vault_conventions',
                                                   'search_vault_notes', 'read_vault_note', 'preview_linked_notes'})
                    for name, tool in listing.items():
                        for key in ('root', 'destination', 'account', 'config', 'apply'):
                            self.assertNotIn(key, tool.inputSchema['properties'])
                        self.assertEqual(tool.annotations.readOnlyHint, name != 'save_selected_capture')
                    schema = listing['preview_linked_notes'].inputSchema
                    self.assertFalse(schema['$defs']['NoteDraft']['additionalProperties'])
                    async def call(name, arguments):
                        result = await session.call_tool(name, arguments)
                        self.assertFalse(result.isError, result.content)
                        return json.loads(result.content[0].text)
                    self.assertEqual((await call('read_vault_conventions', {}))['status'], 'read')
                    self.assertEqual((await call('search_vault_notes', {'query': 'pears'}))['matching_notes'], 2)
                    read = await call('read_vault_note', {'note_ref': 'Sources/Selected chat.md'})
                    self.assertEqual(read['sha256'], proposal(self.bridge)[0]['sources'][0]['sha256'])
                    preview = await call('preview_linked_notes', {'notes': proposal(self.bridge), 'entry_point': 'Knowledge/Orchard.md'})
                    self.assertEqual(preview['written'], 0)
                    self.assertFalse(preview['can_apply'])
                    denied = await call('read_vault_note', {'note_ref': 'Private/Secret.md'})
                    self.assertEqual(denied['status'], 'error')
                    self.assertNotIn(str(self.vault), json.dumps(denied))
                    self.config['vault_bridge']['enabled'] = False
                    cfg.write_text(json.dumps(self.config))
                    self.assertEqual((await call('read_vault_note', {'note_ref': 'Notes/Pears.md'}))['code'], 'bridge_disabled')
            self.assertEqual(before, snapshot(self.vault))
        asyncio.run(exercise())


if __name__ == '__main__':
    unittest.main()
