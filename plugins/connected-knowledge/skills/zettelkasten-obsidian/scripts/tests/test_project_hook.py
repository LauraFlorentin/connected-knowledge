import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from project_hook import setup


class ProjectHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.project = self.root / "project's notes $(ignored)"
        self.project.mkdir()
        self.config = self.root / 'private capture.json'
        self.cfg = {'host': 'codex', 'enabled': False, 'account': 'synthetic',
                    'projects': [str(self.project)], 'transcript_roots': [str(self.root)],
                    'spool': str(self.root/'spool'), 'destination': str(self.root/'archive')}
        self.config.write_text(json.dumps(self.cfg))
        self.target = self.project/'.codex/hooks.json'

    def tearDown(self):
        self.tmp.cleanup()

    def test_preview_merge_backup_repeat(self):
        old = {'description': 'Keep me', 'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'true'}]}]}}
        self.target.parent.mkdir()
        original = json.dumps(old).encode()
        self.target.write_bytes(original)
        result = setup(self.project, self.config)
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual(len(result['hook_configuration']['hooks']['Stop']), 2)
        result = setup(self.project, self.config, apply=True)
        self.assertEqual(Path(result['backup']).read_bytes(), original)
        saved = self.target.read_bytes()
        self.assertFalse(setup(self.project, self.config, apply=True)['changed'])
        self.assertEqual(self.target.read_bytes(), saved)
        self.assertFalse(json.loads(self.config.read_text())['enabled'])

    def test_generated_command_disabled_capture_repeat_and_recovery(self):
        command = setup(self.project, self.config)['hook_configuration']['hooks']['Stop'][0]['hooks'][0]['command']
        env = {k:v for k,v in os.environ.items() if not k.startswith('CONNECTED_KNOWLEDGE_') and k not in ('PLUGIN_ROOT','CLAUDE_PLUGIN_ROOT')}
        def run(payload):
            return subprocess.run(command, shell=True, env=env, input=payload, text=True, capture_output=True, cwd=self.project)
        self.assertEqual(run('not JSON').returncode, 0)
        self.assertFalse((self.root/'archive').exists())
        transcript = self.root/'test.jsonl'
        records = [{'type':'session_meta','payload':{'id':'synthetic','cwd':str(self.project)}},
                   {'type':'response_item','ordinal':1,'payload':{'type':'message','role':'user','content':'Fictional question'}},
                   {'type':'response_item','ordinal':2,'payload':{'type':'message','role':'assistant','content':'Fictional answer'}}]
        raw = '\n'.join(map(json.dumps,records))+'\n'
        transcript.write_text(raw)
        self.cfg['enabled'] = True
        self.config.write_text(json.dumps(self.cfg))
        event = json.dumps({'hook_event_name':'Stop','session_id':'synthetic','cwd':str(self.project),'transcript_path':str(transcript)})
        result = run(event)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(run(event).returncode, 0)
        self.assertEqual(len(list((self.root/'archive').glob('*.md'))), 1)
        transcript.write_text(raw+'{')
        self.assertEqual(run(event).returncode, 1)
        transcript.write_text(raw)
        self.assertEqual(run(event).returncode, 0)

    def test_refuses_enabled_wrong_scope_symlink_and_conflict(self):
        self.cfg['enabled'] = True
        self.config.write_text(json.dumps(self.cfg))
        with self.assertRaises(ValueError): setup(self.project, self.config, apply=True)
        self.cfg['enabled'] = False
        self.cfg['projects'] = []
        self.config.write_text(json.dumps(self.cfg))
        with self.assertRaises(ValueError): setup(self.project, self.config, apply=True)
        self.cfg['projects'] = [str(self.project)]
        self.config.write_text(json.dumps(self.cfg))
        self.target.parent.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): setup(self.project, self.config, apply=True)
        self.target.parent.unlink()
        self.target.parent.mkdir()
        self.target.write_text(json.dumps({'hooks':{'Stop':[{'hooks':[{'type':'command','command':'python other/hooks/capture.py'}]}]}}))
        original = self.target.read_bytes()
        with self.assertRaises(ValueError): setup(self.project, self.config, apply=True)
        self.assertEqual(self.target.read_bytes(), original)

    def test_invalid_existing_json_preserved(self):
        self.target.parent.mkdir()
        self.target.write_text('{broken')
        with self.assertRaises(ValueError): setup(self.project, self.config, apply=True)
        self.assertEqual(self.target.read_text(), '{broken')

if __name__ == '__main__': unittest.main()
