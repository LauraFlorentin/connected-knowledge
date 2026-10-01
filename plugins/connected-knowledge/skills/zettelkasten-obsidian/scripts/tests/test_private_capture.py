import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from private_capture import capture, private_path, PLUGIN


class PrivateCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.cfg = {'enabled': True, 'account': 'synthetic', 'spool': str(self.root/'spool'),
                    'destination': str(self.root/'archive')}
        self.payload = {'source': 'chatgpt', 'conversation_id': 'fictional-chat',
                        'capture_id': 'selection-1', 'title': 'Fictional orchard', 'coverage': 'excerpt',
                        'messages': [{'id': 'm1', 'role': 'user', 'text': 'Plant fictional apples.'}]}

    def test_preview_repeat_revision_and_separate_selection(self):
        self.assertEqual(capture(self.cfg, self.payload)['status'], 'preview')
        self.assertFalse((self.root/'spool').exists())
        self.assertEqual(capture(self.cfg, self.payload, True)['status'], 'saved')
        self.assertEqual(capture(self.cfg, self.payload, True)['status'], 'unchanged')
        self.payload['messages'][0]['text'] = 'Plant fictional pears.'
        self.assertEqual(capture(self.cfg, self.payload, True)['status'], 'saved')
        self.payload['capture_id'] = 'selection-2'
        capture(self.cfg, self.payload, True)
        self.assertEqual(len(list((self.root/'archive').glob('*.md'))), 2)
        originals = list((self.root/'archive'/'originals').glob('*.json'))
        self.assertEqual(len(originals), 3)
        self.assertEqual(json.loads(originals[0].read_text())[0]['capture_provenance']['source'], 'chatgpt')

    def test_conflict_preserves_human_edit(self):
        capture(self.cfg, self.payload, True)
        note = next((self.root/'archive').glob('*.md'))
        note.write_text('human edit')
        with self.assertRaises(ValueError):
            capture(self.cfg, self.payload, True)
        self.assertEqual(note.read_text(), 'human edit')

    def test_disabled_and_invalid_coverage(self):
        self.cfg['enabled'] = False
        with self.assertRaises(ValueError):
            capture(self.cfg, self.payload, True)
        self.assertFalse((self.root/'spool').exists())
        self.cfg['enabled'] = True
        for coverage in ('full-account-history', None):
            self.payload['coverage'] = coverage
            with self.assertRaises(ValueError):
                capture(self.cfg, self.payload, True)

    def test_private_boundaries(self):
        with self.assertRaises(ValueError):
            private_path(str(PLUGIN/'runtime'))
        alias = self.root/'alias'
        alias.symlink_to(self.root/'archive')
        with self.assertRaises(ValueError):
            private_path(str(alias/'nested'))
        self.cfg['destination'] = self.cfg['spool']
        with self.assertRaises(ValueError):
            capture(self.cfg, self.payload, True)

    def test_concurrent_same_selection_is_one_record(self):
        config = self.root/'config.json'
        config.write_text(json.dumps(self.cfg))
        script = Path(__file__).resolve().parents[1]/'private_capture.py'
        processes = [subprocess.Popen([sys.executable, str(script), '--config', str(config), '--apply'],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                     for _ in range(2)]
        for process in processes:
            process.stdin.write(json.dumps(self.payload))
            process.stdin.close()
            process.stdin = None
        reports = [json.loads(p.communicate(timeout=10)[0]) for p in processes]
        self.assertEqual(sorted(r['status'] for r in reports), ['saved', 'unchanged'])
        self.assertEqual(len(list((self.root/'archive').glob('*.md'))), 1)

    def test_recovery_after_import_before_receipt(self):
        import private_capture
        original = private_capture.run
        def interrupted(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError('synthetic interruption')
        with patch.object(private_capture, 'run', interrupted):
            with self.assertRaises(RuntimeError):
                capture(self.cfg, self.payload, True)
        self.assertEqual(capture(self.cfg, self.payload, True)['status'], 'unchanged')

    def test_gemini_hook_repeat_resume_and_gates(self):
        cfg = dict(self.cfg, host='gemini-cli', projects=[str(self.root)])
        config = self.root/'config.json'
        config.write_text(json.dumps(cfg))
        import os
        env = dict(os.environ, CONNECTED_KNOWLEDGE_GEMINI_CONFIG=str(config))
        hook = PLUGIN/'hooks/gemini_capture.py'
        event = {'hook_event_name': 'AfterAgent', 'session_id': 'fictional-session',
                 'cwd': str(self.root), 'timestamp': '2026-01-01T00:00:00Z',
                 'prompt': 'Fictional orchard?', 'prompt_response': 'Fictional pears.',
                 'stop_hook_active': False}
        def invoke(e):
            p = subprocess.run([sys.executable, str(hook)], input=json.dumps(e), text=True,
                               capture_output=True, env=env)
            self.assertEqual(p.stdout, '{}\n')
            self.assertEqual(p.returncode, 0, p.stderr)
        invoke(event)
        invoke(event)
        event['timestamp'] = '2026-01-01T00:01:00Z'
        invoke(event)
        self.assertEqual(len(list((self.root/'archive').glob('*.md'))), 2)
        event['cwd'] = str(self.root/'unselected')
        invoke(event)
        self.assertEqual(len(list((self.root/'archive').glob('*.md'))), 2)
        cfg['enabled'] = False
        config.write_text(json.dumps(cfg))
        invoke({'broken': 'ignored while disabled'})


if __name__ == '__main__':
    unittest.main()
