"""Verify Android bookmark follow-up sources, signatures, tests and publication."""
import io
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
from release_paths import PROJECT as ROOT, WORK, sha256, source_versions, verify_manifest
sys.path.insert(0, str(WORK))
from package_network_update import source_files

BASE = 'c3029c4a8e42ac2a2b0ceb0b3220347f224eafb6'
REPORT = ROOT / 'outputs/reports/bookmark-followup-0613-complete'
REPORT.mkdir(parents=True, exist_ok=True)
DELIVERY = ROOT.parent / 'Android/0.6.13'
BUILD = ROOT / 'outputs/reports/bookmarks-followup-0613-android'
VERSIONS = dict(windows='0.3.30', android='0.6.13')

def run(*args):
    return subprocess.check_output(args, cwd=ROOT)

def save(name, data):
    (REPORT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def lf(data):
    return data.replace(b'\r\n', b'\n')

mode = sys.argv[1]
if mode == 'packages':
    assert source_versions() == VERSIONS
    assert not run('git', 'diff', BASE, '--', 'work/jmbatch').strip()
    suites = []
    for directory, name, count in (
        ('bookmark-focus-fixed', 'BookmarkRuntimeTest', 36),
        ('bookmark-dialog-regression', 'BookmarkRuntimeTest', 8),
        ('bookmark-dialog-regression', 'ChapterViewRuntimeTest', 8),
        ('bookmark-dialog-regression', 'ReaderScrollRuntimeTest', 10),
    ):
        test = WORK / 'tests' / directory
        suite = ET.parse(test / f'target/surefire-reports/TEST-app.jmbatch.android.{name}.xml').getroot()
        result = {key: int(suite.get(key)) for key in ('tests', 'failures', 'errors', 'skipped')}
        assert result == dict(tests=count, failures=0, errors=0, skipped=0)
        relative = 'app/jmbatch/android/ReaderActivity.java'
        assert lf((test / 'src/main/java' / relative).read_bytes()) == lf((WORK / 'jmbatch-android/app/src/main/java' / relative).read_bytes())
        suites.append(dict(directory=directory, name=name, **result))
    old = ET.parse(WORK / 'tests/bookmark-before-relayout/target/surefire-reports/TEST-app.jmbatch.android.BookmarkRuntimeTest.xml').getroot()
    assert old.get('tests') == '4' and old.get('failures') == '2' and old.get('errors') == '0'
    assert all(c['exit_code'] == 0 for c in json.loads((BUILD / 'checks.json').read_text()))
    for path, digest in json.loads((BUILD / 'source-hashes.json').read_text()).items():
        assert sha256(ROOT / path) == digest, path
    for path in ('work/jmbatch/update_trust.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/UpdateTrust.java'):
        assert lf((ROOT / path).read_bytes()) == lf(run('git', 'show', BASE + ':' + path))
    manifest = 'work/jmbatch-android/app/src/main/AndroidManifest.xml'
    current = ET.parse(ROOT / manifest).getroot()
    old = ET.fromstring(run('git', 'show', BASE + ':' + manifest))
    ns = '{http://schemas.android.com/apk/res/android}'
    assert current.get(ns + 'versionName') == '0.6.13' and current.get(ns + 'versionCode') == '613'
    for key in ('versionName', 'versionCode'):
        current.set(ns + key, old.get(ns + key))
    assert ET.tostring(current) == ET.tostring(old)
    apk = DELIVERY / 'JMBatch-0.6.13-Android.apk'
    assert sha256(apk) == sha256(WORK / 'builds/android-0.6.13' / apk.name)
    log = (BUILD / 'android-build.log').read_text(encoding='utf-8', errors='replace')
    cert = 'cee4da716e0ac1d1b5fa3a8395e27040f18702264c433e1568c1d0b2e73d4f29'
    assert 'Signer #1 certificate SHA-256 digest: ' + cert in log
    assert "versionCode='613' versionName='0.6.13'" in log
    assert all('Verified using ' + s + ': true' in log for s in ('v2 scheme (APK Signature Scheme v2)', 'v3 scheme (APK Signature Scheme v3)'))
    with zipfile.ZipFile(apk) as archive:
        assert archive.testzip() is None
        assert all(marker in archive.read('classes.dex') for marker in (b'0.6.13', b'jumpFromDialog', b'postDialogJump', b'scrollTarget'))
    tracked = set(run('git', 'ls-files', '-z').decode().split('\0'))
    names = set(run('git', 'diff', '--cached', '--name-only').decode().splitlines())
    sources = {name: path for name, path in source_files('android').items() if path.relative_to(ROOT).as_posix() in tracked}
    with zipfile.ZipFile(DELIVERY / 'JMBatch-0.6.13-Android-source.zip') as archive:
        assert archive.testzip() is None and set(archive.namelist()) == set(sources)
        for name, path in sources.items():
            assert archive.read(name) == path.read_bytes(), name
            names.add(path.relative_to(ROOT).as_posix())
    for name in names:
        path = ROOT / name
        assert path.suffix.lower() not in ('.pem', '.jks', '.key', '.keystore', '.apk', '.zip')
        assert not re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', path.read_bytes())
        assert 'DnsTransportAuditRuntimeTest' not in name and 'TransportAuditServer' not in name
    notes = (WORK / 'release-android-0613/release-notes.md').read_bytes()
    assert (ROOT / 'CHANGELOG.md').read_bytes().startswith(notes)
    for name in ('更新日志-0.6.13.md', 'release-notes-android-0.6.13.md'):
        assert (DELIVERY / name).read_bytes() == notes
    plain = re.sub(r'(?m)^#{1,6} ', '', lf(notes).decode()).replace('- ', '• ')
    updates = (WORK / 'jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java').read_text(encoding='utf-8')
    assert json.loads(re.search(r'CURRENT_NOTES=("(?:\\.|[^"\\])*");', updates)[1]) == plain
    assert verify_manifest(DELIVERY, {'android':'0.6.13'})['tag'] == 'release-android-0.6.13'
    for line in (DELIVERY / 'SHA256-android-0.6.13.txt').read_text(encoding='utf-8').splitlines():
        digest, name = line.split('  ', 1)
        assert sha256(DELIVERY / name) == digest
    delivery = [dict(name=p.name, size=p.stat().st_size, sha256=sha256(p)) for p in sorted(DELIVERY.iterdir()) if p.is_file()]
    assert len(delivery) == 9
    save('audit.json', dict(ok=True, baseline=BASE, versions=VERSIONS, framework=suites, framework_total=62,
         original_layout_failures=2, apk_certificate_sha256=cert, packaged_sources=len(sources),
         allowed_paths=sorted(names), delivery=delivery, android_device_tested=False))
    print('Verified 62 framework cases, old layout failure, original signing,', len(sources), 'sources and nine delivery files')
elif mode in ('commit', 'remote'):
    audit = json.loads((REPORT / 'audit.json').read_text(encoding='utf-8'))
    head = run('git', 'rev-parse', 'HEAD').decode().strip()
    names = audit['allowed_paths']
    query = ''.join(head + ':' + name + '\n' for name in names).encode()
    stream = io.BytesIO(subprocess.run(['git', 'cat-file', '--batch'], input=query, cwd=ROOT, capture_output=True, check=True).stdout)
    checked = []
    for name in names:
        blob, kind, size = stream.readline().decode().strip().split()
        assert kind == 'blob'
        committed = stream.read(int(size)); assert stream.read(1) == b'\n'
        assert lf((ROOT / name).read_bytes()) == lf(committed), name
        checked.append(dict(path=name, blob=blob))
    assert stream.read() == b''
    if mode == 'remote':
        gh = str(WORK / 'github-cli/bin/gh.exe')
        assert json.loads(run(gh, 'api', 'repos/norskhelo/jmbatch/git/ref/heads/main'))['object']['sha'] == head
        tree = json.loads(run(gh, 'api', f'repos/norskhelo/jmbatch/git/trees/{head}?recursive=1'))
        assert not tree.get('truncated')
        blobs = {item['path']:item['sha'] for item in tree['tree'] if item['type'] == 'blob'}
        for item in checked:
            assert blobs[item['path']] == item['blob']
    save(mode + '-source-verification.json', dict(ok=True, commit=head, files=checked))
    print('Verified', len(checked), 'source/release files against', mode, head)
else:
    raise ValueError(mode)
