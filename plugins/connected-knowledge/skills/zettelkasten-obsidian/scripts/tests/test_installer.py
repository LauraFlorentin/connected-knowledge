import hashlib
import asyncio
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runtime_install as installer
from install_host import configure
from install_support import runtime_lock
from install_dependencies import install_node, unpack_node


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.runtime = self.root/'Private Runtime'
        self.vault = self.root/'Existing Vault'
        self.vault.mkdir()
        self.guide = self.vault/'Vault Guide.md'
        self.guide.write_text('Preserve human notes.')
        self.answers = {'runtime': str(self.runtime), 'private': {'vault': str(self.vault),
                        'account': 'fictional', 'tunnel_id': 'tunnel_' + '0'*32}}
        self.build = patch('install_dependencies.build', side_effect=self.fake_build).start()
        self.real_validate = installer.validate_generation
        self.validate = patch('runtime_install.validate_generation').start()
        self.addCleanup(patch.stopall)

    def fake_build(self, generation, private, filesystem):
        (generation/'venv/bin').mkdir(parents=True)
        python = generation/'venv/bin/python'
        python.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' "$@"\n')
        python.chmod(0o700)
        if private:
            (generation/'bin').mkdir()
            (generation/'bin/tunnel-client').write_text('synthetic binary')
        return {'python': 'synthetic test environment'}

    def test_preview_never_creates_downloads_or_reads_vault_notes(self):
        result = installer.install(self.answers)
        self.assertEqual(result['mode'], 'preview')
        self.assertFalse(result['starts_connection'])
        self.assertFalse(self.runtime.exists())
        self.build.assert_not_called()
        self.assertEqual(self.guide.read_text(), 'Preserve human notes.')

    def test_fresh_install_repeat_and_stable_entrypoint(self):
        first = installer.install(self.answers, True)
        self.assertEqual(first['mode'], 'installed')
        before = (self.runtime/'capture-config.json').read_bytes()
        repeat = installer.install(self.answers, True)
        self.assertEqual(repeat['mode'], 'unchanged')
        self.assertEqual(self.build.call_count, 1)
        self.assertEqual(before, (self.runtime/'capture-config.json').read_bytes())
        self.assertFalse((self.vault/'Inbox').exists())
        launched = subprocess.run([sys.executable, str(self.runtime/'scripts/private_runtime.py'),
                                   'status', '--runtime', str(self.runtime)], capture_output=True, text=True)
        self.assertEqual(launched.returncode, 0, launched.stdout + launched.stderr)
        self.assertEqual(json.loads(launched.stdout)['state'], 'offline')

    def test_update_preserves_settings_templates_profiles_and_state(self):
        first = installer.install(self.answers, True)
        files = {'capture-template.md': b'Human custom template', 'profiles/private.yaml': b'Keep tunnel identity',
                 'spool/example.json': b'Private capture state', 'vault-bridge-state/receipt.json': b'Previous note bytes'}
        for name, data in files.items():
            target = self.runtime/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        files.update({name: (self.runtime/name).read_bytes() for name in ('capture-config.json', 'runtime.json')})
        payload = {**installer.source_files(), 'scripts/new-version.py': b'# New release\n'}
        with patch('runtime_install.source_files', return_value=payload):
            updated = installer.install({'runtime': str(self.runtime)}, True)
        self.assertNotEqual(first['generation'], updated['generation'])
        self.assertEqual(updated['previous_generation'], first['generation'])
        self.assertTrue((self.runtime/'releases'/first['generation']).is_dir())
        for name, data in files.items():
            self.assertEqual((self.runtime/name).read_bytes(), data, name)

    def test_legacy_runtime_upgrades_without_recreating_identity(self):
        self.runtime.mkdir()
        (self.runtime/'scripts').mkdir()
        (self.runtime/'scripts/private_runtime.py').write_text('# old entrypoint\n')
        (self.runtime/'scripts/capture_mcp.py').write_text('# old capture\n')
        (self.runtime/'venv/bin').mkdir(parents=True)
        (self.runtime/'venv/bin/python').symlink_to(sys.executable)
        cfg = {'enabled': False, 'account': 'old-owner', 'spool': str(self.runtime/'spool'),
               'destination': str(self.vault/'Old Archive'), 'custom': {'retain': True}}
        raw = json.dumps(cfg, indent=4).encode() + b'\n\n'
        (self.runtime/'capture-config.json').write_bytes(raw)
        (self.runtime/'runtime.json').write_text('{"version":1,"tunnel_id":"tunnel_' + '1'*32 + '"}')
        result = installer.install({'runtime': str(self.runtime)}, True)
        self.assertEqual((self.runtime/'capture-config.json').read_bytes(), raw)
        self.assertEqual((Path(result['backup'])/'private_runtime.py').read_text(), '# old entrypoint\n')

    def test_download_or_validation_failure_does_not_select_new_generation(self):
        first = installer.install(self.answers, True)
        pointer = (self.runtime/installer.CURRENT).read_bytes()
        payload = {**installer.source_files(), 'scripts/new-version.py': b'# new\n'}
        with patch('runtime_install.source_files', return_value=payload):
            for collaborator in (self.build, self.validate):
                original = collaborator.side_effect
                collaborator.side_effect = RuntimeError('Synthetic failure')
                with self.assertRaises(RuntimeError):
                    installer.install({'runtime': str(self.runtime)}, True)
                collaborator.side_effect = original
                self.assertEqual((self.runtime/installer.CURRENT).read_bytes(), pointer)
                self.assertFalse((self.runtime/'install-pending.json').exists())

    def test_concurrent_private_edit_prevents_switch(self):
        installer.install(self.answers, True)
        pointer = (self.runtime/installer.CURRENT).read_bytes()
        payload = {**installer.source_files(), 'scripts/new-version.py': b'# new\n'}
        def edit(*_args):
            cfg = json.loads((self.runtime/'capture-config.json').read_text())
            cfg['human_setting'] = 'Keep this'
            (self.runtime/'capture-config.json').write_text(json.dumps(cfg))
        self.validate.side_effect = edit
        with patch('runtime_install.source_files', return_value=payload), self.assertRaisesRegex(ValueError, 'changed'):
            installer.install({'runtime': str(self.runtime)}, True)
        self.assertEqual((self.runtime/installer.CURRENT).read_bytes(), pointer)
        self.assertIn('human_setting', (self.runtime/'capture-config.json').read_text())

    def test_busy_and_live_runtime_refuse_upgrade(self):
        self.runtime.mkdir()
        with runtime_lock(self.runtime, shared=True), self.assertRaisesRegex(ValueError, 'busy'):
            # Recognize a folder initialized by this installer.
            (self.runtime/'install-owner.json').write_text(json.dumps({'owner': installer.OWNER, 'runtime': str(self.runtime)}))
            installer.install(self.answers, True)
        with patch('private_runtime.status', return_value={'live': True}), self.assertRaisesRegex(ValueError, 'Stop'):
            installer.install(self.answers, True)
        self.build.assert_not_called()

    def test_interrupted_publication_is_detected_and_retry_completes(self):
        real_atomic = installer.atomic
        def interrupt(file, *args, **kwargs):
            if file == self.runtime/installer.CURRENT:
                raise OSError('Synthetic interruption before switch')
            return real_atomic(file, *args, **kwargs)
        with patch('runtime_install.atomic', side_effect=interrupt), self.assertRaises(OSError):
            installer.install(self.answers, True)
        self.assertTrue((self.runtime/'install-pending.json').exists())
        launched = subprocess.run([sys.executable, str(self.runtime/'scripts/private_runtime.py'),
                                   'status', '--runtime', str(self.runtime)], capture_output=True, text=True)
        self.assertNotEqual(launched.returncode, 0)
        self.assertIn('interrupted', launched.stderr)
        result = installer.install(self.answers, True)
        self.assertEqual(result['mode'], 'installed')
        self.assertFalse((self.runtime/'install-pending.json').exists())

    def test_foreign_destinations_scope_and_symlinks_are_rejected(self):
        self.runtime.mkdir()
        (self.runtime/'personal.txt').write_text('Keep')
        with self.assertRaisesRegex(ValueError, 'Occupied'):
            installer.install(self.answers, True)
        self.assertEqual((self.runtime/'personal.txt').read_text(), 'Keep')
        self.answers['runtime'] = str(self.vault/'Runtime')
        with self.assertRaises(ValueError):
            installer.install(self.answers, True)
        redirected = self.root/'Redirected'
        redirected.mkdir()
        (redirected/'releases').symlink_to(self.vault)
        self.answers['runtime'] = str(redirected)
        with self.assertRaises(ValueError):
            installer.install(self.answers, True)
        self.assertEqual([p.name for p in self.vault.iterdir()], ['Vault Guide.md'])

    def test_filesystem_host_registration_failure_is_retryable(self):
        host = self.root/'config.toml'
        host.write_text('[mcp_servers.connected-knowledge-filesystem]\ncommand="different"\n')
        answers = {'runtime': str(self.runtime), 'filesystem': {'host': 'codex', 'directories': [str(self.vault)],
                   'register': True, 'host_config': str(host)}}
        result = installer.install(answers, True)
        self.assertEqual(result['host_connection']['status'], 'pending')
        self.assertIn('different', host.read_text())
        host.write_text('# Personal settings\nmodel="unchanged"\n')
        result = installer.install(answers, True)
        self.assertEqual(result['mode'], 'unchanged')
        self.assertEqual(result['host_connection']['status'], 'registered')
        self.assertEqual(self.build.call_count, 1)
        self.assertIn('# Personal settings', host.read_text())

    def test_ck_setup_filesystem_answers_match_installer(self):
        # /ck-setup documents this answers file for Claude desktop chat; keep it valid.
        skill = (Path(__file__).resolve().parents[3]/'ck-setup/SKILL.md').read_text()
        block = skill.split('## Filesystem answers file', 1)[1].split('```json', 1)[1].split('```', 1)[0]
        answers = json.loads(block.replace('/Users/me', str(self.root)))
        (self.root/'Vaults/My Vault').mkdir(parents=True)
        host = Path(answers['filesystem']['host_config'])
        host.parent.mkdir(parents=True)
        host.write_text('{"theme":"dark","mcpServers":{"other":{"command":"unchanged"}}}')
        preview = installer.install(answers)
        self.assertEqual(preview['mode'], 'preview')
        self.assertFalse(Path(answers['runtime']).exists())
        self.assertNotIn('connected-knowledge-filesystem', host.read_text())
        result = installer.install(answers, True)
        self.assertEqual(result['host_connection']['status'], 'registered')
        settings = json.loads(host.read_text())
        self.assertEqual(settings['theme'], 'dark')
        self.assertEqual(settings['mcpServers']['other'], {'command': 'unchanged'})
        self.assertIn('connected-knowledge-filesystem', settings['mcpServers'])
        self.assertFalse(list((self.root/'Vaults/My Vault').iterdir()))

    def test_cli_update_preview_and_wizard_do_not_install(self):
        installer.install(self.answers, True)
        script = Path(installer.__file__).with_name('install.py')
        result = subprocess.run([sys.executable, str(script), '--runtime', str(self.runtime)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['mode'], 'preview')
        result = subprocess.run([sys.executable, str(script), '--wizard'],
                                input=str(self.runtime)+'\nn\nn\nn\n', capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Nothing installed', result.stdout)

    def test_real_candidate_validation_and_invalid_template_prevent_switch(self):
        self.validate.side_effect = self.real_validate
        template = self.vault/'Template.md'
        template.write_text('---\ntype: reference\nstatus: auto\n---\n# {{title}}\n\n{{capture}}\n')
        self.answers['private']['template'] = str(template)
        installer.install(self.answers, True)
        pointer = (self.runtime/installer.CURRENT).read_bytes()
        template.write_text('{{execute:unsupported}}')
        changed = {**installer.source_files(), 'scripts/new-version.py': b'# update\n'}
        with patch('runtime_install.source_files', return_value=changed), self.assertRaisesRegex(ValueError, 'validation'):
            installer.install({'runtime': str(self.runtime)}, True)
        self.assertEqual((self.runtime/installer.CURRENT).read_bytes(), pointer)
        self.assertEqual(template.read_text(), '{{execute:unsupported}}')
        self.assertFalse((self.vault/'Inbox').exists())

    def test_legacy_save_survives_upgrade_through_actual_stdio_launcher(self):
        from private_setup import setup
        from private_capture import capture
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        with patch('private_setup.venv.EnvBuilder'):
            setup(self.runtime, self.vault, 'tunnel_'+'0'*32, 'fictional', apply=True)
        (self.runtime/'venv/bin').mkdir(parents=True)
        (self.runtime/'venv/bin/python').symlink_to(sys.executable)
        cfg_path = self.runtime/'capture-config.json'
        cfg = json.loads(cfg_path.read_text())
        args = {'source': 'chatgpt', 'conversation_id': 'existing-chat', 'capture_id': 'one',
                'title': 'Original source', 'coverage': 'excerpt',
                'messages': [{'id': 'm1', 'role': 'user', 'text': 'Synthetic migration trial.'}]}
        self.assertEqual(capture(cfg, args, True)['written'], 1)
        original = {p: p.read_bytes() for p in self.vault.rglob('*') if p.is_file()}
        config_bytes = cfg_path.read_bytes()
        self.validate.side_effect = self.real_validate
        installer.install({'runtime': str(self.runtime)}, True)
        self.assertEqual(cfg_path.read_bytes(), config_bytes)
        async def exercise():
            params = StdioServerParameters(command=str(self.runtime/'venv/bin/python'),
                args=[str(self.runtime/'scripts/capture_mcp.py')],
                env=dict(os.environ, CONNECTED_KNOWLEDGE_PRIVATE_CONFIG=str(cfg_path)))
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    retry = await session.call_tool('save_selected_capture', args)
                    self.assertFalse(retry.isError)
                    self.assertEqual(json.loads(retry.content[0].text)['status'], 'unchanged')
                    for file, content in original.items():
                        self.assertEqual(file.read_bytes(), content)
                    new = {**args, 'capture_id': 'two', 'title': 'New source'}
                    saved = await session.call_tool('save_selected_capture', new)
                    self.assertFalse(saved.isError)
                    self.assertEqual(json.loads(saved.content[0].text)['status'], 'saved')
        asyncio.run(exercise())
        for file, content in original.items():
            if file.suffix == '.md':
                self.assertEqual(file.read_bytes(), content)
        self.assertEqual(len(list(Path(cfg['destination']).glob('*.md'))), 2)


class HostAndDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.connection = {'command': '/private/runtime/venv/bin/python', 'args': ['/private/runtime/scripts/filesystem_mcp.py']}

    def test_host_merges_preserve_unrelated_options_and_reuse_selected_entry(self):
        for host, content, name in [('codex', '# Keep this comment\nmodel="chosen"\n[mcp_servers.other]\nurl="https://example.invalid"\n', 'config.toml'),
                                    ('claude-desktop', '{"theme":"dark","mcpServers":{"other":{"command":"unchanged"}}}', 'claude_desktop_config.json')]:
            target = self.root/name
            target.write_text(content)
            configure(host, target, 'selected', self.connection)
            self.assertEqual(target.read_text(), content)
            result = configure(host, target, 'selected', self.connection, True)
            self.assertEqual(Path(result['backup']).read_text(), content)
            self.assertIn('other', target.read_text())
            after = target.read_bytes()
            self.assertEqual(configure(host, target, 'selected', self.connection, True)['status'], 'reused')
            self.assertEqual(target.read_bytes(), after)
            with self.assertRaises(ValueError):
                configure(host, target, 'selected', {'command': 'different', 'args': []}, True)
            self.assertEqual(target.read_bytes(), after)

    def test_low_disk_space_stops_before_dependency_install(self):
        from install_dependencies import build
        from collections import namedtuple
        usage = namedtuple('usage', 'total used free')(1000, 999, 1)
        with patch('install_dependencies.shutil.disk_usage', return_value=usage), patch('install_dependencies.venv.EnvBuilder') as environment:
            with self.assertRaisesRegex(ValueError, 'disk space'):
                build(self.root, True, None)
            environment.assert_not_called()

    def archive(self, members):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
            for name, value, kind in members:
                entry = tarfile.TarInfo(name)
                if kind == 'link':
                    entry.type = tarfile.SYMTYPE
                    entry.linkname = value
                    archive.addfile(entry)
                else:
                    entry.size = len(value)
                    entry.mode = 0o755
                    archive.addfile(entry, io.BytesIO(value))
        return buffer.getvalue()

    def test_node_archive_rejects_traversal_external_links_and_redirected_parents(self):
        for members in [ [('node/../outside', b'bad', 'file')],
                         [('node/bin/npm', '../../outside', 'link')],
                         [('node/bin', '/outside', 'link'), ('node/bin/node', b'bad', 'file')]]:
            with self.assertRaises(ValueError):
                unpack_node(self.archive(members), self.root/'node', 'node')

    def test_official_node_checksum_and_internal_links(self):
        from install_dependencies import NODE_VERSION
        prefix = f'node-v{NODE_VERSION}-darwin-arm64'
        blob = self.archive([(prefix+'/bin/node', b'node', 'file'),
                             (prefix+'/lib/npm.js', b'npm', 'file'),
                             (prefix+'/bin/npm', '../lib/npm.js', 'link')])
        sha = hashlib.sha256(blob).hexdigest()
        def fetch(url, limit):
            return (sha+'  '+prefix+'.tar.gz\n').encode() if url.endswith('.txt') else blob
        with patch('install_dependencies.download', side_effect=fetch), patch('install_dependencies.sys.platform', 'darwin'), patch('platform.machine', return_value='arm64'):
            result = install_node(self.root/'Node')
            self.assertEqual(result['archive_sha256'], sha)
            self.assertEqual((self.root/'Node/bin/npm').read_bytes(), b'npm')
            sha = '0'*64
            with self.assertRaisesRegex(ValueError, 'checksum'):
                install_node(self.root/'Rejected')
            self.assertFalse((self.root/'Rejected').exists())


if __name__ == '__main__':
    unittest.main()
