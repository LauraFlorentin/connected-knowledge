"""Release hygiene: versions, manifests, links, README coverage, private-data guard.

These checks read the source repository, so they skip inside an installed plugin.
"""
import json
from pathlib import Path
import re
import sys
import unittest
from urllib.parse import unquote

PLUGIN = Path(__file__).resolve().parents[4]
ROOT = PLUGIN.parents[1]
SOURCE = (ROOT/'tools/release_files.py').exists()
if SOURCE:
    sys.path.insert(0, str(ROOT/'tools'))
    import release_files

MANIFESTS = ('.claude-plugin/plugin.json', '.codex-plugin/plugin.json', 'plugin.json', 'gemini-extension.json')
LINK = re.compile(r'(?<!!)\[[^\]\n]*\]\((<[^>]+>|[^)\s]+)\)')


@unittest.skipUnless(SOURCE, 'source checkout only')
class Versions(unittest.TestCase):
    def test_manifests_agree(self):
        versions = {json.loads((PLUGIN/m).read_text())['version'] for m in MANIFESTS}
        self.assertEqual(versions, {release_files.manifest_version()})

    def test_every_current_version_string_matches_the_manifest(self):
        expected = release_files.manifest_version()
        for name, found in release_files.doc_versions().items():
            self.assertTrue(found, name + ' does not state the current version')
            self.assertEqual(set(found), {expected}, name)


@unittest.skipUnless(SOURCE, 'source checkout only')
class Manifests(unittest.TestCase):
    def test_claude_manifest_and_marketplace_shape(self):
        manifest = json.loads((PLUGIN/'.claude-plugin/plugin.json').read_text())
        for key in ('name', 'version', 'description', 'author', 'repository', 'homepage'):
            self.assertTrue(manifest.get(key), key)
        self.assertTrue(manifest['author'].get('name'))
        marketplace = json.loads((ROOT/'.claude-plugin/marketplace.json').read_text())
        self.assertTrue(marketplace.get('description'))
        self.assertEqual(marketplace['plugins'][0]['source'], './plugins/connected-knowledge')
        # Claude Code does not load a plugin-root CLAUDE.md; context ships in skills.
        self.assertFalse((PLUGIN/'CLAUDE.md').exists())
        self.assertFalse((ROOT/'docs/core-file-hashes.json').exists())

    def test_hooks_are_registered_but_inert_by_default(self):
        hooks = json.loads((PLUGIN/'hooks/hooks.json').read_text())['hooks']
        self.assertEqual(sorted(hooks), ['SessionEnd', 'SessionStart', 'Stop'])
        for entries in hooks.values():
            for hook in entries[0]['hooks']:
                self.assertEqual(hook['type'], 'command')
                self.assertIn('hooks/capture.py', hook['command'])
        example = json.loads((ROOT/'config/capture.disabled.json').read_text())
        self.assertIs(example['enabled'], False)


@unittest.skipUnless(SOURCE, 'source checkout only')
class Docs(unittest.TestCase):
    def documents(self):
        yield ROOT/'README.md'
        yield ROOT/'START-HERE.md'
        yield from sorted((ROOT/'docs').glob('*.md'))
        yield from sorted(PLUGIN.rglob('*.md'))

    def test_relative_links_resolve(self):
        broken = []
        for doc in self.documents():
            if 'review' in doc.parts or 'templates' in doc.parts or '__pycache__' in doc.parts:
                continue
            text = re.sub(r'^(```|~~~).*?^\1', '', doc.read_text(encoding='utf-8'), flags=re.M | re.S)
            text = re.sub(r'`[^`\n]*`', '', text)
            for match in LINK.finditer(text):
                target = match.group(1).strip('<>')
                if re.match(r'^[a-z][a-z0-9+.-]*:', target) or target.startswith('#'):
                    continue
                path = unquote(target.split('#')[0])
                if path and not (doc.parent/path).exists():
                    broken.append(doc.relative_to(ROOT).as_posix() + ' → ' + target)
        self.assertEqual(broken, [])

    def test_readme_architecture_names_every_host(self):
        readme = (ROOT/'README.md').read_text()
        section = readme.split('## Architecture', 1)[1]
        self.assertIn('```mermaid', section)
        for host in ('Claude Code', 'Codex', 'Gemini CLI', 'ChatGPT', 'Claude desktop', 'Gemini app', 'iPhone', 'Cowork'):
            self.assertIn(host, section, host)
        for command in ('/ck-setup', '/ck-help', '/ck-add-session', '$ck-setup'):
            self.assertIn(command, section)

    def test_readme_test_steps_state_python_310(self):
        readme = (ROOT/'README.md').read_text()
        self.assertIn('Python 3.10', readme.split('## Run the local tests', 1)[1].split('##', 1)[0])


@unittest.skipUnless(SOURCE, 'source checkout only')
class PrivateData(unittest.TestCase):
    def test_private_names_are_refused(self):
        for name in ('private-data/export.json', 'skills/x/conversations.json', 'a/session.jsonl', '.env',
                     'keys/id_ed25519'):
            self.assertTrue(release_files.is_private(name), name)
        for name in ('skills/zettelkasten-obsidian/SKILL.md', 'hooks/hooks.json', 'skills/ck-setup/SKILL.md'):
            self.assertFalse(release_files.is_private(name), name)

    def test_ignored_files_never_reach_a_package(self):
        probe = PLUGIN/'private-data/probe.json'
        probe.parent.mkdir(exist_ok=True)
        try:
            probe.write_text('{}')
            names = {name for _, name in release_files.plugin_files()}
            self.assertNotIn('private-data/probe.json', names)
            self.assertIn('skills/ck-setup/SKILL.md', names)
        finally:
            probe.unlink()
            probe.parent.rmdir()

    def test_gitignore_covers_private_data(self):
        ignored = (ROOT/'.gitignore').read_text().split()
        for entry in ('private-data/', '*.jsonl', 'conversations.json'):
            self.assertIn(entry, ignored)


if __name__ == '__main__':
    unittest.main()
