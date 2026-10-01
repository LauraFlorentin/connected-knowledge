import io
import hashlib
import json
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from private_runtime import startup, status
from private_setup import install_tunnel


class PrivateRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def test_startup_preview_and_argument_boundaries(self):
        runtime = self.root/'Runtime with spaces'
        runtime.mkdir()
        with patch('private_runtime.Path.home', return_value=self.root), patch('private_runtime.sys.platform', 'darwin'):
            result = startup(runtime)
            target = Path(result['file'])
            self.assertFalse(target.exists())
            startup(runtime, True)
            data = plistlib.loads(target.read_bytes())
            self.assertEqual(data['ProgramArguments'][-1], str(runtime))
            self.assertNotIn('CONTROL_PLANE_API_KEY', str(data))
            with self.assertRaises(ValueError):
                startup(runtime, True)
        with patch('private_runtime.Path.home', return_value=self.root), patch('private_runtime.sys.platform', 'linux'):
            result = startup(runtime, True)
            self.assertIn('Restart=on-failure', Path(result['file']).read_text())
            self.assertEqual(result['activation_argv'][:3], ['systemctl', '--user', 'enable'])

    def test_health_never_calls_external_urls(self):
        self.assertEqual(status(self.root)['state'], 'offline')
        (self.root/'health.url').write_text('https://fictional.example/secret')
        with patch('urllib.request.build_opener') as opener:
            with self.assertRaises(ValueError):
                status(self.root)
            opener.assert_not_called()

    def test_official_binary_checksum_and_exact_variant(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            archive.writestr('bundle/tunnel-client', b'fictional-binary')
            archive.writestr('../unrelated', b'never-extracted')
        binary_zip = output.getvalue()
        name = 'tunnel-client-v0.0.15-darwin-arm64.zip'
        base = 'https://github.com/openai/tunnel-client/releases/download/v0.0.15/'
        assets = [{'name': item, 'browser_download_url': base+item} for item in
                  (name, 'tunnel-client-runtime-v0.0.15-darwin-arm64.zip', 'SHA256SUMS.txt')]
        release = json.dumps({'tag_name': 'v0.0.15', 'assets': assets}).encode()
        checksum = (hashlib.sha256(binary_zip).hexdigest() + '  ' + name).encode()
        def response(request, timeout):
            url = request.full_url
            return io.BytesIO(release if url.endswith('/latest') else checksum if url.endswith('SHA256SUMS.txt') else binary_zip)
        with patch('private_setup.sys.platform', 'darwin'), patch('platform.machine', return_value='arm64'), patch('urllib.request.urlopen', side_effect=response):
            receipt = install_tunnel(self.root)
            self.assertEqual(receipt['version'], 'v0.0.15')
            self.assertEqual((self.root/'bin/tunnel-client').read_bytes(), b'fictional-binary')
            self.assertFalse((self.root.parent/'unrelated').exists())
        (self.root/'bin/tunnel-client').unlink()
        checksum = ('0'*64 + '  ' + name).encode()
        with patch('private_setup.sys.platform', 'darwin'), patch('platform.machine', return_value='arm64'), patch('urllib.request.urlopen', side_effect=response):
            with self.assertRaises(ValueError):
                install_tunnel(self.root)
            self.assertFalse((self.root/'bin/tunnel-client').exists())


if __name__ == '__main__':
    unittest.main()
