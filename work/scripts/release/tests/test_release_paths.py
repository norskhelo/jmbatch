"""Regression checks for local delivery integrity; no network or publication."""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile

WORK = Path(__file__).resolve().parents[3]
sys.dont_write_bytecode = True
sys.path.insert(0, str(WORK / 'scripts/release'))
from release_paths import delivery_dir, distribute, sha256, verify_manifest

spec = importlib.util.spec_from_file_location('packaging_local', WORK / 'package_network_update.py')
packaging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        test_root = WORK / 'tests/release-paths'
        test_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=test_root)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_independent_versions_and_traversal_rejection(self):
        self.assertEqual(delivery_dir('windows', '0.1.11', self.root), self.root / 'Win/0.1.11')
        self.assertEqual(delivery_dir('android', '0.2.11', self.root), self.root / 'Android/0.2.11')
        for number in ('../outputs', '1/../../2', '0.2.11/extra', ''):
            with self.assertRaises(ValueError):
                delivery_dir('windows', number, self.root)

    def test_preflight_conflict_preserves_all_destinations(self):
        source = self.root / 'new'
        source.write_bytes(b'new')
        conflict = self.root / 'old'
        conflict.write_bytes(b'existing signed release')
        first = self.root / 'not-created'
        with self.assertRaises(FileExistsError):
            distribute([(source, first), (source, conflict)])
        self.assertFalse(first.exists())
        self.assertEqual(conflict.read_bytes(), b'existing signed release')

    def test_repeat_keeps_existing_bytes_and_timestamp(self):
        source = self.root / 'source'
        source.write_bytes(b'exact signed bytes')
        target = self.root / 'Win/0.1.11/package.zip'
        distribute([(source, target)])
        modified = target.stat().st_mtime_ns
        distribute([(source, target)])
        self.assertEqual(target.read_bytes(), source.read_bytes())
        self.assertEqual(target.stat().st_mtime_ns, modified)

    def test_deterministic_archives_ignore_filesystem_timestamp(self):
        source = self.root / 'source.py'
        source.write_bytes(b'print("hello")\n')
        first, second = self.root / 'first.zip', self.root / 'second.zip'
        packaging.archive({'src/source.py': source}, first)
        os.utime(source, (1, 1))
        packaging.archive({'src/source.py': source}, second)
        self.assertEqual(sha256(first), sha256(second))

    def test_private_signing_material_cannot_enter_archive(self):
        for name, data in [('local.jks', b'keystore'), ('secret.pem', b'-----BEGIN PRIVATE KEY-----')]:
            source = self.root / name
            source.write_bytes(data)
            with self.assertRaises(ValueError):
                packaging.archive({name: source}, self.root / 'invalid.zip')

    def test_source_allowlist_excludes_user_data_and_caches(self):
        workspace = self.root / 'work'
        for name in ('jmbatch', 'jmbatch-android'):
            shutil.copytree(WORK / name, workspace / name,
                            ignore=shutil.ignore_patterns('__pycache__', 'build', 'dist', '_tmp'))
            for extra in ('cookies.json', 'history.json', 'downloads/private.zip', '.venv/secret.py'):
                path = workspace / name / extra
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('private sentinel')
        with patch.object(packaging, 'ROOT', workspace):
            for platform in ('windows', 'android'):
                selected = packaging.source_files(platform)
                self.assertFalse(any('private sentinel' in p.read_text(errors='ignore')
                                     for p in selected.values()))

    def signed_android_fixture(self):
        original = WORK.parent / 'outputs'
        for name in ('update-manifest.json', 'update-manifest.sig', 'JMBatch-0.2.11-Android.apk'):
            shutil.copy2(original / name, self.root / name)
        return self.root

    def test_manifest_signature_tamper_is_rejected(self):
        directory = self.signed_android_fixture()
        verify_manifest(directory, {'android': '0.2.11'})
        manifest = directory / 'update-manifest.json'
        manifest.write_bytes(manifest.read_bytes() + b' ')
        with self.assertRaises(ValueError):
            verify_manifest(directory, {'android': '0.2.11'})

    def test_installer_tamper_is_rejected(self):
        directory = self.signed_android_fixture()
        with (directory / 'JMBatch-0.2.11-Android.apk').open('ab') as stream:
            stream.write(b'tampered')
        with self.assertRaises(ValueError):
            verify_manifest(directory, {'android': '0.2.11'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
