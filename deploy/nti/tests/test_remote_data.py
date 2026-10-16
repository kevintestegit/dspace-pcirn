"""Remote imports fail before database access and reuse verified private downloads."""
import hashlib
import io
import json
from email.message import Message
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import subprocess
from types import SimpleNamespace
import unittest
from unittest import mock
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pcirn
import remote_data
import releases
import wizard
from data_migration import PACKAGE_FILES, REQUIRED_TABLES


class RemoteDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        os.umask(0o077)
        self.release = {'schema_version': 1, 'version': '1.0.0',
                        'images': {k: 'ghcr.io/fixture/' + k + '@sha256:' + '1' * 64
                                   for k in pcirn.IMAGE_KEYS},
                        'database': {'migrations': [{'version': '1', 'script': 'test', 'checksum': 1}]}}
        self.files = {name: b'fixture' for name in PACKAGE_FILES}
        self.files['release.json'] = json.dumps(self.release).encode()
        self.files['source-report.json'] = json.dumps({
            'schema_version': 1, 'tables': dict.fromkeys(REQUIRED_TABLES, {})}).encode()
        self.files['checksums.json'] = json.dumps({
            name: hashlib.sha256(data).hexdigest() for name, data in self.files.items()}).encode()
        self.payload = self.archive(self.files)
        self.source = {'url': 'https://downloads.example/data.tar.gz',
                       'sha256': hashlib.sha256(self.payload).hexdigest(), 'size': len(self.payload)}
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(remote_data.socket, 'getaddrinfo', return_value=[
            (2, 1, 6, '', ('8.8.8.8', 443))]).start()
        self.disk = mock.patch.object(remote_data.shutil, 'disk_usage',
                                     return_value=SimpleNamespace(free=120 * remote_data.GIB)).start()

    @staticmethod
    def archive(files):
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode='w:gz') as archive:
            for name, contents in files.items():
                member = tarfile.TarInfo(name)
                if contents is None:
                    member.type, member.linkname = tarfile.SYMTYPE, '/etc/passwd'
                    archive.addfile(member)
                else:
                    member.size = len(contents)
                    archive.addfile(member, io.BytesIO(contents))
        return out.getvalue()

    def download(self, payload=None, source=None, content_type='application/gzip'):
        response = io.BytesIO(self.payload if payload is None else payload)
        response.geturl = lambda: self.source['url']
        response.headers = Message()
        response.headers['Content-Type'] = content_type
        with mock.patch.object(remote_data, 'urlopen', return_value=response):
            return remote_data.download_package(self.root, source or self.source)

    def test_verified_flat_package_is_private_and_cached(self):
        package = self.download()
        self.assertEqual(package.stat().st_mode & 0o777, 0o700)
        for name in self.files:
            self.assertEqual((package / name).read_bytes(), self.files[name])
            self.assertEqual((package / name).stat().st_mode & 0o777, 0o600)
        with mock.patch.object(remote_data, 'urlopen', side_effect=AssertionError('repeated download')):
            self.assertEqual(remote_data.download_package(self.root, self.source), package)

    def test_source_identity_must_be_bounded_and_well_formed(self):
        for identity in (b'[]', json.dumps({'containers': []}).encode(), b'{}'):
            files = dict(self.files)
            files['source-identity.json'] = identity
            files['checksums.json'] = json.dumps({
                name: hashlib.sha256(data).hexdigest()
                for name, data in files.items() if name != 'checksums.json'}).encode()
            payload = self.archive(files)
            source = self.source | {'sha256': hashlib.sha256(payload).hexdigest(), 'size': len(payload)}
            with self.assertRaises(pcirn.Error):
                self.download(payload, source)
        files['source-identity.json'] = b' ' * (2 * remote_data.CHUNK + 1)
        files['checksums.json'] = json.dumps({
            name: hashlib.sha256(data).hexdigest()
            for name, data in files.items() if name != 'checksums.json'}).encode()
        payload = self.archive(files)
        source = self.source | {'sha256': hashlib.sha256(payload).hexdigest(), 'size': len(payload)}
        with self.assertRaises(pcirn.Error):
            self.download(payload, source)

    def test_corruption_truncation_and_oversize_never_publish_package(self):
        for payload in (b'bad', self.payload[:-1], self.payload + b'bad'):
            with self.assertRaises(pcirn.Error):
                self.download(payload)
        self.assertFalse(list(self.root.rglob('package')))
        self.assertFalse(list(self.root.rglob('.download-*')))

    def test_network_failure_is_retryable_and_hides_url_secrets(self):
        with mock.patch.object(remote_data, 'urlopen', side_effect=URLError('private-url-token')):
            with self.assertRaises(pcirn.Error) as caught:
                remote_data.download_package(self.root, self.source)
        self.assertNotIn('private-url-token', str(caught.exception))
        self.assertTrue(self.download().is_dir())

    def test_preview_page_and_private_redirect_are_rejected(self):
        with self.assertRaisesRegex(pcirn.Error, 'web page'):
            self.download(content_type='text/html')
        with mock.patch.object(remote_data.socket, 'getaddrinfo', return_value=[
                (2, 1, 6, '', ('169.254.169.254', 443))]):
            with self.assertRaises(pcirn.Error):
                remote_data.PublicRedirect().redirect_request(None, None, 302, '', {},
                                                              'https://metadata.example/data')
        for url in ('http://example.com/data', 'https://user:secret@example.com/data',
                    'https://example.com:444/data', 'https://example.com/data#fragment'):
            with self.assertRaises(pcirn.Error):
                remote_data.validate_source(self.source | {'url': url})

    def test_unsafe_incomplete_and_corrupt_archives_are_rejected(self):
        for files in (self.files | {'../outside': b'bad'}, self.files | {'link': None},
                      {k: v for k, v in self.files.items() if k != 'database.dump'},
                      self.files | {'database.dump': b'corrupt'}):
            payload = self.archive(files)
            source = self.source | {'sha256': hashlib.sha256(payload).hexdigest(), 'size': len(payload)}
            with self.assertRaises(pcirn.Error):
                self.download(payload, source)
        self.assertFalse(list(self.root.rglob('package')))

    def test_cached_files_and_symlinks_cannot_bypass_checksums(self):
        package = self.download()
        (package / 'database.dump').write_bytes(b'corrupt')
        with self.assertRaises(pcirn.Error):
            remote_data.download_package(self.root, self.source)
        (package / 'database.dump').unlink()
        (package / 'database.dump').symlink_to(self.root / 'outside')
        with self.assertRaises(pcirn.Error):
            remote_data.download_package(self.root, self.source)

    def test_space_and_descriptor_validation_happen_before_download(self):
        self.disk.return_value.free = remote_data.GIB
        with mock.patch.object(remote_data, 'urlopen') as download:
            with self.assertRaisesRegex(pcirn.Error, 'disk space'):
                remote_data.download_package(self.root, self.source)
            download.assert_not_called()
        for value in ({}, self.source | {'size': True}, self.source | {'sha256': 'bad'}):
            with self.assertRaises(pcirn.Error):
                remote_data.validate_source(value)

    def test_release_descriptor_has_an_independent_verified_checksum(self):
        payload = json.dumps(self.source).encode()
        asset = {'name': 'data-package.json', 'size': len(payload),
                 'digest': 'sha256:' + hashlib.sha256(payload).hexdigest(),
                 'browser_download_url': 'https://github.com/' + releases.REPOSITORY +
                                         '/releases/download/v1.0.0/data-package.json'}
        release = {'tag_name': 'v1.0.0', 'assets': [asset]}
        with mock.patch.object(releases, 'select', return_value=release), \
                mock.patch.object(releases, '_download', return_value=payload):
            self.assertEqual(releases.download_data_source('1.0.0'), self.source)
            asset['digest'] = 'sha256:' + '0' * 64
            with self.assertRaisesRegex(pcirn.Error, 'checksum'):
                releases.download_data_source('1.0.0')

    def test_wizard_uses_remote_package_for_both_database_modes(self):
        package = self.download()
        for mode in ('docker', 'external'):
            args = SimpleNamespace(root=self.root / mode, config=None, manifest=None, data_package=None)
            wiz = wizard.Wizard(args)
            wiz.inputs['config'] = {'PG_MODE': mode}
            with mock.patch.object(wiz, 'release', return_value=self.release), \
                    mock.patch.object(releases, 'download_data_source', return_value=self.source), \
                    mock.patch.object(wiz, 'confirm', return_value=True) as confirm, \
                    mock.patch.object(remote_data, 'download_package', return_value=package):
                wiz.import_data()
            confirm.assert_called_once_with('Import data?', default=False)
            self.assertEqual(wiz.inputs['installation_mode'], 'migration')
            self.assertEqual(wiz.inputs['package'], str(package))

    def test_missing_source_does_not_trap_import_selection(self):
        args = SimpleNamespace(root=self.root, config=None, manifest=None, data_package=None)
        wiz = wizard.Wizard(args)
        with mock.patch.object(wiz, 'release', return_value=self.release), \
                mock.patch.object(wiz, 'confirm', return_value=True), \
                mock.patch.object(releases, 'download_data_source', side_effect=pcirn.Error('no data package')):
            with self.assertRaisesRegex(pcirn.Error, 'no data package'):
                wiz.import_data()
        self.assertNotIn('installation_mode', wiz.inputs)

    def test_packaging_script_produces_a_downloadable_export_and_does_not_overwrite(self):
        package = self.root / 'export'
        package.mkdir(mode=0o700)
        for name, contents in self.files.items():
            (package / name).write_bytes(contents)
        output = self.root / 'export.tar.gz'
        command = [sys.executable, str(Path(__file__).resolve().parents[3] / 'scripts/package-data.py'),
                   '--package', str(package), '--url', self.source['url'], '--output', str(output)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        source = pcirn.read_json(output.with_name(output.name + '.json'))
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertTrue(self.download(output.read_bytes(), source).is_dir())
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(pcirn.checksum(output), source['sha256'])
        invalid = command.copy()
        invalid[-1] = str(package / 'archive.tar.gz')
        result = subprocess.run(invalid, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('outside the export directory', result.stderr)
        self.assertEqual(set(p.name for p in package.iterdir()), set(self.files))

    def test_import_declined_does_not_download_or_require_a_package(self):
        args = SimpleNamespace(root=self.root, config=None, manifest=None, data_package=None)
        wiz = wizard.Wizard(args)
        with mock.patch.object(wiz, 'confirm', return_value=False), \
                mock.patch.object(wiz, 'validate_bootstrap'), \
                mock.patch.object(remote_data, 'download_package') as download:
            wiz.import_data()
        self.assertEqual(wiz.inputs['installation_mode'], 'new')
        self.assertNotIn('package', wiz.inputs)
        download.assert_not_called()

    def test_internal_progress_goes_to_private_log(self):
        from contextlib import redirect_stdout
        args = SimpleNamespace(root=self.root, config=None, manifest=None, data_package=None)
        wiz = wizard.Wizard(args)
        output = io.StringIO()
        with redirect_stdout(output):
            wiz.record(print, 'internal progress')
        self.assertEqual(output.getvalue(), '')
        log = self.root / 'installer.log'
        self.assertEqual(log.read_text(), 'internal progress\n')
        self.assertEqual(log.stat().st_mode & 0o777, 0o600)

    def test_import_prompt_is_english_and_defaults_to_no(self):
        args = SimpleNamespace(root=self.root, config=None, manifest=None, data_package=None)
        wiz = wizard.Wizard(args)
        with mock.patch('builtins.input', side_effect=['', 'YES']) as prompt:
            self.assertFalse(wiz.confirm('Import data?', default=False))
            self.assertTrue(wiz.confirm('Import data?', default=False))
        self.assertEqual(prompt.call_args.args[0], 'Import data? [y/N]: ')

    def test_wrong_release_is_refused_before_restoration(self):
        package = self.download()
        args = SimpleNamespace(root=self.root, config=None, manifest=None, data_package=package)
        wiz = wizard.Wizard(args)
        with mock.patch.object(wiz, 'release', return_value=self.release | {'version': '2.0.0'}), \
                mock.patch('data_migration.migrate_data') as restore:
            with self.assertRaisesRegex(pcirn.Error, 'Package and release must match'):
                wiz.import_data()
        restore.assert_not_called()
