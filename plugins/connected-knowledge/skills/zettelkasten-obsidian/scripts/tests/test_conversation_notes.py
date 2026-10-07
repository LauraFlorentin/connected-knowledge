"""Labels, safe rendering, migration, starter variants and adoption (uses PyYAML)."""
import json
from pathlib import Path
import shutil
import unittest

import yaml

from ck_fixtures import Claude, Codex, Machine
import chat_import
import ck
import ck_config
import ck_render
import ck_sweep
import knowledge_graph
import starter_vault
import vault_check


class Escaping(unittest.TestCase):
    CASES = [
        ('```dataviewjs\ndv.pages()\n```', '```text\ndv.pages()\n```'),
        ('~~~query\ntag:#x\n~~~', '~~~text\ntag:#x\n~~~'),
        ('```tasks\nnot done\n```', '```text\nnot done\n```'),
        ('```base\nviews: []\n```', '```text\nviews: []\n```'),
        ('```python\nprint("[[x]]")\n```', '```python\nprint("[[x]]")\n```'),
        ('Run `= this.file.name` now', 'Run `\u2060= this.file.name` now'),
        ('Run `$= dv.current()`', 'Run `\u2060$= dv.current()`'),
        ('See [[Secret note]]', 'See \\[\\[Secret note]]'),
        ('![[embed.pdf]]', '!\\[\\[embed.pdf]]'),
        ('![chart](https://tracker.example/p.png)', '\\![chart]\\(https://tracker.example/p.png)'),
        ('[open](obsidian://open?vault=x)', '[open]\\(obsidian://open?vault=x)'),
        ('Tag #project and (#inner)', 'Tag \\#project and (\\#inner)'),
        ('Issue #12 stays', 'Issue #12 stays'),
        ('# Heading', '\\# Heading'),
        ('- [ ] buy soil', '- \\[ ] buy soil'),
        ('status:: done', 'status:\\: done'),
        ('<iframe src="https://x"></iframe>', '&lt;iframe src="https://x">&lt;/iframe>'),
        ('%% hidden %%', '\\%\\% hidden \\%\\%'),
        ('Text\n---', 'Text\n\\---'),
        ('```js\nunclosed', '```js\nunclosed\n```'),
    ]

    def test_table(self):
        for source, expected in self.CASES:
            self.assertEqual(ck_render.inert(source), expected, source)

    def test_inert_transcript_has_no_live_links_or_tags_for_the_checker(self):
        m = Machine()
        try:
            cfg = ck_config.validate(m.cfg)
            text = '\n'.join(source for source, _ in self.CASES)
            path = Claude('s-1', m.projects/'garden').user(text).assistant(text).save(m.claude/'g')
            ck_sweep.capture_file(cfg, 'claude-code', path, {'category': 'Work'}, apply=True)
            report = vault_check.check(m.vault, 'auto')
            self.assertEqual([f for f in report['findings'] if f['severity'] != 'info'], [])
        finally:
            m.cleanup()


class Starters(unittest.TestCase):
    def setUp(self):
        self.m = Machine()

    def tearDown(self):
        self.m.cleanup()

    def start(self, variant, **kwargs):
        target = self.m.root/variant
        starter_vault.create(target, True, variant=variant, topics=['AI & Agents', 'Health'], **kwargs)
        return target

    def test_both_variants_pass_the_strict_check_after_one_capture(self):
        for variant in ('templates', 'no-templates'):
            vault = self.start(variant)
            cfg = ck_config.validate(dict(self.m.cfg, vault=str(vault)))
            path = Claude('s-' + variant, self.m.projects/'garden').user('Fictional question').assistant('Answer').save(self.m.claude/variant)
            report = ck_sweep.capture_file(cfg, 'claude-code', path, {'category': 'Work', 'topics': ['Health']}, apply=True)
            self.assertEqual(report['status'], 'created')
            result = vault_check.check(vault, 'auto')
            self.assertEqual((result['errors'], result['warnings']), (0, 0), result['findings'])
            self.assertFalse((vault/'.obsidian').exists())
            self.assertTrue((vault/'Vault Guide.md').exists())
            self.assertFalse(list(vault.glob('VAULT-GUIDE.md')))

    def test_variant_b_guide_holds_every_note_shape(self):
        vault = self.start('no-templates')
        guide = (vault/'Vault Guide.md').read_text()
        self.assertFalse((vault/'Templates').exists())
        for name in starter_vault.NOTE_TEMPLATES:
            self.assertIn((starter_vault.ASSETS/'templates'/(name + '.md')).read_text(), guide)

    def test_variant_a_has_templates_and_no_capture_templates(self):
        vault = self.start('templates')
        names = sorted(p.name for p in (vault/'Templates').iterdir())
        self.assertEqual(names, sorted(n.capitalize() + '.md' for n in starter_vault.NOTE_TEMPLATES))
        for path in (vault/'Templates').iterdir():
            meta = yaml.safe_load(path.read_text().replace('{{', '"').replace('}}', '"').split('---')[1].replace('""', '"'))
            self.assertNotIn('type', meta)
            self.assertNotIn('status', meta)

    def test_full_and_minimal_structures(self):
        full = self.start('no-templates')
        for folder in starter_vault.FOLDERS:
            self.assertTrue((full/folder).is_dir(), folder)
        minimal = self.m.root/'minimal'
        starter_vault.create(minimal, True, structure='minimal')
        self.assertEqual(sorted(p.name for p in minimal.iterdir()),
                         ['AGENTS.md', 'CLAUDE.md', 'GEMINI.md', 'Home.md', 'Vault Guide.md', '_meta'])

    def test_topic_names_are_checked_and_maps_link_home(self):
        with self.assertRaises(ValueError):
            starter_vault.files(topics=['Bad/Name'])
        with self.assertRaises(ValueError):
            starter_vault.files(topics=['Same', 'same'])
        vault = self.start('no-templates')
        self.assertIn('[[Maps/AI & Agents|AI & Agents]]', (vault/'Home.md').read_text())

    def test_custom_categories_are_accepted_by_the_check(self):
        vault = self.m.root/'custom'
        starter_vault.create(vault, True, 'custom', ['Research', 'Life'])
        cfg = ck_config.validate(dict(self.m.cfg, vault=str(vault)))
        path = Claude('s-c', self.m.projects/'garden').user('Fictional').save(self.m.claude/'c')
        with self.assertRaises(ValueError):
            ck_sweep.capture_file(cfg, 'claude-code', path, {'category': 'Work'})
        ck_sweep.capture_file(cfg, 'claude-code', path, {'category': 'Research'}, apply=True)
        self.assertEqual(vault_check.check(vault, 'auto')['errors'], 0)


class CheckerRules(unittest.TestCase):
    def test_missing_category_is_a_warning_only_while_provisional(self):
        m = Machine()
        try:
            note = m.vault/'Idea.md'
            base = 'schema_version: 1\nid: "x"\nnote_type: idea\ntitle: "Idea"\n'
            note.write_text('---\n' + base + 'classification_status: provisional\n---\nBody\n')
            report = vault_check.check(m.vault, 'auto')
            self.assertEqual((report['errors'], report['warnings']), (0, 1))
            note.write_text('---\n' + base + 'classification_status: reviewed\n---\nBody\n')
            self.assertEqual(vault_check.check(m.vault, 'auto')['errors'], 1)
            note.write_text('---\nschema_version: 1\nid: "x"\nnote_type: map\ntitle: "Map"\n---\nBody\n')
            report = vault_check.check(m.vault, 'auto')
            self.assertEqual((report['errors'], report['warnings']), (0, 0))
        finally:
            m.cleanup()


class Adoption(unittest.TestCase):
    def setUp(self):
        self.m = Machine()
        (self.m.vault/'Sources').mkdir()
        (self.m.vault/'.obsidian').mkdir()
        (self.m.vault/'.obsidian/app.json').write_text('{"keep": true}')
        (self.m.vault/'Sources/Old.md').write_text('---\ntype: reference\nstatus: auto\ndate: "2026-09-01"\n---\nOld note\n')
        (self.m.vault/'Vault Guide.md').write_text('# Guide\n\nMy conventions.\n')
        self.answers = {'machine': 'mac-mini', 'role': 'hub', 'vault': str(self.m.vault), 'vault_mode': 'existing',
                        'state': str(self.m.state), 'capture': {'roots': [str(self.m.projects)],
                        'transcript_roots': self.m.cfg['capture']['transcript_roots']}}
        self.cfg_path = self.m.home/'.config/connected-knowledge/config.json'

    def tearDown(self):
        self.m.cleanup()

    def test_preview_writes_nothing_and_proposes_the_vaults_own_names(self):
        before = self.m.vault_files()
        plan = ck.setup(self.answers, False, self.cfg_path)
        self.assertEqual(self.m.vault_files(), before)
        self.assertFalse(self.cfg_path.exists())
        profile = plan['vault']['profile']
        self.assertEqual(profile['fields'], {'note_type': 'type', 'review_status': 'status'})
        self.assertEqual(profile['values'], {'note_type': {'source': 'reference'}, 'review_status': {'draft': 'auto'}})
        self.assertIn('_meta/ck/vault.json', plan['vault']['additions'])

    def test_adopted_vault_gets_its_own_names_and_no_parallel_fields(self):
        ck.setup(dict(self.answers, update_guide=True), True, self.cfg_path)
        self.assertEqual((self.m.vault/'.obsidian/app.json').read_text(), '{"keep": true}')
        self.assertIn('## AI history', (self.m.vault/'Vault Guide.md').read_text())
        self.assertEqual((self.m.vault/'Sources/Old.md').read_text(), '---\ntype: reference\nstatus: auto\ndate: "2026-09-01"\n---\nOld note\n')
        cfg = ck_config.load(self.cfg_path)
        self.assertFalse(cfg['capture']['enabled'])
        self.assertEqual(self.m.state.stat().st_mode & 0o777, 0o700)
        path = Claude('s-a', self.m.projects/'garden').user('Fictional question').save(self.m.claude/'a')
        report = ck_sweep.capture_file(cfg, 'claude-code', path, apply=True)
        meta = yaml.safe_load((self.m.vault/report['note']).read_text().split('---')[1])
        self.assertEqual((meta['type'], meta['status']), ('reference', 'auto'))
        self.assertNotIn('note_type', meta)
        self.assertNotIn('review_status', meta)
        # The vault's own profile is understood by the checker.
        self.assertEqual(vault_check.check(self.m.vault, 'auto')['errors'], 0)

    def test_new_vault_setup(self):
        target = self.m.root/'New Vault'
        answers = dict(self.answers, vault=str(target), vault_mode='new',
                       new_vault={'variant': 'templates', 'topics': ['Gardening']})
        plan = ck.setup(answers, False, self.cfg_path)
        self.assertIn('Templates/Idea.md', plan['vault']['files'])
        self.assertFalse(target.exists())
        ck.setup(answers, True, self.cfg_path)
        self.assertTrue((target/'Maps/Gardening.md').exists())
        self.assertEqual(ck_config.load(self.cfg_path)['vault'], str(target))


class ImporterLabels(unittest.TestCase):
    def setUp(self):
        self.m = Machine()

    def tearDown(self):
        self.m.cleanup()

    def test_chatgpt_epoch_dates_become_iso_and_keys_follow_the_ontology(self):
        export = self.m.root/'conversations.json'
        export.write_text(json.dumps([{'id': 'c1', 'title': 'Fictional pears', 'create_time': 1759759740.5,
                                       'update_time': 1759763340, 'mapping': {'n1': {'parent': None, 'message': {
                                           'author': {'role': 'user'}, 'create_time': 1759759740.5,
                                           'content': {'parts': ['See [[x]] and #tag']}}}}}]))
        archive = self.m.vault/'ChatArchive/chatgpt'
        chat_import.run(export, archive, 'chatgpt', 'personal', True)
        note = next(archive.glob('*.md')).read_text()
        meta = yaml.safe_load(note.split('---')[1])
        self.assertRegex(meta['source_created'], r'^2025-10-0\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$')
        self.assertEqual((meta['source_platform'], meta['source_id'], meta['source_account']), ('ChatGPT', 'c1', 'personal'))
        for legacy in ('conversation_source', 'conversation_id', 'account_label'):
            self.assertNotIn(legacy, meta)
        self.assertIn('> See \\[\\[x]] and \\#tag', note)
        # The graph tools read identity from the manifest, so new keys are understood.
        sources, _ = knowledge_graph.load_sources(self.m.vault, 'ChatArchive/chatgpt')
        self.assertEqual(len(sources), 1)

    def test_graph_tools_still_read_legacy_notes(self):
        export = self.m.root/'claude.json'
        export.write_text(json.dumps([{'uuid': 'u1', 'name': 'Fictional', 'chat_messages': [
            {'uuid': 'm1', 'sender': 'human', 'text': 'Fictional question'}]}]))
        archive = self.m.vault/'ChatArchive/claude'
        chat_import.run(export, archive, 'claude', 'personal', True)
        manifest = json.loads((archive/'manifest.json').read_text())
        record = next(iter(manifest['records'].values()))
        note = archive/record['path']
        meta = yaml.safe_load(note.read_text().split('---')[1])
        legacy = dict(meta, conversation_source='claude', conversation_id='u1', account_label='personal')
        for key in ('source_platform', 'source_id', 'source_account'):
            legacy.pop(key)
        text = '---\n' + yaml.safe_dump(legacy, sort_keys=False) + '---' + note.read_text().split('---', 2)[2]
        note.write_text(text)
        for key in ('platform', 'account', 'conversation_id'):
            record.pop(key)
        record['sha256'] = chat_import.digest(text.encode())
        (archive/'manifest.json').write_text(json.dumps(manifest))
        sources, _ = knowledge_graph.load_sources(self.m.vault, 'ChatArchive/claude')
        self.assertEqual(next(iter(sources.values()))['platform'], 'claude')


class Migration(unittest.TestCase):
    def setUp(self):
        self.m = Machine()
        self.cfg = ck_config.validate(self.m.cfg)
        export = self.m.root/'claude.json'
        export.write_text(json.dumps([
            {'uuid': 'u1', 'name': 'Fictional orchard', 'created_at': '2026-09-01T10:00:00Z',
             'chat_messages': [{'uuid': 'm1', 'sender': 'human', 'text': 'How many pears?', 'created_at': '2026-09-01T10:00:00Z'},
                               {'uuid': 'm2', 'sender': 'assistant', 'text': 'Twelve.', 'created_at': '2026-09-01T10:01:00Z'}]},
            {'uuid': 'u2', 'name': 'Fictional edited', 'chat_messages': [{'uuid': 'm3', 'sender': 'human', 'text': 'Hello'}]}]))
        self.archive = self.m.vault/'ChatArchive/claude-1'
        chat_import.run(export, self.archive, 'claude', 'personal', True)
        # Turn it into what 1.6.0 wrote: identity in legacy properties, not in the manifest.
        manifest = json.loads((self.archive/'manifest.json').read_text())
        for record in manifest['records'].values():
            note = self.archive/record['path']
            head, body = note.read_text().split('---', 2)[1:]
            meta = yaml.safe_load(head)
            meta.update(conversation_source='claude', conversation_id=meta.pop('source_id'),
                        account_label=meta.pop('source_account'))
            meta.pop('source_platform')
            text = '---\n' + yaml.safe_dump(meta, sort_keys=False) + '---' + body
            note.write_text(text)
            record['sha256'] = chat_import.digest(text.encode())
            for key in ('platform', 'account', 'conversation_id'):
                record.pop(key)
        (self.archive/'manifest.json').write_text(json.dumps(manifest))
        edited = next(r for r in manifest['records'].values() if 'edited' in (self.archive/r['path']).read_text())
        (self.archive/edited['path']).write_text((self.archive/edited['path']).read_text() + '\nMy edit')

    def tearDown(self):
        self.m.cleanup()

    def test_migrates_once_reports_edits_and_is_a_no_op_after(self):
        before = {p: p.read_bytes() for p in self.archive.rglob('*') if p.is_file()}
        preview = ck.migrate(self.cfg, self.archive)
        self.assertEqual((preview['migrated'], len(preview['human_edited'])), (1, 1))
        self.assertFalse(self.m.state.exists())
        first = ck.migrate(self.cfg, self.archive, True)
        self.assertEqual((first['migrated'], first['failed']), (1, []))
        notes = list((self.m.vault/'Sources/AI Conversations').rglob('*.md'))
        self.assertEqual(len(notes), 1)
        meta, _ = ck_render.split_note(notes[0].read_text())
        self.assertEqual((meta['source_platform'], meta['source_surface'], meta['title']), ('Claude', 'account-export', 'Fictional orchard'))
        self.assertTrue(meta['source_created'].startswith('2026-09-01T'))
        second = ck.migrate(self.cfg, self.archive, True)
        self.assertEqual((second['migrated'], second['unchanged']), (0, 1))
        self.assertEqual({p: p.read_bytes() for p in self.archive.rglob('*') if p.is_file()}, before)
        self.assertTrue(list((self.m.state/'raw/claude').glob('*.json')))

    def test_legacy_session_capture_migrates_and_live_capture_continues_it(self):
        import session_capture
        garden = self.m.projects/'garden'
        session = Claude('11111111-aaaa-4bbb-8ccc-0000000000ee', garden).user('Fictional question').assistant('Answer')
        path = session.save(self.m.claude/'legacy')
        legacy = {'host': 'claude-code', 'enabled': True, 'account': 'personal', 'projects': [str(garden)],
                  'transcript_roots': [str(self.m.claude)], 'spool': str(self.m.root/'spool'),
                  'destination': str(self.m.vault/'ChatArchive/claude-code'), 'vocabulary': 'default'}
        session_capture.capture(legacy, path, True)
        report = ck.migrate(self.cfg, self.m.vault/'ChatArchive/claude-code', True)
        self.assertEqual(report['migrated'], 1, report)
        self.assertEqual(ck_sweep.capture_file(self.cfg, 'claude-code', path, apply=True)['status'], 'unchanged')
        session.user('More').save(self.m.claude/'legacy')
        self.assertEqual(ck_sweep.capture_file(self.cfg, 'claude-code', path, apply=True)['status'], 'updated')


if __name__ == '__main__':
    unittest.main()
