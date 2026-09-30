import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PLUGIN=Path(__file__).resolve().parents[4]

class BundledHooks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.config=self.root/'capture.json';self.transcript=self.root/'session.jsonl'
        self.cfg={'enabled':True,'host':'codex','account':'synthetic','projects':[str(self.root)],
                  'transcript_roots':[str(self.root)],'spool':str(self.root/'spool'),'destination':str(self.root/'archive')}
        self.event={'hook_event_name':'Stop','session_id':'synthetic','cwd':str(self.root),'transcript_path':str(self.transcript)}
        self.transcript.write_text(json.dumps({'type':'session_meta','payload':{'id':'synthetic','cwd':str(self.root)}})+'\n'+json.dumps({'type':'response_item','ordinal':1,'payload':{'type':'message','role':'user','content':'Fictional question'}})+'\n')
    def tearDown(self):self.tmp.cleanup()
    def invoke(self,host='codex',config=True,event=None,python=None):
        env={k:v for k,v in os.environ.items() if k not in ('PLUGIN_ROOT','CLAUDE_PLUGIN_ROOT') and not k.startswith('CONNECTED_KNOWLEDGE_')}
        env['CLAUDE_PLUGIN_ROOT']=str(PLUGIN)
        if host=='codex':env['PLUGIN_ROOT']=str(PLUGIN)
        if config:
            self.config.write_text(json.dumps(self.cfg))
            env['CONNECTED_KNOWLEDGE_CODEX_CONFIG' if host=='codex' else 'CONNECTED_KNOWLEDGE_CLAUDE_CODE_CONFIG']=str(self.config)
        env['CONNECTED_KNOWLEDGE_PYTHON']=python or sys.executable
        definition=json.loads((PLUGIN/'hooks/hooks.json').read_text())
        command=definition['hooks'][self.event['hook_event_name']][0]['hooks'][0]['command']
        return subprocess.run(command,shell=True,env=env,input=json.dumps(self.event) if event is None else event,capture_output=True,text=True)
    def test_absent_config_no_dependency_or_transcript_read(self):
        self.transcript.unlink()
        r=self.invoke(config=False,event='not JSON');self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(r.stdout,'{}\n');self.assertFalse((self.root/'spool').exists())
    def test_disabled_config_ignores_invalid_payload(self):
        self.cfg['enabled']=False;self.transcript.unlink()
        r=self.invoke(event='not JSON');self.assertEqual(r.returncode,0,r.stderr)
        self.assertFalse((self.root/'archive').exists())
    def test_codex_capture_and_sessionend_repeat(self):
        r=self.invoke();self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(r.stdout,'{}\n')
        self.event['hook_event_name']='SessionEnd';self.assertEqual(self.invoke().returncode,0)
        self.assertEqual(json.loads((self.root/'spool/last-result.json').read_text())['status'],'unchanged')
    def test_claude_capture(self):
        self.cfg['host']='claude-code'
        self.transcript.write_text(json.dumps({'type':'user','uuid':'m','sessionId':'synthetic','cwd':str(self.root),'message':{'role':'user','content':'Fictional'}})+'\n')
        r=self.invoke(host='claude-code');self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(len(list((self.root/'archive').glob('*.md'))),1)
    def test_host_mismatch_and_invalid_event_fail_nonblocking(self):
        self.cfg['host']='claude-code'
        r=self.invoke();self.assertEqual(r.returncode,1);self.assertEqual(r.stdout,'{}\n')
        self.assertNotIn(str(self.root),r.stderr);self.assertFalse((self.root/'spool').exists())
        self.cfg['host']='codex';self.event.pop('session_id')
        self.assertEqual(self.invoke().returncode,1)
    def test_unselected_project_and_subagent_do_not_read_transcript(self):
        self.transcript.unlink();self.cfg['projects']=[str(self.root/'other')]
        self.assertEqual(self.invoke().returncode,0)
        self.cfg['projects']=[str(self.root)];self.event['agent_id']='child'
        self.assertEqual(self.invoke().returncode,0)
    def test_dependency_failure_and_disabled_without_site_packages(self):
        # Run launcher with -S directly, bypassing site-packages (including PyYAML).
        env=dict(os.environ,PLUGIN_ROOT=str(PLUGIN),CLAUDE_PLUGIN_ROOT=str(PLUGIN),CONNECTED_KNOWLEDGE_CODEX_CONFIG=str(self.config))
        for enabled,code in [(False,0),(True,1)]:
            self.cfg['enabled']=enabled;self.config.write_text(json.dumps(self.cfg))
            r=subprocess.run([sys.executable,'-S',str(PLUGIN/'hooks/capture.py')],env=env,input=json.dumps(self.event),capture_output=True,text=True)
            self.assertEqual(r.returncode,code);self.assertEqual(r.stdout,'{}\n')
        self.assertFalse((self.root/'spool').exists())
    def test_failed_transcript_retry(self):
        raw=self.transcript.read_bytes();self.transcript.write_bytes(raw+b'{')
        self.assertEqual(self.invoke().returncode,1)
        self.transcript.write_bytes(raw);self.assertEqual(self.invoke().returncode,0)

if __name__=='__main__':unittest.main()
