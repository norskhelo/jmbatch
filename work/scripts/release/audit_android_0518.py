"""Audit the Android library crash release, regression proof and original identities."""
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from release_paths import PROJECT as ROOT, WORK, sha256, verify_manifest, source_versions

REPORT = ROOT/'outputs/reports/library-crash-0518-complete'
REPORT.mkdir(parents=True, exist_ok=True)
DELIVERY = ROOT.parent/'Android/0.5.18'
BASE = '72b2b90d9d09f3611109c05d68a29483ec611821'
checks = json.loads((ROOT/'outputs/reports/library-crash-0518-android-final/android-checks.json').read_text(encoding='utf-8'))
assert len(checks) == 2 and all(item['exit_code'] == 0 for item in checks)
log = (ROOT/'outputs/reports/library-crash-0518-android-final/android-build-and-host-tests.log').read_text(encoding='utf-8', errors='replace')
for text in ('LibraryRowsTest: 29 checks passed', 'LibraryInteractionTest: 46 checks passed',
             'Persistent cover cache: 27 checks passed', 'Library cover integration: 26 checks passed',
             'Action layout: 96 synthetic font/scale/width scenarios, 12430 checks passed (not Android rendering)'):
    assert text in log, text
counts = [int(n) for n in re.findall(r'(\d+) checks(?: passed)?', '\n'.join(line for line in log.splitlines() if not line.startswith('Action layout:')))]
counts += [int(n) for n in re.findall(r'Download pool checks: (\d+)', log)]
assert sum(counts) == 1347
assert source_versions() == {'windows':'0.3.20', 'android':'0.5.18'}

def suite(run):
    tree = ET.parse(WORK/'tests'/run/'target/surefire-reports/TEST-app.jmbatch.android.LibraryScreenRuntimeTest.xml').getroot()
    return {key:int(tree.attrib[key]) for key in ('tests', 'errors', 'failures', 'skipped')}

baseline = suite('library-crash-baseline-proof')
runtime = suite('library-crash-0518-runtime')
assert baseline == dict(tests=7, errors=4, failures=0, skipped=0)
assert runtime == dict(tests=7, errors=0, failures=0, skipped=0)
runtime_sources = WORK/'tests/library-crash-0518-runtime/src/main/java'
production_sources = WORK/'jmbatch-android/app/src/main/java'
for path in production_sources.rglob('*.java'):
    assert path.read_bytes() == (runtime_sources/path.relative_to(production_sources)).read_bytes(), path

tools = WORK/'android-tools'; java = next(tools.glob('jdk-*'))/'bin/java.exe'
signer = next(tools.rglob('apksigner.jar')); certs = []
for version in ('0.5.17', '0.5.18'):
    apk = ROOT.parent/f'Android/{version}/JMBatch-{version}-Android.apk'
    text = subprocess.run([str(java), '-jar', str(signer), 'verify', '--verbose', '--print-certs', str(apk)], check=True, capture_output=True).stdout.decode('utf-8')
    (REPORT/f'apk-signature-{version}.txt').write_text(text, encoding='utf-8')
    assert 'Verified using v2 scheme (APK Signature Scheme v2): true' in text
    assert 'Verified using v3 scheme (APK Signature Scheme v3): true' in text
    certs.append(re.search(r'Signer #1 certificate SHA-256 digest: ([a-f0-9]+)', text).group(1))
assert certs[0] == certs[1]
apk = DELIVERY/'JMBatch-0.5.18-Android.apk'
assert apk.read_bytes() == (WORK/'builds/android-0.5.18/JMBatch-0.5.18-Android.apk').read_bytes()
with zipfile.ZipFile(apk) as archive:
    assert archive.testzip() is None
    dex = archive.read('classes.dex')
    for value in (b'LibraryGridView;', b'restorePosition', b'scrollListBy', b'CoverDiskCache;', b'0.5.18'):
        assert value in dex, value
badging = subprocess.run([str(next(tools.rglob('aapt.exe'))), 'dump', 'badging', str(apk)], check=True, capture_output=True).stdout.decode('utf-8', errors='replace')
assert "name='app.jmbatch.android' versionCode='518' versionName='0.5.18'" in badging
(REPORT/'apk-badging.txt').write_text(badging, encoding='utf-8')

def original(path):
    return subprocess.run(['git', 'show', BASE+':'+path], cwd=ROOT, capture_output=True, check=True).stdout

manifest = ET.parse(WORK/'jmbatch-android/app/src/main/AndroidManifest.xml').getroot()
old = ET.fromstring(original('work/jmbatch-android/app/src/main/AndroidManifest.xml'))
ns = '{http://schemas.android.com/apk/res/android}'
assert int(manifest.get(ns+'versionCode')) > int(old.get(ns+'versionCode'))
manifest.set(ns+'versionCode', old.get(ns+'versionCode')); manifest.set(ns+'versionName', old.get(ns+'versionName'))
assert ET.tostring(manifest) == ET.tostring(old), 'Manifest changed beyond version'
for path in ('work/jmbatch/core.py', 'work/jmbatch/update_trust.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/UpdateTrust.java'):
    assert (ROOT/path).read_bytes().replace(b'\r\n', b'\n') == original(path).replace(b'\r\n', b'\n'), path
assert not subprocess.run(['git', 'diff', BASE, '--', 'work/jmbatch'], cwd=ROOT, capture_output=True, check=True).stdout
spec = importlib.util.spec_from_file_location('packager', WORK/'package_network_update.py')
packager = importlib.util.module_from_spec(spec); spec.loader.exec_module(packager)
files = packager.source_files('android')
with zipfile.ZipFile(DELIVERY/'JMBatch-0.5.18-Android-source.zip') as archive:
    assert set(archive.namelist()) == set(files) and archive.testzip() is None
    assert any(n.endswith('/LibraryScreenRuntimeTest.java') for n in files)
    assert any(n.endswith('/tests/runtime/pom.xml') for n in files)
    for name, path in files.items(): assert archive.read(name) == path.read_bytes(), name
notes = (WORK/'release-android-0518/release-notes.md').read_bytes()
assert (ROOT/'CHANGELOG.md').read_bytes().startswith(notes)
assert notes == (DELIVERY/'release-notes-android-0.5.18.md').read_bytes() == (DELIVERY/'更新日志-0.5.18.md').read_bytes()
assert (DELIVERY/'安卓使用说明-0.5.18.txt').read_bytes() == (WORK/'jmbatch-android/README.txt').read_bytes()
plain = re.sub(r'^#{1,2} ', '', notes.decode('utf-8').replace('\r\n', '\n'), flags=re.M).replace('- ', '• ')
source = (WORK/'jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java').read_text(encoding='utf-8')
assert json.loads(re.search(r'CURRENT_NOTES=("(?:\\.|[^"\\])*");', source).group(1)) == plain
assert verify_manifest(DELIVERY, {'android':'0.5.18'})['tag'] == 'release-android-0.5.18'
for line in (DELIVERY/'SHA256-android-0.5.18.txt').read_text(encoding='utf-8').splitlines():
    expected, name = line.split('  ', 1); assert expected == sha256(DELIVERY/name), name
readme = (ROOT/'README.md').read_text(encoding='utf-8')
assert 'release-android-0.5.18/JMBatch-0.5.18-Android.apk' in readme
assert 'release-0.3.20-0.5.17/JMBatch-0.3.20-Windows-x64.zip' in readme
assert 'JMBatch-0.5.17-Android.apk' not in readme
assert 'release-android-0.5.18/SHA256-release-android-0.5.18.txt' in readme
allowed = set(files.values())
allowed.update(ROOT/p for p in ('README.md', 'CHANGELOG.md', 'work/release-android-0518/release-notes.md',
    'work/package_network_update.py', 'work/scripts/maintenance/prepare_android_crash_release.py',
    'work/scripts/maintenance/run_android_runtime_tests.py',
    'work/scripts/maintenance/verify_android_crash_online.py',
    'work/scripts/release/prepare_publication_android_0518.py', 'work/scripts/release/publish_android_0518.py',
    'work/scripts/release/verify_crash_commit.py', 'work/scripts/release/audit_android_0518.py'))
entries = []
for path in sorted(allowed):
    name = path.relative_to(ROOT).as_posix(); data = path.read_bytes()
    assert path.suffix not in ('.jks', '.pem', '.key', '.apk', '.zip') and not path.is_symlink()
    assert not re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', data)
    entries.append(dict(path=name, sha256=hashlib.sha256(data).hexdigest()))
(REPORT/'pathspec.txt').write_bytes(b'\0'.join(e['path'].encode('utf-8') for e in entries)+b'\0')
receipt = dict(ok=True, android='0.5.18', windows_unchanged='0.3.20', android_host_checks=sum(counts),
    apk_certificate_sha256=certs[0], packaged_source_files=len(files), allowed_paths=entries,
    android_device_tested=False, synthetic_font_scenarios=96, synthetic_layout_checks=12430,
    library_row_checks=29, library_interaction_checks=46, synthetic_grid_list_scenarios=18,
    android_10_touch_runtime=runtime, original_0517_runtime=baseline,
    delivery=[dict(name=p.name, size=p.stat().st_size, sha256=sha256(p)) for p in sorted(DELIVERY.iterdir()) if p.is_file()])
assert len(receipt['delivery']) == 9
(REPORT/'audit.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print('AUDITED', sum(counts), 'host checks;', len(files), 'packaged sources;', len(entries), 'source/docs paths; original signing certificate; nine delivery files')
