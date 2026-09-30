import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import session_capture

class CaptureRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.file=self.root/'session.jsonl';self.cfg=self.root/'capture.json'
        self.config={'host':'codex','enabled':True,'account':'synthetic','projects':[str(self.root)],
                     'transcript_roots':[str(self.root)],'spool':str(self.root/'spool'),
                     'destination':str(self.root/'archive'),'vocabulary':'existing'}
        self.rows=[{'type':'session_meta','payload':{'id':'s','cwd':str(self.root)}},
                   {'type':'response_item','ordinal':1,'payload':{'type':'message','role':'user','content':'Fictional question'}}]
        self.save()
    def tearDown(self):self.tmp.cleanup()
    def save(self):
        self.file.write_text(''.join(json.dumps(r)+'\n' for r in self.rows))
        self.cfg.write_text(json.dumps(self.config))
    def hook(self,**kw):
        event={'hook_event_name':'Stop','session_id':'s','cwd':str(self.root),'transcript_path':str(self.file)}
        event.update(kw)
        return subprocess.run([sys.executable,str(Path(session_capture.__file__)),'--config',str(self.cfg),'--hook','--apply'],
                              input=json.dumps(event),capture_output=True,text=True)
    def test_real_cli_stop_sessionend_repeat_and_flush_retry(self):
        first=self.hook();self.assertEqual(first.returncode,0,first.stderr);self.assertEqual(json.loads(first.stdout),{})
        success=(self.root/'spool/last-result.json').read_bytes()
        failed=self.hook(last_assistant_message='Fictional reply')
        self.assertEqual(failed.returncode,1);self.assertEqual(json.loads(failed.stdout),{})
        self.assertEqual((self.root/'spool/last-result.json').read_bytes(),success)
        self.rows.append({'type':'response_item','ordinal':2,'payload':{'type':'message','role':'assistant','content':'Fictional reply'}});self.save()
        self.assertEqual(self.hook(last_assistant_message='Fictional reply').returncode,0)
        self.assertEqual(self.hook(hook_event_name='SessionEnd').returncode,0)
        self.assertEqual(json.loads((self.root/'spool/last-result.json').read_text())['status'],'unchanged')
        self.assertEqual(len(list((self.root/'archive').glob('*.md'))),1)
    def test_claude_code_cli_and_incomplete_retry(self):
        self.config['host']='claude-code'
        self.rows=[{'type':'user','uuid':'u','sessionId':'s','cwd':str(self.root),'message':{'role':'user','content':'Fictional'}},
                   {'type':'assistant','uuid':'a','parentUuid':'u','sessionId':'s','cwd':str(self.root),'message':{'role':'assistant','content':'Reply'}}]
        self.save();original=self.file.read_bytes();self.file.write_bytes(original+b'{')
        self.assertEqual(self.hook().returncode,1);self.assertFalse((self.root/'archive').exists())
        self.file.write_bytes(original)
        self.assertEqual(self.hook(last_assistant_message='Reply').returncode,0)
        self.assertEqual(self.hook().returncode,0)
    def test_checkpoint_failure_after_import_retries_without_duplicate(self):
        write=session_capture.atomic_write
        def fail_checkpoint(path,data):
            if path.parent==self.root/'spool' and path.name!='last-result.json':
                raise OSError('Synthetic checkpoint disk failure')
            return write(path,data)
        with patch('session_capture.atomic_write',side_effect=fail_checkpoint):
            with self.assertRaises(OSError):session_capture.capture(self.config,self.file,True)
        self.assertFalse((self.root/'spool/.capture.lock').exists())
        self.assertEqual(session_capture.capture(self.config,self.file,True)['status'],'unchanged')
        self.assertEqual(len(list((self.root/'archive').glob('*.md'))),1)
    def test_stale_or_live_locks_fail_closed(self):
        spool=self.root/'spool';spool.mkdir();lock=spool/'.capture.lock';lock.write_text('Synthetic active lock')
        self.assertEqual(self.hook().returncode,1);self.assertTrue(lock.exists())
        self.assertFalse((self.root/'archive').exists())
        # Test owns the synthetic lock; production recovery must first establish no live writer.
        lock.unlink();self.assertEqual(self.hook().returncode,0)
    def test_corrupt_normalized_snapshot_not_overwritten(self):
        session_capture.capture(self.config,self.file,True)
        snapshot=next((self.root/'spool/normalized').glob('*.json'));snapshot.write_text('Corruption')
        with self.assertRaisesRegex(ValueError,'Normalized snapshot integrity'):
            session_capture.capture(self.config,self.file,True)
        self.assertEqual(snapshot.read_text(),'Corruption')
    def test_interrupted_note_manifest_pair_preserves_note_for_reconciliation(self):
        import chat_import
        write=chat_import.atomic_write
        def fail_manifest(path,data):
            if path.name=='manifest.json':raise OSError('Synthetic interrupted manifest write')
            return write(path,data)
        with patch('chat_import.atomic_write',side_effect=fail_manifest):
            with self.assertRaises(OSError):session_capture.capture(self.config,self.file,True)
        note=next((self.root/'archive').glob('*.md'));before=note.read_bytes()
        with self.assertRaises(ValueError):session_capture.capture(self.config,self.file,True)
        self.assertEqual(note.read_bytes(),before)
        self.assertFalse((self.root/'spool/.capture.lock').exists())
        self.assertFalse((self.root/'archive/.import.lock').exists())

if __name__=='__main__':unittest.main()
