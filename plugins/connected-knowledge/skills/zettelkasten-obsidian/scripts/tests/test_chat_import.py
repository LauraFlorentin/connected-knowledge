import json
from pathlib import Path
import sys
import tempfile
import unittest
import yaml
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat_import import run, normalize


class ChatImport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root/'export.json'
        self.dest = self.root/'archive'
        self.data = [{'id':'c1','title':'A thought','messages':[{'id':'m1','role':'user','text':'Original thought'}]}]
        self.save()
    def tearDown(self): self.tmp.cleanup()
    def save(self): self.source.write_text(json.dumps(self.data))
    def run_import(self, **kw):
        return run(self.source,self.dest,'normalized','personal',**kw)
    def test_preview_is_read_only(self):
        report=self.run_import()
        self.assertEqual(report['created'],1)
        self.assertFalse(self.dest.exists())
    def test_repeat_and_revision_preserve_originals(self):
        self.assertEqual(self.run_import(apply=True)['written'],1)
        self.assertEqual(self.run_import(apply=True)['unchanged'],1)
        self.data[0]['messages'].append({'id':'m2','role':'assistant','text':'Reply'})
        self.save()
        self.assertEqual(self.run_import(apply=True)['updated'],1)
        self.assertEqual(len(list((self.dest/'originals').glob('*.json'))),2)
        self.assertEqual(len(list((self.dest/'revisions').glob('*.md'))),1)
    def test_human_edits_block_entire_batch(self):
        first=self.run_import(apply=True)
        note=self.dest/first['items'][0]['path']
        note.write_text(note.read_text()+'\nHuman addition')
        self.data.append({'id':'c2','messages':[]});self.save()
        report=self.run_import(apply=True)
        self.assertEqual(report['conflicts'],1)
        self.assertEqual(report['written'],0)
        self.assertIn('Human addition',note.read_text())
    def test_unrelated_export_change_does_not_rewrite_note(self):
        first=self.run_import(apply=True)
        note=self.dest/first['items'][0]['path'];before=note.read_bytes()
        self.data.append({'id':'c2','messages':[]});self.save()
        report=self.run_import(apply=True)
        self.assertEqual(report['unchanged'],1)
        self.assertEqual(before,note.read_bytes())
    def test_missing_ids_and_duplicate_ids_block_batch(self):
        for bad in ({'messages':[]},self.data[0]):
            self.data.append(bad);self.save()
            report=self.run_import(apply=True)
            self.assertEqual(report['failed'],1)
            self.assertEqual(report['written'],0)
            self.assertFalse(self.dest.exists())
            self.data.pop()
    def test_account_identity_separates_conversations(self):
        self.run_import(apply=True)
        report=run(self.source,self.dest,'normalized','work',apply=True)
        self.assertEqual(report['created'],1)
        self.assertEqual(len(list(self.dest.glob('*.md'))),2)
    def test_chatgpt_preserves_alternative_nodes(self):
        record={'id':'c','mapping':{
            'root':{'message':None},
            'a':{'parent':'root','message':{'author':{'role':'user'},'content':{'parts':['Question']}}},
            'b':{'parent':'a','message':{'author':{'role':'assistant'},'content':{'parts':['First answer']}}},
            'c':{'parent':'a','message':{'author':{'role':'assistant'},'content':{'parts':['Alternative',{'image':'x'}]}}}}}
        chat=normalize(record,'chatgpt')
        self.assertEqual(len(chat['messages']),3)
        self.assertEqual([m['parent'] for m in chat['messages']],['root','a','a'])
        self.assertIn('branches',chat['coverage'])
        self.assertTrue(chat['warnings'])
    def test_claude_text_and_attachments(self):
        chat=normalize({'uuid':'c','name':'Test','chat_messages':[{'uuid':'m','sender':'human','content':[{'type':'text','text':'Hello'}],'attachments':[{'name':'paper.pdf'}]}]},'claude')
        self.assertEqual(chat['messages'][0]['text'],'Hello')
        self.assertTrue(chat['warnings'])
    def test_ontology_optional_existing_vocabulary(self):
        result=self.run_import(apply=True,vocabulary='existing',categories=['Admin','Personal','Work'],annotations={'c1':{'category':'Personal'}})
        text=(self.dest/result['items'][0]['path']).read_text()
        meta=yaml.safe_load(text.split('---')[1])
        self.assertEqual(meta['type'],'reference');self.assertEqual(meta['status'],'auto')
        self.assertEqual(meta['category'],'Personal');self.assertNotIn('classification_status',meta)
    def test_invalid_classification_and_unresolved_links_block(self):
        for annotation in ({'category':'Other'},{'links':[{'target':'missing.md','reason':'related'}]}):
            report=self.run_import(apply=True,annotations={'c1':annotation},categories=['Personal'])
            self.assertEqual(report['failed'],1);self.assertFalse(self.dest.exists())
    def test_existing_directory_and_lock_are_preserved(self):
        self.dest.mkdir();(self.dest/'existing.md').write_text('Human note')
        with self.assertRaises(ValueError):self.run_import(apply=True)
        (self.dest/'existing.md').unlink();self.run_import(apply=True)
        (self.dest/'.import.lock').write_text('')
        self.data[0]['title']='Updated';self.save()
        with self.assertRaises(FileExistsError):self.run_import(apply=True)
        self.assertTrue((self.dest/'.import.lock').exists())

if __name__=='__main__':unittest.main()
