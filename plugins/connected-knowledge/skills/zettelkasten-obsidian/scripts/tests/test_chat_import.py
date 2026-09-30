import json
from pathlib import Path
import sys
import tempfile
import unittest
import yaml
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat_import import run, normalize, digest, encoded


class ChatImport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
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
    def test_claude_export_reply_branches_round_trip(self):
        # Entirely synthetic values; no exported user data is a test fixture.
        self.data = [{'uuid':'synthetic-chat','name':'Fictional conversation',
            'summary':'Synthetic summary','account':{'uuid':'synthetic-account'},
            'created_at':'2025-01-01T00:00:00Z','updated_at':'2025-01-01T00:03:00Z',
            'chat_messages':[
                {'uuid':'question','sender':'human','text':'Fictional question',
                 'content':[], 'attachments':[], 'files':[],
                 'parent_message_uuid':'root-placeholder'},
                {'uuid':'answer-one','sender':'assistant','text':'',
                 'content':[{'type':'text','text':'First fictional answer',
                             'flags':None,'citations':[],
                             'start_timestamp':'2025-01-01T00:01:00Z',
                             'stop_timestamp':'2025-01-01T00:02:00Z'}],
                 'parent_message_uuid':'question'},
                {'uuid':'answer-two','sender':'assistant','text':'Alternative answer',
                 'content':[{'type':'text','text':'Alternative answer'}],
                 'parent_message_uuid':'question'}]}]
        self.save()
        chat = normalize(self.data[0], 'claude')
        self.assertEqual([m['parent'] for m in chat['messages']],
                         ['root-placeholder','question','question'])
        self.assertEqual(chat['messages'][1]['text'], 'First fictional answer')
        self.assertEqual(chat['messages'][2]['text'], 'Alternative answer')
        preview = run(self.source,self.dest,'claude','synthetic')
        self.assertEqual(preview['created'],1)
        self.assertFalse(self.dest.exists())
        result = run(self.source,self.dest,'claude','synthetic',apply=True)
        note = (self.dest/result['items'][0]['path']).read_text()
        self.assertEqual(note.count('"parent": "question"'),2)
        self.assertEqual(next((self.dest/'originals').glob('*.json')).read_bytes(),
                         self.source.read_bytes())
        self.assertEqual(run(self.source,self.dest,'claude','synthetic',apply=True)['unchanged'],1)

    def test_claude_parent_field_precedence_and_legacy_fallback(self):
        for fields, expected in [({'parent':'legacy'},'legacy'),
                                  ({'parent_message_uuid':None,'parent':'legacy'},None),
                                  ({'parent_message_uuid':'native','parent':'legacy'},'native')]:
            message = dict(uuid='message',sender='human',text='Synthetic',**fields)
            record = {'uuid':'conversation','chat_messages':[message]}
            self.assertEqual(normalize(record,'claude')['messages'][0]['parent'],expected)
        record = {'id':'conversation','messages':[dict(id='message',text='Synthetic',
                  parent='normalized-parent',parent_message_uuid='unrelated')]}
        self.assertEqual(normalize(record,'normalized')['messages'][0]['parent'],'normalized-parent')

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

    def test_missing_or_changed_original_blocks_repeat(self):
        self.run_import(apply=True)
        original = next((self.dest/'originals').glob('*.json'))
        original.write_text('changed')
        report = self.run_import(apply=True)
        self.assertEqual(report['failed'], 1)
        self.assertEqual(report['written'], 0)
        self.assertEqual(original.read_text(), 'changed')
        original.unlink()
        report = self.run_import(apply=True)
        self.assertEqual(report['failed'], 1)
        self.assertEqual(report['unchanged'], 0)
        self.assertFalse(original.exists())

    def test_symlink_destination_and_parent_rejected(self):
        outside=self.root/'outside';outside.mkdir()
        link=self.root/'redirect';link.symlink_to(outside,target_is_directory=True)
        for dest in (link,link/'archive'):
            with self.assertRaisesRegex(ValueError,'Symlink output'):
                run(self.source,dest,'normalized','synthetic',apply=True)
        self.assertEqual(list(outside.iterdir()),[])

    def test_format_upgrade_refreshes_legacy_reply_metadata_once(self):
        self.data=[{'uuid':'c','chat_messages':[{'uuid':'m','sender':'human','text':'Synthetic','parent_message_uuid':'root'}]}]
        self.save()
        result=run(self.source,self.dest,'claude','synthetic',apply=True)
        note=self.dest/result['items'][0]['path']
        note.write_text(note.read_text().replace('"parent": "root"','"parent": null'))
        old_note=note.read_bytes()
        path=self.dest/'manifest.json';state=json.loads(path.read_text())
        for entry in state['records'].values():
            entry['sha256']=digest(old_note)
            entry['fingerprint']=digest(encoded([self.data[0],{},'default',None]))
        path.write_bytes(encoded(state))
        self.assertEqual(run(self.source,self.dest,'claude','synthetic')['updated'],1)
        self.assertEqual(note.read_bytes(),old_note)
        self.assertEqual(run(self.source,self.dest,'claude','synthetic',apply=True)['updated'],1)
        self.assertIn('"parent": "root"',note.read_text())
        self.assertEqual(next((self.dest/'revisions').glob('*.md')).read_bytes(),old_note)
        self.assertEqual(run(self.source,self.dest,'claude','synthetic',apply=True)['unchanged'],1)
        note.write_text(note.read_text()+'Human edit')
        self.assertEqual(run(self.source,self.dest,'claude','synthetic',apply=True)['conflicts'],1)

    def test_legacy_manifest_original_is_verified(self):
        self.run_import(apply=True)
        manifest = self.dest/'manifest.json'
        state = json.loads(manifest.read_text())
        for entry in state['records'].values(): entry.pop('original')
        manifest.write_text(json.dumps(state))
        self.assertEqual(self.run_import(apply=True)['unchanged'], 1)
        next((self.dest/'originals').glob('*.json')).unlink()
        self.assertEqual(self.run_import(apply=True)['failed'], 1)

if __name__=='__main__':unittest.main()
