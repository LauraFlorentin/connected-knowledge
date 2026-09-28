import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import vault_check
import vault_compare
from vault_profile import file_inventory


class Profiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)/'vault'; self.root.mkdir()
        self.cfg = {'fields':{'note_type':'type','review_status':'status'},
                    'enums':{'review_status':['auto','reviewed']},
                    'roles':{'decision':{'identity':'decision_id'}},
                    'references':['workstream_id'], 'types':{'aliases':'string_list'}}
    def tearDown(self): self.tmp.cleanup()
    def note(self, name, text):
        p = self.root/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)
        return p
    def codes(self, cfg=None):
        return {x['code'] for x in vault_check.check(self.root,'generic',self.cfg if cfg is None else cfg)['findings']}
    def test_generic_local_states_and_types_without_schema(self):
        self.note('A.md','---\ntype: decision\nstatus: invalid\ndecision_id: D1\naliases: wrong\n---\n')
        self.assertTrue({'enum','property-type'} <= self.codes())
        self.assertNotIn('schema-version', self.codes())
    def test_scoped_identity_and_repeated_references(self):
        self.note('A.md','---\ntype: decision\ndecision_id: D1\nworkstream_id: 2\n---\n')
        self.note('B.md','---\ntype: decision\ndecision_id: D1\nworkstream_id: 2\n---\n')
        self.assertIn('duplicate-id', self.codes())
        self.note('B.md','---\ntype: decision\ndecision_id: D2\nworkstream_id: 2\n---\n')
        self.assertEqual(self.codes(), set())
    def test_identity_scopes_and_mapping(self):
        cfg = dict(self.cfg, fields={'note_type':'type','decision_id':'uid'},
                   roles={'decision':{'identity':'decision_id'}, 'entity':{'identity':'uid'}})
        self.note('A.md','---\ntype: decision\nuid: same\n---\n')
        self.note('B.md','---\ntype: entity\nuid: same\n---\n')
        self.assertNotIn('duplicate-id',self.codes(cfg))
    def test_role_required(self):
        self.cfg['roles']['decision']['required']=['decision_id']
        self.note('A.md','---\ntype: decision\n---\n')
        self.assertIn('required',self.codes())
    def test_custom_folder_detected_and_template_yaml_checked(self):
        self.note('.obsidian/templates.json',json.dumps({'folder':'Blueprints'}))
        self.note('Blueprints/A.md','---\ntitle: "{{title}}"\ndate: "{{date:YYYY-MM-DD}}"\n---\n')
        self.note('A.md','[[Blueprints/A]]')
        r = vault_check.check(self.root,'generic',self.cfg)
        self.assertEqual(r['files_checked'],1); self.assertEqual(len(r['templates']),1)
        self.assertEqual(r['errors'],0); self.assertIn('excluded-link',self.codes())
        self.note('Blueprints/Bad.md','---\na: [\n---\n')
        self.assertIn('template-yaml',self.codes())
    def test_blank_template_placeholders_and_unsupported_variables(self):
        self.cfg['template_folders']=['Blueprints']
        self.note('Blueprints/Decision.md','---\ntype: decision\ndecision_id:\nstatus:\n---\n{{uuid}}')
        r = vault_check.check(self.root,'generic',self.cfg)
        self.assertEqual(r['errors'],0); self.assertIn('template-variable',self.codes())
    def test_link_scopes_and_spaces(self):
        (self.root.parent/'outside file.md').write_text('outside')
        self.note('templates/T.md','template')
        self.note('A.md','[external](<../outside file.md>) [[templates/T]] [[Missing]]')
        r = vault_check.check(self.root,'generic')
        self.assertEqual(r['errors'],1)
        self.assertTrue({'external-link','excluded-link','broken-link'} <= {f['code'] for f in r['findings']})
    def test_comparison_preserves_hashes_and_exact_diffs(self):
        self.note('A.md','# Original'); other=self.root.parent/'other';other.mkdir()
        (other/'A.md').write_text('# Changed');(other/'B.md').write_text('# Added')
        before=file_inventory(self.root)
        r=vault_compare.compare(self.root,other,self.cfg)
        self.assertEqual(r['files']['changed'],['A.md']);self.assertEqual(r['files']['only_right'],['B.md'])
        self.assertTrue(r['left']['unchanged_during_check']); self.assertEqual(before,file_inventory(self.root))
    def test_concurrent_change_is_reported(self):
        self.note('A.md','# Original')
        original=vault_compare.check
        def changing(*args):
            result=original(*args);self.note('A.md','# Human edit');return result
        with patch.object(vault_compare,'check',side_effect=changing):
            r=vault_compare.inspect(self.root,self.cfg)
        self.assertFalse(r['unchanged_during_check'])
        self.assertEqual(r['changed_during_check']['changed'],['A.md'])
    def test_invalid_configuration_fails(self):
        for cfg in [{'types':{'status':'typo'}},{'enums':{'status':[]}},
                    {'roles':{'decision':{'identity':'workstream_id','references':['workstream_id']}}},
                    {'template_folders':['../outside']}]:
            with self.subTest(cfg=cfg), self.assertRaises(ValueError): vault_check.check(self.root,'generic',cfg)
    def test_symlink_target_is_outside_scope(self):
        target=self.root.parent/'outside.md';target.write_text('outside')
        (self.root/'Linked.md').symlink_to(target);self.note('A.md','[[Linked]]')
        self.assertIn('external-link',self.codes())
        self.assertNotIn('Linked.md',file_inventory(self.root))
    def test_short_excluded_link_and_ambiguity(self):
        self.note('templates/T.md', '# Template')
        self.note('A.md', '[[T]]')
        self.assertIn('excluded-link', self.codes())
        self.note('templates/sub/T.md', '# Other')
        self.assertIn('ambiguous-link', self.codes())
    def test_false_frontmatter_rejected(self):
        self.note('A.md', '---\nfalse\n---\n')
        self.assertIn('yaml', self.codes())
    def test_mapped_identity_reference_conflict_rejected(self):
        cfg = dict(self.cfg, fields={'id':'workstream_id'}, roles={'decision':{'identity':'id'}})
        with self.assertRaises(ValueError): vault_check.check(self.root, 'generic', cfg)
    def test_cli_exit_codes(self):
        self.note('A.md','[[Missing]]')
        command=[sys.executable,str(SCRIPTS/'vault_compare.py'),str(self.root)]
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,1);self.assertIn('validation',json.loads(result.stdout))
        result=subprocess.run(command+['--other-config','absent'],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)

if __name__ == '__main__': unittest.main()
