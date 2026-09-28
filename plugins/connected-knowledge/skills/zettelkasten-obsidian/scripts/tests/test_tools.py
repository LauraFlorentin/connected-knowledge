import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from pypdf import PdfWriter
from reportlab.pdfgen import canvas

SCRIPTS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))
import collect
import extract_pdf
import vault_check
import starter_vault

def make_pdf(path,text='Fictional example: one small pilot cannot establish a universal improvement.'):
    c=canvas.Canvas(str(path)); c.drawString(50,750,text); c.showPage(); c.save()

class Tools(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def config(self,sources):
        p=self.root/'config.json'; p.write_text(json.dumps({'inbox':'inbox','ongoing_enabled':False,'sources':sources})); return p
    def test_pdf_pages_cache_integrity_and_scan(self):
        p=self.root/'source.pdf'; make_pdf(p); before=p.read_bytes()
        r=extract_pdf.extract(p,self.root/'out'); self.assertEqual(r['page_count'],1); self.assertEqual(r['status'],'text_extracted')
        self.assertEqual(p.read_bytes(),before); self.assertTrue(extract_pdf.extract(p,self.root/'out')['reused'])
        (Path(r['output_dir'])/'document.md').write_text('changed')
        with self.assertRaises(ValueError): extract_pdf.extract(p,self.root/'out')
        w=PdfWriter(); w.add_blank_page(100,100); scan=self.root/'blank.pdf'
        with scan.open('wb') as f: w.write(f)
        self.assertEqual(extract_pdf.extract(scan,self.root/'out')['status'],'needs_review')
    def test_image_only_scanned_pdf(self):
        from PIL import Image, ImageDraw
        from reportlab.lib.utils import ImageReader
        im=Image.new('RGB',(400,100),'white'); ImageDraw.Draw(im).text((10,20),'Image-only scanned fixture',fill='black')
        path=self.root/'scan.pdf'; c=canvas.Canvas(str(path)); c.drawImage(ImageReader(im),20,600,width=400,height=100); c.save()
        report=extract_pdf.extract(path,self.root/'out')
        self.assertEqual(report['pages'][0]['status'],'needs_visual_review')
        self.assertEqual(report['status'],'needs_review')
    def test_bad_and_encrypted_pdf(self):
        bad=self.root/'bad.pdf'; bad.write_bytes(b'not pdf')
        with self.assertRaises(ValueError): extract_pdf.extract(bad,self.root/'out')
        w=PdfWriter(); w.add_blank_page(100,100); w.encrypt('secret'); p=self.root/'encrypted.pdf'
        with p.open('wb') as f: w.write(f)
        with self.assertRaises(ValueError): extract_pdf.extract(p,self.root/'out')
    def test_collection_repeat_version_failure_and_no_schedule(self):
        p=self.root/'input.txt'; p.write_text('one')
        cfg=self.config([{'id':'local','kind':'local','enabled':True,'path':'input.txt'},{'id':'bad','kind':'local','enabled':True,'path':'absent'}])
        r=collect.run(cfg); self.assertEqual(r['counts']['captured'],1); self.assertEqual(r['counts']['failed'],1)
        self.assertEqual(collect.run(cfg)['counts']['duplicate'],1)
        p.write_text('two'); self.assertEqual(collect.run(cfg)['counts']['captured'],1)
        with self.assertRaises(ValueError): collect.run(cfg,scheduled=True)
        self.assertEqual(len(list((self.root/'inbox/records').glob('*.json'))),2)
    def test_feed_scope_cap_and_provenance(self):
        feed=b'<rss version="2.0"><channel><item><guid>x</guid><title>One</title><link>https://example.org/a</link></item><item><guid>y</guid><title>Two</title></item></channel></rss>'
        cfg=self.config([{'id':'feed','kind':'feed','enabled':True,'url':'https://example.org/feed','allowed_hosts':['example.org'],'max_items':1}])
        with patch.object(collect,'fetch',return_value=(feed,'https://example.org/feed','application/xml')):
            r=collect.run(cfg)
        self.assertEqual(r['counts']['captured'],1); self.assertEqual(r['counts']['incomplete'],1)
        meta=json.loads(next((self.root/'inbox/records').glob('*.json')).read_text())
        self.assertEqual(meta['coverage'],'feed_entry_only'); self.assertEqual(meta['source_ref'],'https://example.org/a')
    def test_atom_and_xml_entity_rejection(self):
        cfg=self.config([{'id':'atom','kind':'feed','enabled':True,'url':'https://example.org/feed','allowed_hosts':['example.org']}])
        atom=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>a</id><title>A</title><link href="https://example.org/a"/></entry></feed>'
        with patch.object(collect,'fetch',return_value=(atom,'https://example.org/feed','application/xml')): self.assertEqual(collect.run(cfg)['counts']['captured'],1)
        bad=b'<!DOCTYPE rss [<!ENTITY x "expansion">]><rss><channel><item><title>&x;</title></item></channel></rss>'
        with patch.object(collect,'fetch',return_value=(bad,'https://example.org/feed','application/xml')): self.assertEqual(collect.run(cfg)['counts']['failed'],1)
    def test_exclusion_missing_archive_and_lock(self):
        p=self.root/'a.txt'; p.write_text('x'); cfg=self.config([{'id':'a','kind':'local','enabled':True,'path':'a.txt'}])
        r=collect.run(cfg); identity=r['results'][0]['identity']
        raw=next((self.root/'inbox/raw').glob('*')); raw.unlink()
        self.assertEqual(collect.run(cfg)['counts']['failed'],1)
        c=json.loads(cfg.read_text()); c['excluded_ids']=[identity]; cfg.write_text(json.dumps(c))
        self.assertEqual(collect.run(cfg)['counts']['excluded'],1)
        (self.root/'inbox/.collector.lock').write_text('busy')
        with self.assertRaises(ValueError): collect.run(cfg)
    def test_private_url_and_disabled_sources(self):
        with self.assertRaises(ValueError): collect.validate_url('http://127.0.0.1/a',['127.0.0.1'])
        with self.assertRaises(ValueError): collect.validate_url('file:///etc/passwd',[])
        with self.assertRaises(ValueError): collect.run(self.config([]))
    def test_vault_findings_are_read_only(self):
        vault=self.root/'vault'; vault.mkdir(); make_pdf(vault/'paper.pdf')
        base='---\nschema_version: 1\nid: same\nnote_type: idea\ncategory: Work\ntitle: Test\n---\n'
        (vault/'A.md').write_text(base+'[[Missing]] [[paper.pdf#page=20]] [[B#Absent]]\n')
        (vault/'B.md').write_text(base+'# Exists\n')
        (vault/'C.md').write_text('---\nid: a\nid: b\n---\n')
        before={str(p):p.read_bytes() for p in vault.iterdir()}
        r=vault_check.check(vault); codes={x['code'] for x in r['findings']}
        self.assertTrue({'duplicate-id','broken-link','pdf-page','missing-anchor','yaml'}<=codes)
        self.assertEqual(before,{str(p):p.read_bytes() for p in vault.iterdir()})
    def test_metadata_mapping_and_source_drift(self):
        vault=self.root/'vault'; vault.mkdir()
        raw=vault/'source.txt'; raw.write_text('original')
        (vault/'A.md').write_text('---\nuid: stable\ntitle: A\nsource_file: source.txt\nsource_sha256: wrong\ntopics: [one]\n---\n')
        (vault/'B.md').write_text('---\nuid: stable\ntitle: B\ntopics: one\n---\n')
        result=vault_check.check(vault,'generic',{'fields':{'id':'uid'},'required':['id','title']})
        codes={x['code'] for x in result['findings']}
        self.assertTrue({'source-drift','inconsistent-type','duplicate-id'}<=codes)
    def test_generic_does_not_impose_schema_and_links(self):
        vault=self.root/'vault'; vault.mkdir()
        (vault/'Legacy.md').write_text('# Heading\n[[#Heading]]\n')
        self.assertEqual(vault_check.check(vault,'generic')['errors'],0)
        self.assertGreater(vault_check.check(vault,'zettelkasten')['errors'],0)
    def test_starter_requires_explicit_choice_and_absent_target(self):
        path=self.root/'new'
        with self.assertRaises(ValueError): starter_vault.create(path)
        self.assertFalse(path.exists()); starter_vault.create(path,True)
        self.assertFalse((path/'.obsidian').exists())
        with self.assertRaises(ValueError): starter_vault.create(path,True)
if __name__=='__main__': unittest.main()
