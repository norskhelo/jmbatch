"""Audit the exact Android 0.6.2 release and create an explicit source allowlist."""
from pathlib import Path
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'work'))
from package_network_update import source_files
sys.path.insert(0, str(ROOT / 'work/scripts/release'))
from release_paths import verify_manifest, source_versions, sha256

REPORT = ROOT / 'outputs/reports/dns-speed-062-release'
REPORT.mkdir(parents=True, exist_ok=True)
build_report = ROOT / 'outputs/reports/dns-speed-062-release-build-final'
checks = json.loads((build_report / 'android-checks.json').read_text())
assert len(checks) == 2 and all(c['exit_code'] == 0 for c in checks)
build = (build_report / 'android-build-and-host-tests.log').read_text(encoding='utf-8', errors='replace')
assert 'FallbackDnsTest: 57 checks passed' in build
assert 'JmApiFallbackTest: 158 checks passed' in build
assert 'Probe engine: 24 checks passed' in build
assert "package: name='app.jmbatch.android' versionCode='602' versionName='0.6.2'" in build
cert = 'cee4da716e0ac1d1b5fa3a8395e27040f18702264c433e1568c1d0b2e73d4f29'
assert 'Signer #1 certificate SHA-256 digest: ' + cert in build
assert all('Verified using ' + s + ': true' in build for s in ['v2 scheme (APK Signature Scheme v2)', 'v3 scheme (APK Signature Scheme v3)'])
assert '96 synthetic font/scale/width scenarios, 11962 checks passed' in build
runtime = ROOT / 'outputs/reports/dns-speed-062-release-runtime-final/runtime.log'
assert 'Tests run: 71, Failures: 0, Errors: 0, Skipped: 0' in runtime.read_text(encoding='utf-8')
java = ROOT / 'work/jmbatch-android/app/src/main/java'
snapshot = ROOT / 'work/tests/dns-speed-062-release-runtime-final/src/main/java'
for path in java.rglob('*.java'):
    assert path.read_bytes() == (snapshot / path.relative_to(java)).read_bytes(), path
assert source_versions() == {'windows': '0.3.22', 'android': '0.6.2'}
ns = '{http://schemas.android.com/apk/res/android}'
manifest = ET.parse(ROOT / 'work/jmbatch-android/app/src/main/AndroidManifest.xml').getroot()
assert manifest.get(ns + 'versionCode') == '602' and manifest.get(ns + 'versionName') == '0.6.2'
perms = {p.get(ns + 'name') for p in manifest.findall('uses-permission')}
assert not {'android.permission.MANAGE_EXTERNAL_STORAGE', 'android.permission.READ_PHONE_STATE', 'android.permission.ACCESS_FINE_LOCATION'} & perms
dest = ROOT.parent / 'Android/0.6.2'
signed = verify_manifest(dest, {'android': '0.6.2'})
assert signed['tag'] == 'release-android-0.6.2'
assert sha256(dest / 'JMBatch-0.6.2-Android.apk') == sha256(ROOT / 'work/builds/android-0.6.2/JMBatch-0.6.2-Android.apk')
source = source_files('android')
with zipfile.ZipFile(dest / 'JMBatch-0.6.2-Android-source.zip') as archive:
    assert archive.testzip() is None and set(archive.namelist()) == set(source)
    for name, path in source.items():
        assert archive.read(name) == path.read_bytes(), name
        assert path.suffix.lower() not in ('.jks', '.keystore', '.pem', '.key')
notes = (ROOT / 'work/release-android-062/release-notes.md').read_text(encoding='utf-8')
assert (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8').startswith(notes)
assert (dest / 'release-notes-android-0.6.2.md').read_text(encoding='utf-8') == notes
assert '本地验证版' not in notes and '尚未推送' not in notes
plain = re.sub(r'(?m)^#{1,6} ', '', notes).replace('- ', '• ')
updates = (java / 'app/jmbatch/android/GithubUpdates.java').read_text(encoding='utf-8')
assert 'private static final String CURRENT_NOTES=' + json.dumps(plain, ensure_ascii=False) + ';' in updates

paths = set(path.relative_to(ROOT).as_posix() for path in source.values())
paths.update(['README.md', 'CHANGELOG.md', 'work/release-android-062/release-notes.md',
              'work/scripts/maintenance/prepare_dns_speed_release.py',
              'work/scripts/maintenance/audit_dns_speed_release.py',
              'work/scripts/maintenance/verify_dns_speed_online.py',
              'work/scripts/release/prepare_publication_android_062.py',
              'work/scripts/release/publish_android_062.py',
              'work/scripts/release/verify_dns_speed_commit.py',
              'work/package_network_update.py', 'work/sign_update_release.py',
              'work/scripts/release/release_paths.py',
              'work/scripts/maintenance/check_development.py',
              'work/scripts/maintenance/run_android_runtime_tests.py'])
for checksum in dest.glob('SHA256*.txt'):
    for line in checksum.read_text(encoding='utf-8').splitlines():
        expected, name = line.split('  ', 1)
        assert sha256(dest / name) == expected, name
host = sum(int(match[1]) for line in build.splitlines() if not line.startswith('Action layout:')
           for match in [re.search(r'(\d+) checks', line)] if match) + 25
assert host == 1624, host
audit = dict(main_host_checks=host, fallback_dns_checks=57, fallback_transport_checks=158,
             network_probe_checks=24, runtime_tests=71, tls_runtime_tests=14,
             layout_scenarios=96, layout_assertions=11962, source_package_files=len(source),
             android='0.6.2', versionCode=602, windows='0.3.22', real_device_tested=False,
             published=False, apk_certificate_sha256=cert,
             local_preview_archived='work/builds/android-0.6.2/local-verification-backup',
             allowed_paths=[dict(path=n, sha256=sha256(ROOT / n)) for n in sorted(paths)],
             delivery_files=[dict(name=p.name, size=p.stat().st_size, sha256=sha256(p)) for p in sorted(dest.iterdir()) if p.is_file()])
assert len(audit['delivery_files']) == 9
(REPORT / 'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(ROOT / 'work/builds/android-0.6.2/source-paths.txt').write_bytes(b'\0'.join(n.encode('utf-8') for n in sorted(paths)) + b'\0')
print(json.dumps({k: v for k, v in audit.items() if k not in ('allowed_paths', 'delivery_files')}, ensure_ascii=False))
print('Allowed source files', len(paths), 'delivery files', len(audit['delivery_files']))
