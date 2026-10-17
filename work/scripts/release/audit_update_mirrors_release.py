"""Audit source packages, build receipts, APK identity, and the commit allowlist."""
import importlib.util
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
REPORT=ROOT/'outputs/reports/update-mirrors-0313-057-complete';REPORT.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('packager',ROOT/'work/package_network_update.py')
packager=importlib.util.module_from_spec(spec);spec.loader.exec_module(packager)
paths=set();source_count=0
for relative in ('work/jmbatch/update_trust.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/UpdateTrust.java'):
    original=subprocess.run(['git','show','90d81bb1eb42ac218e3761db27d42371296518cd:'+relative],cwd=ROOT,capture_output=True,check=True).stdout
    assert original.replace(b'\r\n',b'\n')==(ROOT/relative).read_bytes().replace(b'\r\n',b'\n'),'Update public key changed'
for platform,version in (('windows','0.3.13'),('android','0.5.7')):
    sources=packager.source_files(platform)
    name=f'JMBatch-{version}-'+('source.zip' if platform=='windows' else 'Android-source.zip')
    with zipfile.ZipFile(ROOT.parent/('Win' if platform=='windows' else 'Android')/version/name) as archive:
        assert set(archive.namelist())==set(sources)
        for name,path in sources.items():
            assert archive.read(name)==path.read_bytes(),str(path)
            source_count+=1;paths.add(path)
for name in ('.gitignore','README.md','CHANGELOG.md','CONTRIBUTING.md',
    'work/package_network_update.py','work/sign_update_release.py','work/scripts/release/release_paths.py',
    'work/scripts/release/verify_delivery.py','work/scripts/release/tests/test_release_paths.py',
    'work/release-0313-057/release-notes.md','work/scripts/maintenance/prepare_update_mirrors_release.py',
    'work/scripts/maintenance/verify_update_mirrors_online.py','work/scripts/maintenance/verify_android_update_mirrors_online.py','work/scripts/release/audit_update_mirrors_release.py','work/scripts/release/verify_update_mirrors_commit.py',
    'work/scripts/release/prepare_publication_0313_057.py','work/scripts/release/publish_0313_057.py'):
    paths.add(ROOT/name)
paths.add(ROOT/'work/scripts/maintenance/verify_update_mirror_routes.py')
allowed=[]
for path in sorted(paths):
    relative=path.relative_to(ROOT).as_posix()
    assert path.is_file() and not path.is_symlink()
    assert path.suffix.lower() not in ('.pem','.jks','.keystore','.key','.apk','.zip','.exe')
    assert not any(part in ('venv','android-tools','android-signing','update-signing','outputs','builds','__pycache__') for part in path.relative_to(ROOT).parts)
    assert not re.search(rb'(?m)^\s*-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',path.read_bytes())
    allowed.append(relative)
(REPORT/'pathspec.txt').write_bytes(b'\0'.join(p.encode() for p in allowed)+b'\0')
for platform in ('windows','android'):
    run='update-mirrors-windows-verified' if platform=='windows' else 'update-mirrors-android-verified'
    data=json.loads((ROOT/f'outputs/reports/{run}/{platform}-checks.json').read_text())
    assert len(data)==(5 if platform=='windows' else 2) and all(c['exit_code']==0 for c in data)
for kind in ('source','frozen'):
    data=json.loads((ROOT/f'work/tests/update-mirrors-windows-verified/windows-{kind}-selftest/self-test.json').read_text())
    assert data['ok'] and len(data['checks'])==37
    assert all(len(seams)==6 and all(s['gap']==0 for s in seams) for seams in data['reader_scroll_seams'].values())
    assert set(data['reader_scroll_seams'])=={'images','zip','pdf'}
    assert data['reader_paging']['transitions']==100 and data['reader_paging']['failure_retains_display']
for path in (ROOT/'work/jmbatch').glob('*.py'):
    assert path.read_bytes()==(ROOT/'work/tests/update-mirrors-windows-verified/windows-source'/path.name).read_bytes(),str(path)
wlog=(ROOT/'outputs/reports/update-mirrors-windows-verified/windows-unit-tests.log').read_text(encoding='utf-8')
assert 'Ran 190 tests' in wlog and '\nOK\n' in wlog
alog=(ROOT/'outputs/reports/update-mirrors-android-verified/android-build-and-host-tests.log').read_text(encoding='utf-8',errors='replace')
assert 'CacheCleanupTest: 50 checks passed' in alog
assert 'CancelServiceTest: 38 checks passed' in alog
assert 'ReaderPagerTest: 29 checks passed' in alog
assert 'UpdateDownloadTest: 76 checks passed' in alog
counts=[int(n) for n in re.findall(r'(\d+) checks(?: passed)?',alog)]
counts += [int(n) for n in re.findall(r'Download pool checks: (\d+)',alog)]
tools=ROOT/'work/android-tools';java=next(tools.glob('jdk-*'))/'bin/java.exe';signer=next(tools.rglob('apksigner.jar'))
certificates=[]
for version in ('0.5.6','0.5.7'):
    apk=ROOT.parent/f'Android/{version}/JMBatch-{version}-Android.apk'
    output=subprocess.run([str(java),'-jar',str(signer),'verify','--verbose','--print-certs',str(apk)],capture_output=True,check=True).stdout.decode('utf-8')
    (REPORT/f'apk-signature-{version}.txt').write_text(output,encoding='utf-8')
    certificates.append(re.search(r'Signer #1 certificate SHA-256 digest: ([a-f0-9]+)',output).group(1))
assert certificates[0]==certificates[1]
apk=ROOT.parent/'Android/0.5.7/JMBatch-0.5.7-Android.apk'
with zipfile.ZipFile(apk) as archive:
    dex=archive.read('classes.dex')
    for value in (b'Lapp/jmbatch/android/UpdateDownload;',b'https://ghfast.top/',b'https://gh-proxy.com/'):
        assert value in dex,value
    for value in (b'Lapp/jmbatch/android/CancelledTaskCleanup;',b'Lapp/jmbatch/android/WorkerDrain;',b'discardRequested',b'cleanupUri',b'toRealPath',b'Lapp/jmbatch/android/ReaderPager;',b'Lapp/jmbatch/android/ReaderRequests;',b'setTranslationX'):
        assert value in dex,value
badging=subprocess.run([str(next(tools.rglob('aapt.exe'))),'dump','badging',str(apk)],capture_output=True,check=True).stdout.decode('utf-8',errors='replace')
assert "name='app.jmbatch.android' versionCode='507' versionName='0.5.7'" in badging
(REPORT/'apk-badging.txt').write_text(badging,encoding='utf-8')
assert (ROOT/'CHANGELOG.md').read_text(encoding='utf-8').startswith((ROOT/'work/release-0313-057/release-notes.md').read_text(encoding='utf-8'))
receipt=dict(ok=True,windows='0.3.13',android='0.5.7',source_files=source_count,allowed_paths=allowed,
    windows_unit_tests=190,windows_source_checks=37,windows_frozen_checks=37,android_host_checks=sum(counts),
    apk_certificate_sha256=certificates[0],android_device_tested=False)
(REPORT/'audit.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('AUDITED',source_count,'packaged sources,',len(allowed),'allowed paths;',sum(counts),'Android host checks; original signature retained')
