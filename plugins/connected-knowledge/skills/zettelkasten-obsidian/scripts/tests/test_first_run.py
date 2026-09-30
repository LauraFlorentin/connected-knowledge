import json
from pathlib import Path
import sys
import tempfile
import unittest
import subprocess
import zipfile
import yaml
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from first_run import save_setup
from starter_vault import create

class FirstRun(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.vault=self.root/'vault';self.vault.mkdir();(self.vault/'guide.md').write_text('User conventions')
        self.output=self.root/'setup';self.source=self.root/'history.json';self.source.write_text('[]')
        self.answers={'vault_mode':'existing','vault':str(self.vault),'vocabulary':'existing','ontology':'none',
                      'history':[{'source':str(self.source),'platform':'claude','account':'synthetic'}]}
    def tearDown(self):self.tmp.cleanup()
    def test_preview_has_no_writes(self):
        r=save_setup(self.answers,self.output)
        self.assertEqual(r['categories'],[]);self.assertFalse(self.output.exists())
        self.assertEqual(len(list(self.vault.iterdir())),1)
    def test_capture_plan_disabled_and_no_import(self):
        sessions=self.root/'sessions';sessions.mkdir()
        self.answers['capture']=[{'host':'codex','account':'synthetic','transcript_roots':[str(sessions)],'projects':[str(self.root)]}]
        save_setup(self.answers,self.output,True)
        cfg=json.loads((self.output/'capture-codex.json').read_text())
        self.assertFalse(cfg['enabled']);self.assertFalse(Path(cfg['spool']).exists())
        self.assertFalse((self.vault/'ChatArchive').exists())
        with self.assertRaises(ValueError):save_setup(self.answers,self.output,True)
    def test_inaccessible_existing_and_occupied_starter_rejected(self):
        self.answers['vault']=str(self.root/'missing')
        with self.assertRaises(ValueError):save_setup(self.answers,self.output,True)
        self.answers.update(vault=str(self.vault),vault_mode='starter')
        with self.assertRaises(ValueError):save_setup(self.answers,self.output,True)
        self.assertFalse(self.output.exists())
    def test_ontology_choices(self):
        self.answers['ontology']='default'
        self.assertEqual(save_setup(self.answers,self.output)['categories'],['Admin','Personal','Work'])
        self.answers.update(ontology='custom',categories=['Research'])
        self.assertEqual(save_setup(self.answers,self.output)['categories'],['Research'])
        self.answers['categories']=[]
        with self.assertRaises(ValueError):save_setup(self.answers,self.output)
    def test_runtime_inside_vault_rejected(self):
        with self.assertRaises(ValueError):save_setup(self.answers,self.vault/'setup',True)
    def test_starter_ontology_without_forced_personal(self):
        for ontology,categories in [('none',None),('custom',['Research'])]:
            dest=self.root/ontology;create(dest,True,ontology,categories)
            for path in (dest/'Templates').glob('*.md'):
                meta=yaml.safe_load(path.read_text().split('---')[1])
                self.assertNotIn('category',meta);self.assertNotIn('schema_version',meta)
            self.assertNotIn('Admin / Personal / Work',(dest/'VAULT-GUIDE.md').read_text())
        self.assertEqual((self.vault/'guide.md').read_text(),'User conventions')

    def test_synthetic_setup_bundle_starter_and_import_cli(self):
        source=self.root/'export.zip'
        with zipfile.ZipFile(source,'w') as z:
            z.writestr('conversations.json',json.dumps([{'uuid':'fictional','chat_messages':[{'uuid':'m','sender':'human','text':'Fictional garden question'}]}]))
            z.writestr('assets/reference.txt','Fictional attachment')
        self.answers.update(vault_mode='starter',vault=str(self.root/'new-vault'),history=[{
            'source':str(source),'platform':'claude','account':'synthetic',
            'conversation_member':'conversations.json','attachments':['assets/reference.txt']}])
        result=save_setup(self.answers,self.output,True)
        self.assertFalse((self.root/'new-vault').exists())
        for step in result['steps']:
            completed=subprocess.run(step['argv'],capture_output=True,text=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
        preview=result['steps'][-1]['argv']
        applied=subprocess.run([*preview,'--apply'],capture_output=True,text=True)
        self.assertEqual(applied.returncode,0,applied.stderr)
        self.assertEqual(json.loads(applied.stdout)['written'],1)
        repeat=subprocess.run([*preview,'--apply'],capture_output=True,text=True)
        self.assertEqual(json.loads(repeat.stdout)['written'],0)
        self.assertEqual((self.output/'bundle-1/files/assets/reference.txt').read_text(),'Fictional attachment')

    def test_reordered_history_uses_same_account_archive(self):
        other=self.root/'other.json';other.write_text('[]')
        self.answers['history'].append({'source':str(other),'platform':'claude','account':'synthetic'})
        first=save_setup(self.answers,self.output)['steps']
        self.assertEqual(first[-1]['argv'][3],first[-2]['argv'][3])

    def test_capture_cannot_scan_its_own_outputs(self):
        self.answers['capture']=[{'host':'codex','account':'synthetic','transcript_roots':[str(self.root)],'projects':[str(self.root)]}]
        with self.assertRaises(ValueError):save_setup(self.answers,self.output)

    def test_interactive_wizard_preview(self):
        from first_run import __file__ as script
        answers='\n'.join(['existing',str(self.vault),'existing','none','','n','n'])+'\n'
        result=subprocess.run([sys.executable,script,'--wizard','--output',str(self.output)],
                              input=answers,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Setup plan only',result.stdout);self.assertFalse(self.output.exists())

if __name__=='__main__':unittest.main()
