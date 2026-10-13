"""Release discovery uses fake HTTP and Docker, with no installed resources."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import releases
from pcirn import Error


def candidate(version, prerelease=False):
    payload = json.dumps({
        'schema_version': 1, 'version': version, 'source': {'commit': 'a' * 40},
        'images': {key: 'ghcr.io/kevintestegit/dspace-pcirn-' + name + '@sha256:' + 'b' * 64
                   for key, name in [('backend', 'backend'), ('solr', 'solr'), ('frontend', 'angular')]},
        'database': {'migrations': [{'version': '1', 'script': 'V1__init.sql', 'checksum': 42}]}
    }).encode()
    release = {'tag_name': 'v' + version, 'draft': False, 'prerelease': prerelease,
               'assets': [{'name': 'release-manifest.json', 'size': len(payload),
                           'digest': 'sha256:' + hashlib.sha256(payload).hexdigest(),
                           'browser_download_url': 'https://github.com/' + releases.REPOSITORY
                           + '/releases/download/v' + version + '/release-manifest.json'}]}
    return release, payload


class ReleasesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.release, self.payload = candidate('1.0.0-rc4')

    def discover(self, payload=None, sha='a' * 40):
        with patch.object(releases, 'select', return_value=self.release), \
                patch.object(releases, '_download', return_value=payload or self.payload), \
                patch.object(releases, '_json', return_value={'sha': sha}):
            return releases.discover(self.root)

    def test_stable_beats_higher_rc(self):
        entries = [candidate('2.0.0-rc1')[0], candidate('1.0.2')[0], candidate('1.0.10')[0]]
        with patch.object(releases, '_json', return_value=entries):
            self.assertEqual(releases.select()['tag_name'], 'v1.0.10')

    def test_rc_numeric_order_even_when_github_flag_wrong(self):
        entries = [candidate('1.0.0-rc4')[0], candidate('1.0.0-rc10')[0]]
        with patch.object(releases, '_json', return_value=entries):
            self.assertEqual(releases.select()['tag_name'], 'v1.0.0-rc10')

    def test_drafts_and_non_rc_prereleases_excluded(self):
        draft = candidate('9.0.0')[0]
        draft['draft'] = True
        with patch.object(releases, '_json', return_value=[draft, {'tag_name': 'v10.0.0-beta1'}]):
            with self.assertRaisesRegex(Error, 'No official'):
                releases.select()

    def test_pagination_reaches_stable(self):
        page1 = [candidate('2.0.0-rc1')[0]] * 100
        with patch.object(releases, '_json', side_effect=[page1, [candidate('1.0.0')[0]]]):
            self.assertEqual(releases.select()['tag_name'], 'v1.0.0')

    def test_manual_version_is_explicit(self):
        with patch.object(releases, '_json', return_value=self.release) as fetch:
            self.assertEqual(releases.select('1.0.0-rc4'), self.release)
            self.assertTrue(fetch.call_args.args[0].endswith('/releases/tags/v1.0.0-rc4'))
        with self.assertRaises(Error):
            releases.select('../../main')

    def test_discover_validates_and_saves_private_manifest(self):
        path = self.discover()
        self.assertEqual(path.read_bytes(), self.payload)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_checksum_failure_keeps_existing_download(self):
        path = self.discover()
        with self.assertRaisesRegex(Error, 'checksum'):
            self.discover(self.payload + b'corruption')
        self.assertEqual(path.read_bytes(), self.payload)

    def test_commit_mismatch_refuses_manifest(self):
        with self.assertRaisesRegex(Error, 'commit'):
            self.discover(sha='c' * 40)
        self.assertFalse(list(self.root.rglob('release-manifest.json')))

    def test_version_and_source_validation(self):
        data = json.loads(self.payload)
        for key, value in [('version', '2.0.0'), ('source', {'commit': 'main'})]:
            altered = dict(data, **{key: value})
            payload = json.dumps(altered).encode()
            self.release['assets'][0].update(size=len(payload), digest='sha256:' + hashlib.sha256(payload).hexdigest())
            with self.assertRaisesRegex(Error, 'version or source commit'):
                self.discover(payload)

    def test_assets_require_official_url_and_digest(self):
        asset = self.release['assets'][0]
        for key, value in [('browser_download_url', 'https://evil.example/manifest'), ('digest', '')]:
            modified = dict(self.release, assets=[dict(asset, **{key: value})])
            with self.assertRaises(Error):
                releases._asset(modified, 'release-manifest.json')

    def test_rc4_manager_update_explains_missing_verified_package(self):
        with patch.object(releases, 'select', return_value=self.release):
            with self.assertRaisesRegex(Error, 'dspacepcirn-manager.tar.gz'):
                releases.download_manager(self.root)

    def test_manager_asset_checksum(self):
        payload = b'archive'
        asset = dict(self.release['assets'][0], name='dspacepcirn-manager.tar.gz', size=len(payload),
                     digest='sha256:' + hashlib.sha256(payload).hexdigest())
        asset['browser_download_url'] = asset['browser_download_url'].replace('release-manifest.json', asset['name'])
        self.release['assets'].append(asset)
        with patch.object(releases, 'select', return_value=self.release), \
                patch.object(releases, '_download', return_value=payload):
            path, digest = releases.download_manager(self.root)
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(digest, asset['digest'].removeprefix('sha256:'))

    def test_symlink_download_directory_refused(self):
        (self.root / 'downloads').symlink_to(self.root)
        with self.assertRaisesRegex(Error, 'symlinks'):
            self.discover()

    def test_network_errors_do_not_leak_credentials(self):
        for error in [URLError('password secret'), HTTPError('secret', 403, 'secret', {}, io.BytesIO())]:
            with patch.object(releases, 'urlopen', side_effect=error):
                with self.assertRaises(Error) as caught:
                    releases._download(releases.API)
            self.assertNotIn('secret', str(caught.exception))
            if isinstance(error, HTTPError):
                error.close()

    def test_redirect_is_refused_before_contacting_external_host(self):
        with self.assertRaisesRegex(Error, 'redirect'):
            releases._OfficialRedirect().redirect_request(
                None, None, 302, '', {}, 'https://evil.example/script')

    def test_existing_version_cannot_change(self):
        path = self.discover()
        altered = json.loads(self.payload)
        altered['createdAt'] = 'different bytes'
        payload = json.dumps(altered).encode()
        self.release['assets'][0].update(size=len(payload), digest='sha256:' + hashlib.sha256(payload).hexdigest())
        with self.assertRaisesRegex(Error, 'same version changed'):
            self.discover(payload)
        self.assertEqual(path.read_bytes(), self.payload)

    def test_arbitrary_project_image_is_refused(self):
        altered = json.loads(self.payload)
        altered['images']['backend'] = 'ghcr.io/kevintestegit/dspace-pcirn-untrusted@sha256:' + 'b' * 64
        payload = json.dumps(altered).encode()
        self.release['assets'][0].update(size=len(payload), digest='sha256:' + hashlib.sha256(payload).hexdigest())
        with self.assertRaisesRegex(Error, 'outside the official project'):
            self.discover(payload)

    def test_download_size_limit(self):
        response = io.BytesIO(b'a' * 11)
        response.geturl = lambda: releases.API
        with patch.object(releases, 'urlopen', return_value=response):
            with self.assertRaisesRegex(Error, 'size'):
                releases._download(releases.API, limit=10)

    def test_docker_platform_and_postgres_digest(self):
        for arch in ('amd64', 'arm64'):
            def run(args, timeout=None):
                self.assertEqual(timeout, 30)
                return json.dumps([{'Descriptor': {'digest': 'sha256:' + 'd' * 64,
                                                   'platform': {'os': 'linux', 'architecture': arch}}}])
            self.assertEqual(releases.postgres_image(run, arch), 'postgres@sha256:' + 'd' * 64)
            releases.validate_images(run, json.loads(self.payload), arch)

    def test_docker_architecture(self):
        self.assertEqual(releases.docker_architecture(lambda *a, **k: json.dumps(
            {'OSType': 'linux', 'Architecture': 'aarch64'})), 'arm64')
        with self.assertRaises(Error):
            releases.docker_architecture(lambda *a, **k: '{"OSType":"windows","Architecture":"amd64"}')

    def test_incompatible_images_and_postgres_version(self):
        with self.assertRaises(Error):
            releases.postgres_image(lambda *a, **k: '[]', 'arm64')
        with self.assertRaises(Error):
            releases.postgres_image(lambda *a, **k: '[]', 'arm64', major=15)

    def test_ghcr_errors_are_actionable_and_private(self):
        def run(*args, **kwargs):
            raise Error('secret registry token')
        with self.assertRaisesRegex(Error, 'login') as caught:
            releases.validate_images(run, json.loads(self.payload), 'arm64')
        self.assertNotIn('secret', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
