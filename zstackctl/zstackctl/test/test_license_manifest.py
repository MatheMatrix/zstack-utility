#!/usr/bin/env python
# encoding: utf-8

import os
import sys
import shutil
import tempfile
import unittest

curr_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(os.path.dirname(curr_dir)))

from zstackctl import license_manifest as lm


class LicenseManifestTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, 'lib'))
        self._write('lib/mevoco.jar', 'mevoco-content')
        self._write('conf/license.xml', '<beans><bean id="LicenseManager"/></beans>')
        self.rel_paths = ['lib/mevoco.jar', 'conf/license.xml', 'conf/absent.pem']
        files = lm.collect_files(self.root, self.rel_paths)
        manifest = lm.build_manifest(
            {'product': 'ZStack', 'version': '5.5.28', 'release': '1', 'arch': 'x86_64',
             'build_time': 't', 'git_commit': 'c', 'key_id': 'rel-1'}, files)
        self.manifest_path = os.path.join(self.root, 'manifest.json')
        lm.write_manifest(manifest, self.manifest_path)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, rel, content):
        abs_path = os.path.join(self.root, rel)
        if not os.path.isdir(os.path.dirname(abs_path)):
            os.makedirs(os.path.dirname(abs_path))
        with open(abs_path, 'w') as fd:
            fd.write(content)

    def test_serialization_is_deterministic(self):
        manifest = lm.load_manifest(self.manifest_path)
        self.assertEqual(lm.serialize_manifest(manifest), lm.serialize_manifest(manifest))

    def test_absent_critical_file_recorded_without_hash(self):
        manifest = lm.load_manifest(self.manifest_path)
        absent = [f for f in manifest['files'] if f['path'] == 'conf/absent.pem'][0]
        self.assertIsNone(absent['sha256'])

    def test_clean_tree_passes(self):
        manifest = lm.load_manifest(self.manifest_path)
        self.assertEqual(lm.verify_file_hashes(self.root, manifest), [])

    def test_tampered_file_detected(self):
        self._write('lib/mevoco.jar', 'EVIL')
        manifest = lm.load_manifest(self.manifest_path)
        failures = lm.verify_file_hashes(self.root, manifest)
        self.assertEqual([(f['path'], f['reason']) for f in failures],
                         [('lib/mevoco.jar', 'sha256 mismatch')])

    def test_deleted_file_detected(self):
        os.remove(os.path.join(self.root, 'conf/license.xml'))
        manifest = lm.load_manifest(self.manifest_path)
        failures = lm.verify_file_hashes(self.root, manifest)
        self.assertEqual([(f['path'], f['reason']) for f in failures],
                         [('conf/license.xml', 'missing')])

    def test_orchestrator_missing_manifest_is_tolerated(self):
        result = lm.verify_release_integrity(self.root, '/no/such/manifest.json', None, None)
        self.assertEqual(result['status'], lm.STATUS_MISSING_MANIFEST)

    def test_orchestrator_hash_only_fallback_when_no_helper(self):
        result = lm.verify_release_integrity(self.root, self.manifest_path, None, None)
        self.assertEqual(result['status'], lm.STATUS_VERIFIED)
        self.assertEqual(result['mode'], lm.MODE_HASH_ONLY)
        self.assertFalse(result['pubkey_anchored'])

    def test_orchestrator_hash_only_detects_tamper(self):
        self._write('lib/mevoco.jar', 'EVIL')
        result = lm.verify_release_integrity(self.root, self.manifest_path, None, None)
        self.assertEqual(result['status'], lm.STATUS_TAMPERED)
        self.assertEqual(result['mode'], lm.MODE_HASH_ONLY)


if __name__ == '__main__':
    unittest.main()
