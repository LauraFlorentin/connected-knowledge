"""The ck.py commands behind /ck-setup, /ck-help and /ck-add-session (standard library only)."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
import zipfile

from ck_fixtures import Claude, Codex, Machine, PLUGIN, SCRIPTS
import ck
import ck_config
import ck_render

ROOT = PLUGIN.parents[1]
SKILLS = PLUGIN/'skills'
COMMANDS = ('ck-setup', 'ck-help', 'ck-add-session')


class Doctor(unittest.TestCase):
    def setUp(self):
        self.m = Machine(enabled=False)
        self.path = self.m.root/'config.json'

    def tearDown(self):
        self.m.cleanup()

    def save(self, **changes):
        cfg = dict(self.m.cfg, **changes)
        ck_config.save(cfg, self.path)
        return ck_config.load(self.path)

    def suggestion(self):
        result = ck.doctor(self.path, suggest=True)
        self.assertEqual(result['next']['stop'], 'stop here')
        return result['next']['suggestion']['command'], result

    def capture_one(self, cfg, category=None):
        path = Claude('s-%d' % len(list(self.m.claude.rglob('*.jsonl'))), self.m.projects/'garden') \
            .user('Fictional question').save(self.m.claude/'g')
        ck.add_session(cfg, str(path), {'category': category}, apply=True)

    def test_every_state_in_order(self):
        self.assertEqual(self.suggestion()[0], '/ck-setup')
        self.save(vault=str(self.m.root/'gone'))
        self.assertEqual(self.suggestion()[0], '/ck-setup vault')
        cfg = self.save()
        command, result = self.suggestion()
        self.assertEqual(command, '/ck-add-session current')
        self.assertEqual(result['next']['alternative']['command'], '/ck-add-session all')
        self.capture_one(cfg)
        self.assertEqual(self.suggestion()[0], '/ck-add-session all')
        ck.backfill(cfg, apply=True)
        self.assertEqual(self.suggestion()[0], 'ask: import my Claude export')
        with redirect_stdout(io.StringIO()):
            ck.main(['--config', str(self.path), 'mark-import', 'claude'])
            ck.main(['--config', str(self.path), 'mark-import', 'openai'])
        command, result = self.suggestion()
        self.assertEqual(command, 'ask: classify my unlabelled conversations')
        self.assertEqual(result['unlabelled'], 1)
        manifest = json.loads((self.m.state/'manifest.json').read_text())
        for item in manifest['items'].values():
            item['category'] = 'Work'
        (self.m.state/'manifest.json').write_text(json.dumps(manifest))
        self.assertEqual(self.suggestion()[0], '/ck-setup capture')
        self.save(capture=dict(self.m.cfg['capture'], enabled=True))
        command, result = self.suggestion()
        self.assertEqual(command, 'ask: develop one conversation into notes')
        self.assertIsNone(result['next']['alternative'])

    def test_satellite_is_not_asked_for_exports(self):
        cfg = self.save(role='satellite')
        self.capture_one(cfg, 'Work')
        ck.backfill(cfg, apply=True)
        self.assertEqual(self.suggestion()[0], '/ck-setup capture')

    def test_cli_prints_json(self):
        self.save()
        result = subprocess.run([sys.executable, str(SCRIPTS/'ck.py'), '--config', str(self.path), 'doctor', '--next'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual((report['machine'], report['state']), ('mac-mini', 'ready'))
        self.assertEqual(report['version'], json.loads((PLUGIN/'.claude-plugin/plugin.json').read_text())['version'])


class AddSession(unittest.TestCase):
    def setUp(self):
        self.m = Machine(enabled=False)
        self.cfg = ck_config.validate(self.m.cfg)
        self.old = Claude('11111111-aaaa-4bbb-8ccc-0000000000a1', self.m.projects/'garden').user('Older fictional chat')
        self.old_path = self.old.save(self.m.claude/'garden')
        self.new = Codex('019a0000-1111-7222-8333-4444555566aa', self.m.projects/'orchard').message('user', 'Newest fictional chat')
        self.new_path = self.new.save(self.m.codex)

    def tearDown(self):
        self.m.cleanup()

    def test_preview_writes_nothing(self):
        for target in ('latest', '11111111-aaaa-4bbb-8ccc-0000000000a1', str(self.old_path), 'all'):
            ck.add_session(self.cfg, target)
        self.assertEqual(self.m.vault_files(), [])
        self.assertFalse(self.m.state.exists())

    def test_by_id_latest_path_and_current(self):
        self.assertEqual(ck.add_session(self.cfg, '11111111-aaaa-4bbb-8ccc-0000000000a1')['platform'], 'Claude Code')
        self.assertEqual(ck.add_session(self.cfg, 'latest')['platform'], 'Codex')
        self.assertEqual(ck.add_session(self.cfg, str(self.old_path))['title'], 'Older fictional chat')
        current = ck.add_session(self.cfg, 'current', cwd=str(self.m.projects/'garden'))
        self.assertEqual(current['platform'], 'Claude Code')
        by_session = ck.add_session(self.cfg, 'current', session_id='019a0000-1111-7222-8333-4444555566aa')
        self.assertEqual(by_session['platform'], 'Codex')
        with self.assertRaises(ValueError):
            ck.add_session(self.cfg, 'no-such-session')

    def test_apply_with_labels_and_explicit_session_outside_capture_folders(self):
        outside = Claude('11111111-aaaa-4bbb-8ccc-0000000000a2', self.m.root/'elsewhere').user('Fictional elsewhere')
        path = outside.save(self.m.claude/'elsewhere')
        report = ck.add_session(self.cfg, str(path), {'title': 'Saved on request', 'category': 'Personal',
                                                     'summary': 'A fictional chat.', 'device': 'iphone'}, apply=True)
        self.assertEqual((report['status'], report['device']), ('created', 'iphone'))
        text = (self.m.vault/report['note']).read_text()
        self.assertIn('# [Personal] Saved on request', text)
        self.assertIn('A fictional chat.', text)

    def test_all_respects_capture_folders_and_records_the_backfill(self):
        Claude('11111111-aaaa-4bbb-8ccc-0000000000a3', self.m.root/'elsewhere').user('Out of scope').save(self.m.claude/'x')
        preview = ck.add_session(self.cfg, 'all')
        self.assertEqual((preview['found'], preview['new'], preview['out_of_scope']), (3, 2, 1))
        applied = ck.add_session(self.cfg, 'all', apply=True)
        self.assertEqual(applied['written'], 2)
        self.assertTrue((self.m.state/'backfill.json').exists())
        self.assertEqual(ck.add_session(self.cfg, 'all', apply=True)['written'], 0)

    def test_topics_must_exist_and_can_be_added(self):
        with self.assertRaises(ValueError):
            ck.add_session(self.cfg, 'latest', {'topics': ['Gardening']})
        (self.m.vault/'Home.md').write_text('# Home\n\n## Main topics\n')
        self.assertEqual(ck.topic_add(self.cfg, 'Gardening')['mode'], 'preview')
        self.assertFalse((self.m.vault/'Maps').exists())
        ck.topic_add(self.cfg, 'Gardening', apply=True)
        ck.topic_add(self.cfg, 'Raised beds', parent='Gardening', apply=True)
        tree = ck.topics(self.cfg)
        self.assertEqual(tree['main'], ['Gardening'])
        self.assertEqual(tree['topics']['Raised beds']['parent'], 'Gardening')
        self.assertIn('[[Maps/Gardening|Gardening]]', (self.m.vault/'Home.md').read_text())
        self.assertIn('[[Maps/Raised beds|Raised beds]]', (self.m.vault/'Maps/Gardening.md').read_text())
        report = ck.add_session(self.cfg, 'latest', {'topics': ['raised beds']}, apply=True)
        self.assertEqual(report['topics'], ['Maps/Raised beds'])

    def test_capture_switch(self):
        path = self.m.root/'config.json'
        ck_config.save(self.m.cfg, path)
        self.assertEqual(ck.capture_switch(True, cfg_path=path)['mode'], 'preview')
        self.assertFalse(ck_config.load(path)['capture']['enabled'])
        ck.capture_switch(True, ['claude-code'], cfg_path=path, apply=True)
        cfg = ck_config.load(path)
        self.assertEqual((cfg['capture']['enabled'], cfg['capture']['hosts']), (True, ['claude-code']))
        with self.assertRaises(ValueError):
            ck_config.save(dict(cfg, capture=dict(cfg['capture'], roots=[])), path)


class Skills(unittest.TestCase):
    def test_command_skills_are_complete(self):
        for name in COMMANDS:
            text = (SKILLS/name/'SKILL.md').read_text()
            meta, body = ck_render.split_note(text)
            self.assertEqual(meta['name'], name)
            self.assertLessEqual(len(meta['description']), 1024)
            self.assertIn('/' + name, meta['description'])
            self.assertIn('$' + name, meta['description'])
            self.assertTrue(meta.get('argument-hint'))
            self.assertIn('../zettelkasten-obsidian/scripts/ck.py', body)
            finish = body.split('## Finish', 1)[1]
            self.assertIn('stop here', finish)
            self.assertIn('Do not start the next task unasked', finish)
            agents = (SKILLS/name/'agents/openai.yaml').read_text()
            self.assertIn('$' + name, agents)
            toml = (PLUGIN.parents[1]/'integrations/gemini/commands'/(name + '.toml')).read_text() \
                if (PLUGIN.parents[1]/'integrations').exists() else None
            if toml is not None:
                self.assertIn('Use the ' + name + ' skill', toml)
                self.assertIn('{{args}}', toml)

    def test_guided_workflows_map_the_menu_to_commands(self):
        text = (SKILLS/'zettelkasten-obsidian/references/guided-workflows.md').read_text()
        for name in COMMANDS:
            self.assertIn('/' + name, text)


@unittest.skipUnless((ROOT/'tools/package_gemini.py').exists(), 'source checkout only')
class GeminiPackage(unittest.TestCase):
    def test_zip_contains_the_three_commands_and_no_claude_hooks(self):
        sys.path.insert(0, str(ROOT/'tools'))
        import package_gemini
        m = Machine()
        try:
            names = zipfile.ZipFile(package_gemini.build(m.root/'gemini.zip')).namelist()
        finally:
            m.cleanup()
        for name in COMMANDS:
            self.assertIn('commands/' + name + '.toml', names)
            self.assertIn('skills/' + name + '/SKILL.md', names)
        self.assertNotIn('hooks/capture.py', names)
        self.assertIn('hooks/gemini_capture.py', names)
        self.assertFalse(any('__pycache__' in n or n.endswith('.pyc') for n in names))


if __name__ == '__main__':
    unittest.main()
