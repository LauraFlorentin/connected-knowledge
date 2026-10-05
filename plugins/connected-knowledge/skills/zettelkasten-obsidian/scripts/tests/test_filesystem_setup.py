import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from filesystem_setup import prepare, connection_plan, TESTED_VERSION, PLUGIN
import filesystem_setup


class FilesystemSetup(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.vault = self.root/'Selected Notes'
        self.vault.mkdir()
        self.note = self.vault/'Guide.md'
        self.note.write_text('Existing conventions', encoding='utf-8')
        self.output = self.root/'Private Setup'

    def tearDown(self):
        self.temporary.cleanup()

    def test_preview_performs_no_install_or_write(self):
        with patch('subprocess.run', side_effect=AssertionError('No process should start')):
            plan = prepare('stdio', [self.vault], self.output)
        self.assertEqual(plan['mode'], 'preview')
        self.assertFalse(plan['activated'])
        self.assertFalse(plan['scope_verified'])
        self.assertFalse(self.output.exists())
        self.assertEqual(self.note.read_text(), 'Existing conventions')
        self.assertEqual(set(self.root.iterdir()), {self.vault})

    def test_prepared_host_files_roundtrip_paths_without_shell_expansion(self):
        tricky = self.root/'Research "quoted" café $HOME `touch surprise` \\ notes'
        tricky.mkdir()
        for host in ('stdio', 'claude-desktop', 'codex'):
            with self.subTest(host=host):
                result = prepare(host, [tricky], self.root/host, True)
                self.assertEqual(result['mode'], 'prepared')
                self.assertFalse(result['activated'])
                config = (self.root/host/result['config_filename']).read_text()
                if host == 'codex':
                    try:
                        import tomllib
                    except ImportError:
                        # Python 3.10 has no TOML parser; the same fixture runs on 3.12 in CI.
                        self.assertIn('enabled = false', config)
                    else:
                        server = tomllib.loads(config)['mcp_servers'][result['name']]
                        self.assertFalse(server.pop('enabled'))
                        self.assertEqual(server.pop('startup_timeout_sec'), 60)
                        self.assertEqual(server, result['connection'])
                else:
                    server = json.loads(config)
                    if host == 'claude-desktop':
                        server = server['mcpServers'][result['name']]
                    self.assertEqual(server, result['connection'])
                self.assertEqual(result['connection']['args'][-1], str(tricky))
                self.assertEqual(json.loads((self.root/host/'setup.json').read_text()), result)
                self.assertEqual((self.root/host).stat().st_mode & 0o777, 0o700)
                self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in (self.root/host).iterdir()))
        self.assertEqual(list(tricky.iterdir()), [])

    def test_exact_version_and_connection_name_required(self):
        for version in ('latest', '*', '^1.2.3', '1.2', '1.2.3-beta', '1.2.3;touch x', '01.2.3', ''):
            with self.subTest(version=version), self.assertRaises(ValueError):
                prepare('stdio', [self.vault], self.output, True, version=version)
        for name in ('invalid.name', 'x\ncommand', 'x"', '../x', ''):
            with self.subTest(name=name), self.assertRaises(ValueError):
                connection_plan('codex', [self.vault], name=name)
        plan = connection_plan('stdio', [self.vault])
        self.assertTrue(plan['tested_version'])
        self.assertIn('@modelcontextprotocol/server-filesystem@' + TESTED_VERSION, plan['connection']['args'])
        self.assertFalse(connection_plan('stdio', [self.vault], version='1.2.3')['tested_version'])
        self.assertFalse(self.output.exists())

    def test_scope_requires_specific_existing_directories(self):
        invalid = [[], [self.root/'missing'], [self.note], [Path('relative')], [Path.home()],
                   [Path.home().parent], [Path('/')], [str(self.vault) + '/..'], ['bad\npath']]
        for directories in invalid:
            with self.subTest(directories=directories), self.assertRaises(ValueError):
                prepare('stdio', directories, self.output, True)
        self.assertFalse(self.output.exists())

    def test_aliases_are_canonicalized_duplicates_collapsed_and_overlap_rejected(self):
        alias = self.root/'alias'
        alias.symlink_to(self.vault, target_is_directory=True)
        result = prepare('stdio', [alias, self.vault])
        self.assertEqual(result['directories'], [str(self.vault)])
        nested = self.vault/'Nested'
        nested.mkdir()
        with self.assertRaisesRegex(ValueError, 'overlap'):
            prepare('stdio', [self.vault, nested])
        other = self.root/'Other'
        other.mkdir()
        self.assertEqual(prepare('stdio', [self.vault, other])['directories'], [str(self.vault), str(other)])

    def test_outputs_cannot_replace_data_or_enter_scope_or_plugin(self):
        blocked = [self.vault/'setup', self.root, self.note, PLUGIN/'private-settings',
                   self.root/'missing-parent/setup']
        alias = self.root/'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        blocked.append(alias/'setup')
        for output in blocked:
            with self.subTest(output=output), self.assertRaises(ValueError):
                prepare('stdio', [self.vault], output, True)
        prepare('stdio', [self.vault], self.output, True)
        original = {p.name: p.read_bytes() for p in self.output.iterdir()}
        with self.assertRaisesRegex(ValueError, 'already exists'):
            prepare('codex', [self.vault], self.output, True)
        self.assertEqual(original, {p.name: p.read_bytes() for p in self.output.iterdir()})
        self.assertEqual(self.note.read_text(), 'Existing conventions')

    def test_output_creation_race_does_not_replace_another_setup(self):
        real_mkdir = Path.mkdir
        def competing_mkdir(path, *args, **kwargs):
            if path == self.output:
                real_mkdir(path)
                (path/'existing.txt').write_text('Other setup')
            return real_mkdir(path, *args, **kwargs)
        with patch.object(Path, 'mkdir', competing_mkdir), self.assertRaises(FileExistsError):
            prepare('stdio', [self.vault], self.output, True)
        self.assertEqual([p.name for p in self.output.iterdir()], ['existing.txt'])

    def test_launcher_is_an_argument_not_a_shell_command(self):
        npx = self.root/'npx with spaces'
        npx.write_text('#!/bin/sh\nexit 1\n')
        npx.chmod(0o700)
        result = prepare('stdio', [self.vault], npx=npx)
        self.assertEqual(result['connection']['command'], str(npx))
        for bad in ('npx --bad', self.root/'missing', self.note):
            with self.subTest(npx=bad), self.assertRaises(ValueError):
                prepare('stdio', [self.vault], npx=bad)

    def test_cli_preview_apply_wizard_and_error(self):
        command = [sys.executable, filesystem_setup.__file__, '--host', 'codex',
                   '--directory', str(self.vault), '--output', str(self.output)]
        result = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['mode'], 'preview')
        self.assertFalse(self.output.exists())
        result = subprocess.run([*command, '--apply'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.output/'codex.fragment.toml').is_file())
        result = subprocess.run([*command, '--apply'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('already exists', result.stderr)
        result = subprocess.run([sys.executable, filesystem_setup.__file__, '--wizard'],
                                input='stdio\n' + str(self.vault) + '\n\n', text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"mode": "preview"', result.stdout)

    def test_missing_apply_destination_and_unsupported_host(self):
        with self.assertRaisesRegex(ValueError, '--output'):
            prepare('stdio', [self.vault], apply=True)
        with self.assertRaises(ValueError):
            prepare('chatgpt-web', [self.vault])
        with patch.object(os, 'name', 'nt'), self.assertRaisesRegex(ValueError, 'macOS/Linux'):
            prepare('stdio', [self.vault])


if __name__ == '__main__':
    unittest.main()
