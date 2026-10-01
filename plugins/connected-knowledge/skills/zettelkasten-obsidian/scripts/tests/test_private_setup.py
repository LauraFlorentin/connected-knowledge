import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from private_setup import setup
from private_capture import capture


class PrivateSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.vault = self.root/'Fictional Vault'
        self.vault.mkdir()
        self.runtime = self.root/'Private Runtime'
        self.template = self.vault/'source.md'
        self.template.write_text('---\ntype: reference\nstatus: reviewed\nowner: Fictional owner\ndate: "{{date:YYYY-MM-DD}}"\n---\n# {{title}}\n\n## Review\nNot yet reviewed.\n')
        self.payload = {'source': 'chatgpt', 'conversation_id': 'caller-fictional',
                        'capture_id': 'selection-1', 'title': 'Fictional / orchard', 'coverage': 'excerpt',
                        'messages': [{'id': 'm1', 'role': 'user', 'text': 'Fictional pears.'}]}

    def prepare(self, apply=False):
        return setup(self.runtime, self.vault, 'tunnel_00000000000000000000000000000000', 'fictional-account',
                     template=self.template, apply=apply)

    def test_preview_no_writes_and_install_preserves_template(self):
        before = self.template.read_bytes()
        self.assertEqual(self.prepare()['mode'], 'preview')
        self.assertFalse(self.runtime.exists())
        self.assertFalse((self.vault/'Inbox').exists())
        with patch('private_setup.venv.EnvBuilder') as builder:
            self.prepare(True)
            builder.return_value.create.assert_called_once()
        cfg = json.loads((self.runtime/'capture-config.json').read_text())
        first = capture(cfg, self.payload, True)
        self.assertEqual(first['status'], 'saved')
        relocated = subprocess.run([sys.executable, str(self.runtime/'scripts/private_capture.py'),
                                   '--config', str(self.runtime/'capture-config.json'), '--apply'],
                                  input=json.dumps(self.payload), text=True, capture_output=True)
        self.assertEqual(relocated.returncode, 0, relocated.stdout + relocated.stderr)
        self.assertEqual(json.loads(relocated.stdout)['status'], 'unchanged')
        note = next((self.vault/'Inbox/ChatGPT Captures').glob('*.md'))
        self.assertTrue(note.name.startswith('Fictional - orchard'))
        text = note.read_text()
        self.assertIn('owner: Fictional owner', text)
        self.assertIn('status: auto', text)
        self.assertIn('conversation_source: chatgpt', text)
        self.assertIn('conversation_id: caller-fictional', text)
        self.assertIn('> Fictional pears.', text)
        self.assertEqual(self.template.read_bytes(), before)
        self.payload['title'] = 'Changed title'
        capture(cfg, self.payload, True)
        self.assertEqual(len(list(note.parent.glob('*.md'))), 1)
        self.assertEqual(capture(cfg, self.payload, True)['status'], 'unchanged')
        self.assertFalse(list(note.parent.glob('*.lock')))
        note.write_text('Human edit')
        with self.assertRaises(ValueError):
            capture(cfg, self.payload, True)
        self.assertEqual(note.read_text(), 'Human edit')

    def test_invalid_template_rejected_before_activation(self):
        self.template.write_text('---\ntype: reference\n---\n{{execute:danger}}')
        with self.assertRaises(ValueError):
            self.prepare(True)
        self.assertFalse(self.runtime.exists())

    def test_runtime_must_not_replace_or_enter_vault(self):
        self.runtime = self.vault/'runtime'
        with self.assertRaises(ValueError):
            self.prepare(True)
        self.runtime = self.root/'Private Runtime'
        self.runtime.mkdir()
        (self.runtime/'human.txt').write_text('Keep me')
        with self.assertRaises(ValueError):
            self.prepare(True)
        self.assertEqual((self.runtime/'human.txt').read_text(), 'Keep me')

    def test_process_kill_does_not_leave_import_lock(self):
        # Kill while holding the actual archive OS lock, then save normally.
        script = Path(__file__).resolve().parents[1]
        archive = self.root/'Archive'
        archive.mkdir()
        code = ('import sys,time; from pathlib import Path; '
                'from chat_import import import_lock; '
                'ctx=import_lock(Path(sys.argv[1])); ctx.__enter__(); '
                'print("locked",flush=True); time.sleep(60)')
        process = subprocess.Popen([sys.executable, '-c', code, str(archive)], cwd=script,
                                   stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), 'locked')
        finally:
            process.kill()
            process.wait(timeout=5)
            process.stdout.close()
        from chat_import import import_lock
        with import_lock(archive):
            pass
        cfg = {'enabled': True, 'account': 'fictional', 'spool': str(self.root/'spool'),
               'destination': str(archive)}
        self.assertEqual(capture(cfg, self.payload, True)['status'], 'saved')


if __name__ == '__main__':
    unittest.main()
