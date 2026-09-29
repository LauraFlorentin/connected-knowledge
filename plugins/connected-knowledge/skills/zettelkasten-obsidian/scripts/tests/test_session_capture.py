import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from session_capture import capture,parse_transcript

class SessionCapture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.source=self.root/'sessions';self.source.mkdir();self.file=self.source/'session.jsonl'
        self.config={'host':'codex','enabled':True,'account':'test','projects':[str(self.root)],
                     'transcript_roots':[str(self.source)],'spool':str(self.root/'spool'),
                     'destination':str(self.root/'archive'),'vocabulary':'existing'}
        self.rows=[{'type':'session_meta','payload':{'id':'session','cwd':str(self.root)}},
                   {'type':'response_item','ordinal':1,'payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'Hello'}]}}]
        self.save()
    def tearDown(self):self.tmp.cleanup()
    def save(self):self.file.write_text(''.join(json.dumps(r)+'\n' for r in self.rows))
    def test_preview_never_writes(self):
        self.assertEqual(capture(self.config,self.file)['status'],'preview')
        self.assertFalse((self.root/'spool').exists());self.assertFalse((self.root/'archive').exists())
    def test_repeat_append_and_raw_preservation(self):
        original=self.file.read_bytes()
        self.assertEqual(capture(self.config,self.file,True)['written'],1)
        self.assertEqual(capture(self.config,self.file,True)['status'],'unchanged')
        self.rows.append({'type':'response_item','ordinal':2,'payload':{'type':'message','role':'assistant','content':[{'type':'output_text','text':'Reply'}]}});self.save()
        self.assertEqual(capture(self.config,self.file,True)['written'],1)
        self.assertIn(original,[p.read_bytes() for p in (self.root/'spool/raw').glob('*')])
        self.assertEqual(len(list((self.root/'archive').glob('*.md'))),1)
    def test_disabled_and_project_exclusion(self):
        self.config['enabled']=False
        with self.assertRaises(ValueError):capture(self.config,self.file,True)
        self.config['projects']=[str(self.root/'other')]
        self.assertEqual(capture(self.config,self.file,True)['status'],'excluded')
        self.assertFalse((self.root/'spool').exists())
    def test_truncated_jsonl_rejected(self):
        self.file.write_text(self.file.read_text()+'{"type":')
        with self.assertRaises(ValueError):capture(self.config,self.file,True)
        self.assertFalse((self.root/'spool').exists())
    def test_shrinking_transcript_cannot_replace_archive(self):
        self.rows.append({'type':'response_item','ordinal':2,'payload':{'type':'message','role':'assistant','content':'Reply'}});self.save()
        capture(self.config,self.file,True)
        note=next((self.root/'archive').glob('*.md'));before=note.read_bytes()
        self.rows.pop();self.save()
        with self.assertRaises(ValueError):capture(self.config,self.file,True)
        self.assertEqual(note.read_bytes(),before)
    def test_hook_identity_and_final_message(self):
        event={'session_id':'wrong','cwd':str(self.root),'hook_event_name':'Stop'}
        with self.assertRaises(ValueError):capture(self.config,self.file,True,event)
        event['session_id']='session';event['last_assistant_message']='Not flushed'
        with self.assertRaises(ValueError):capture(self.config,self.file,True,event)
    def test_claude_code_uuid_parent_and_nontext(self):
        rows=[{'type':'user','uuid':'u','sessionId':'s','cwd':str(self.root),'message':{'role':'user','content':'Hello'}},
              {'type':'assistant','uuid':'a','parentUuid':'u','sessionId':'s','cwd':str(self.root),'message':{'role':'assistant','content':[{'type':'text','text':'Reply'},{'type':'tool_use','name':'shell'}]}}]
        chat,_,_=parse_transcript(('\n'.join(json.dumps(r) for r in rows)).encode(),'claude-code')
        self.assertEqual(chat['messages'][1]['parent'],'u');self.assertTrue(chat['capture_warnings'])
    def test_excludes_system_and_reasoning(self):
        self.rows.extend([{'type':'response_item','payload':{'type':'message','role':'developer','content':'Internal'}},
                          {'type':'response_item','payload':{'type':'reasoning','text':'Private reasoning'}}]);self.save()
        chat,_,_=parse_transcript(self.file.read_bytes(),'codex')
        self.assertEqual(len(chat['messages']),1)
    def test_outside_transcript_and_symlink_rejected(self):
        with self.assertRaises(ValueError):capture(self.config,self.root/'missing.jsonl',True)
        link=self.source/'linked.jsonl';link.symlink_to(self.file)
        with self.assertRaises(ValueError):capture(self.config,link,True)
    def test_history_preview_reports_failed_file_without_writes(self):
        (self.source/'broken.jsonl').write_text('{')
        cfg=self.root/'config.json';cfg.write_text(json.dumps(self.config))
        result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'session_capture.py'),'--config',str(cfg),'--history'],capture_output=True,text=True)
        report=json.loads(result.stdout)
        self.assertEqual(result.returncode,1);self.assertEqual(report['files'],2)
        self.assertEqual({r['status'] for r in report['results']},{'preview','failed'})
        self.assertFalse((self.root/'spool').exists())
    def test_archive_human_edit_is_not_overwritten(self):
        capture(self.config,self.file,True)
        note=next((self.root/'archive').glob('*.md'));note.write_text(note.read_text()+'Human edit')
        with self.assertRaises(ValueError):capture(self.config,self.file,True)
        self.assertTrue(note.read_text().endswith('Human edit'))
    def test_hook_failure_does_not_request_continuation(self):
        cfg=self.root/'config.json';cfg.write_text(json.dumps(self.config))
        result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'session_capture.py'),'--config',str(cfg),'--hook','--apply'],input='{}',capture_output=True,text=True)
        self.assertEqual(result.returncode,1);self.assertEqual(json.loads(result.stdout),{})
        self.assertIn('failed',result.stderr)

if __name__=='__main__':unittest.main()
