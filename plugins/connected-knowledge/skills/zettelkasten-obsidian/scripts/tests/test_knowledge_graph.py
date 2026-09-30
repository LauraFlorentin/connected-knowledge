import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from chat_import import run
import knowledge_graph as graph
from vault_check import check


class KnowledgeGraph(unittest.TestCase):
    def test_symlink_vault_root_rejected(self):
        link=self.root/'redirect';link.symlink_to(self.vault,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'Symlink output'):
            graph.search(link,'Archive','')

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.vault=self.root/'vault';self.vault.mkdir()
        self.source=self.root/'export.json'
        self.source.write_text(json.dumps([{'id':'chat','title':'Herb garden','messages':[
            {'id':'question','role':'user','text':'Can mint grow in partial shade?'},
            {'id':'answer','role':'assistant','text':'This needs a gardening source.'}]}]))
        run(self.source,self.vault/'Archive','normalized','personal',True)
        self.hits=graph.search(self.vault,'Archive','mint')['results']
        hit=self.hits[0]
        self.plan={'version':1,'notes':[{'id':'shade-question','title':'Check mint light needs','kind':'idea',
              'category':'Personal','body':'Investigate the light requirements of mint. No botanical conclusion is established.',
              'evidence':[{'source':hit['source'],'source_sha256':hit['source_sha256'],
                           'message':hit['message'],'reason':'The user raised this question.'}]}]}
    def tearDown(self):self.tmp.cleanup()
    def apply(self,plan=None,**kwargs):
        return graph.apply_plan(self.vault,'Archive','Knowledge',self.plan if plan is None else plan,
                                categories=['Personal','Admin','Work'],**kwargs)
    def test_search_returns_exact_message_and_locator(self):
        self.assertEqual(len(self.hits),1)
        self.assertEqual(self.hits[0]['message'],'question')
        self.assertIn('#^msg-',self.hits[0]['citation'])
        self.assertEqual(graph.search(self.vault,'Archive','notfound')['results'],[])
        self.assertTrue(graph.search(self.vault,'Archive',limit=1)['truncated'])
    def test_preview_does_not_write(self):
        result=self.apply();self.assertEqual(result['items'][0]['action'],'created')
        self.assertFalse((self.vault/'Knowledge').exists())
    def test_apply_repeat_and_valid_message_links(self):
        before={p:p.read_bytes() for p in (self.vault/'Archive').rglob('*') if p.is_file()}
        self.assertEqual(self.apply(apply=True)['written'],1)
        self.assertEqual(self.apply(apply=True)['items'][0]['action'],'unchanged')
        self.assertEqual(check(self.vault,'generic')['errors'],0)
        self.assertEqual(check(self.vault,'generic')['warnings'],0)
        self.assertTrue(all(p.read_bytes()==data for p,data in before.items()))
    def test_existing_vocabulary_and_decision_remains_proposed(self):
        self.plan['notes'][0]['kind']='decision'
        self.apply(apply=True,vocabulary='existing')
        meta=yaml.safe_load((self.vault/'Knowledge/shade-question.md').read_text().split('---')[1])
        self.assertEqual(meta['type'],'decision');self.assertEqual(meta['status'],'auto')
        self.assertEqual(meta['decision_state'],'proposed');self.assertNotIn('note_type',meta)
    def test_links_to_existing_and_proposed_notes(self):
        (self.vault/'Gardening.md').write_text('# Gardening')
        other=copy.deepcopy(self.plan['notes'][0]);other.update(id='garden-map',kind='map',title='Garden questions')
        other['links']=[{'node':'shade-question','relation':'related','reason':'Open research question.'},
                        {'target':'Gardening.md','relation':'extends','reason':'Adds a question to the existing topic.'}]
        self.plan['notes'].append(other)
        report=self.apply(apply=True)
        self.assertEqual(report['written'],2);self.assertEqual(len(report['edges']),4)
        self.assertEqual(check(self.vault,'generic')['errors'],0)
    def test_missing_evidence_or_stale_source_rejected(self):
        for field,value in [('message','absent'),('source_sha256','old'),('source','missing')]:
            plan=copy.deepcopy(self.plan);plan['notes'][0]['evidence'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.apply(plan,apply=True)
        self.assertFalse((self.vault/'Knowledge').exists())
    def test_invalid_target_and_traversal_rejected(self):
        for target in ['missing.md','../outside.md','/tmp/note.md']:
            self.plan['notes'][0]['links']=[{'target':target,'relation':'related','reason':'Test.'}]
            with self.subTest(target=target),self.assertRaises(ValueError):self.apply(apply=True)
        self.assertFalse((self.vault/'Knowledge').exists())
    def test_human_edits_and_collisions_block(self):
        self.apply(apply=True)
        note=self.vault/'Knowledge/shade-question.md';note.write_text(note.read_text()+'\nHuman edit')
        self.plan['notes'][0]['body']='Revised proposal'
        self.assertEqual(self.apply(apply=True)['conflicts'],1)
        self.assertIn('Human edit',note.read_text())
    def test_update_retains_revision_and_omitted_nodes(self):
        self.apply(apply=True);note=self.vault/'Knowledge/shade-question.md';before=note.read_bytes()
        self.plan['notes'][0]['body']='A revised question, still unresolved.'
        self.assertEqual(self.apply(apply=True)['items'][0]['action'],'updated')
        self.assertEqual(next((self.vault/'Knowledge/.revisions').glob('*.md')).read_bytes(),before)
        self.apply({'version':1,'notes':[]},apply=True)
        self.assertTrue(note.exists())
    def test_symlink_target_rejected(self):
        outside=self.root/'outside.md';outside.write_text('Private')
        (self.vault/'Linked.md').symlink_to(outside)
        self.plan['notes'][0]['links']=[{'target':'Linked.md','relation':'related','reason':'Test'}]
        with self.assertRaises(ValueError):self.apply(apply=True)
    def test_source_change_during_render_blocks_writes(self):
        original=graph.sentence
        def change(value,label):
            if label=='Evidence explanation':
                p=next((self.vault/'Archive').glob('*.md'));p.write_text(p.read_text()+'Changed')
            return original(value,label)
        with patch.object(graph,'sentence',side_effect=change),self.assertRaises(ValueError):self.apply(apply=True)
        self.assertFalse((self.vault/'Knowledge/shade-question.md').exists())
    def test_invalid_category_and_unchecked_body_links(self):
        for key,value in [('category','Other'),('body','Unchecked [[missing]]')]:
            plan=copy.deepcopy(self.plan);plan['notes'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.apply(plan,apply=True)

if __name__=='__main__':unittest.main()
