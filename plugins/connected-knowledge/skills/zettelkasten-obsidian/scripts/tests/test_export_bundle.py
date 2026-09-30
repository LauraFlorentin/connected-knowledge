import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from export_bundle import prepare

class ExportBundle(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.source=self.root/'export.zip';self.dest=self.root/'bundle'
        self.chat=json.dumps([{'uuid':'synthetic','chat_messages':[{'uuid':'m','sender':'human','text':'Fictional'}]}]).encode()
        self.build()
    def tearDown(self):self.tmp.cleanup()
    def build(self,extras=None):
        with zipfile.ZipFile(self.source,'w') as z:
            z.writestr('data/conversations.json',self.chat)
            z.writestr('attachments/a file.pdf',b'%PDF-synthetic-bytes')
            for n,v in extras or []:z.writestr(n,v)
    def run_bundle(self,apply=False):
        return prepare(self.source,self.dest,'data/conversations.json','claude',['attachments/a file.pdf'],apply)
    def test_inventory_and_preview_no_writes(self):
        self.assertEqual(len(prepare(self.source)['members']),2)
        self.assertEqual(self.run_bundle()['messages'],1)
        self.assertFalse(self.dest.exists())
    def test_preserves_bytes_and_repeat(self):
        self.assertTrue(self.run_bundle(True)['written'])
        self.assertEqual((self.dest/'original.zip').read_bytes(),self.source.read_bytes())
        self.assertEqual((self.dest/'conversations.json').read_bytes(),self.chat)
        self.assertEqual((self.dest/'files/attachments/a file.pdf').read_bytes(),b'%PDF-synthetic-bytes')
        self.assertIn('a%20file.pdf',(self.dest/'ATTACHMENTS.md').read_text())
        self.assertEqual(self.run_bundle(True)['mode'],'unchanged')
    def test_edit_and_missing_attachment_block_repeat(self):
        self.run_bundle(True)
        p=self.dest/'files/attachments/a file.pdf';p.write_bytes(b'Human edit')
        with self.assertRaises(ValueError):self.run_bundle(True)
        self.assertEqual(p.read_bytes(),b'Human edit');p.unlink()
        with self.assertRaises(ValueError):self.run_bundle(True)
    def test_unsafe_paths_and_collisions(self):
        for name in ['../escape','/absolute','a/../../b','a\\b','C:drive','a//b','a/./b','x\x01','x.','DATA/conversations.json']:
            with self.subTest(name=name):
                self.build([(name,b'x')])
                with self.assertRaises(ValueError):self.run_bundle(True)
                self.assertFalse(self.dest.exists())
        self.build([('parent',b'x'),('parent/child',b'x')])
        with self.assertRaises(ValueError):self.run_bundle(True)
    def test_symlink_member_and_output(self):
        info=zipfile.ZipInfo('linked');info.external_attr=(stat.S_IFLNK|0o777)<<16
        self.build([(info,b'/outside')])
        with self.assertRaises(ValueError):self.run_bundle(True)
        self.build();self.dest.symlink_to(self.root/'other')
        with self.assertRaises(ValueError):self.run_bundle(True)
    def test_limits_and_selection(self):
        with patch('export_bundle.MAX_BYTES',10):
            with self.assertRaises(ValueError):self.run_bundle(True)
        with patch('export_bundle.MAX_FILES',1):
            with self.assertRaises(ValueError):self.run_bundle(True)
        with self.assertRaises(ValueError):prepare(self.source,self.dest,apply=True)
        with self.assertRaises(ValueError):prepare(self.source,self.dest,'missing.json',apply=True)
        self.assertFalse(self.dest.exists())
    def test_injected_copy_failure_cleans_stage_and_retry(self):
        with patch('export_bundle.shutil.copyfile',side_effect=OSError('Synthetic disk failure')):
            with self.assertRaises(OSError):self.run_bundle(True)
        self.assertFalse(self.dest.exists());self.assertFalse(list(self.root.glob('.bundle*')))
        self.assertTrue(self.run_bundle(True)['written'])
    def test_existing_lock_not_removed(self):
        lock=self.root/'.bundle.bundle.lock';lock.write_text('Synthetic active writer')
        with self.assertRaises(FileExistsError):self.run_bundle(True)
        self.assertTrue(lock.exists());self.assertFalse(self.dest.exists())

if __name__=='__main__':unittest.main()
