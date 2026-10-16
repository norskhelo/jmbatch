"""Audit built source, test evidence, signing identities and a narrow commit allowlist."""
import hashlib
import importlib.util
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
REPORT=ROOT/'outputs/reports/folder-save-038-048-complete'
REPORT.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('packager',ROOT/'work/package_network_update.py')
packager=importlib.util.module_from_spec(spec);spec.loader.exec_module(packager)
paths=set();source_count=0
for platform,version in (('windows','0.3.8'),('android','0.4.8')):
    filename=f'JMBatch-{version}-'+('source.zip' if platform=='windows' else 'Android-source.zip')
    sources=packager.source_files(platform)
    with zipfile.ZipFile(ROOT.parent/('Win' if platform=='windows' else 'Android')/version/filename) as archive:
        assert set(archive.namelist())==set(sources)
        for name,path in sources.items():
            assert archive.read(name)==path.read_bytes(),str(path)
            source_count+=1;paths.add(path)
for name in ('.gitignore','README.md','CHANGELOG.md','CONTRIBUTING.md',
             'work/package_network_update.py','work/sign_update_release.py',
             'work/scripts/release/release_paths.py','work/scripts/release/verify_delivery.py',
             'work/scripts/release/tests/test_release_paths.py','work/release-038-048/release-notes.md',
             'work/scripts/maintenance/prepare_folder_save_release.py','work/scripts/maintenance/verify_folder_save_io.py',
             'work/scripts/maintenance/verify_folder_save_online.py','work/scripts/release/audit_folder_save_release.py',
             'work/scripts/release/prepare_publication_038_048.py','work/scripts/release/publish_038_048.py'):
    paths.add(ROOT/name)
allowed=[]
for path in sorted(paths):
    relative=path.relative_to(ROOT).as_posix()
    assert path.is_file() and not path.is_symlink(),relative
    assert path.suffix.lower() not in ('.pem','.jks','.keystore','.key','.apk','.zip','.exe')
    assert not any(part in ('venv','android-tools','android-signing','update-signing','local-private-archives','outputs','builds','__pycache__') for part in Path(relative).parts)
    assert not re.search(rb'(?m)^\s*-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',path.read_bytes()),relative
    allowed.append(relative)
(REPORT/'pathspec.txt').write_bytes(b'\0'.join(p.encode('utf-8') for p in allowed)+b'\0')
for platform in ('windows','android'):
    checks=json.loads((ROOT/f'outputs/reports/folder-save-{platform}-final/{platform}-checks.json').read_text())
    assert len(checks)==(5 if platform=='windows' else 2) and all(c['exit_code']==0 for c in checks)
for kind in ('source','frozen'):
    checks=json.loads((ROOT/f'work/tests/folder-save-windows-final/windows-{kind}-selftest/self-test.json').read_text())
    assert checks['ok'] and len(checks['checks'])==31
    assert any('eight workers' in check for check in checks['checks'])
for path in (ROOT/'work/jmbatch').glob('*.py'):
    assert path.read_bytes()==(ROOT/'work/tests/folder-save-windows-final/windows-source'/path.name).read_bytes(),str(path)
windows_log=(ROOT/'outputs/reports/folder-save-windows-final/windows-unit-tests.log').read_text(encoding='utf-8')
assert 'Ran 148 tests' in windows_log and '\nOK\n' in windows_log
android_log=(ROOT/'outputs/reports/folder-save-android-final/android-build-and-host-tests.log').read_text(encoding='utf-8',errors='replace')
assert 'ChapterMetadataTest: 112 checks passed' in android_log and 'FolderSaveTest: 43 checks passed' in android_log
host_counts=[int(n) for n in re.findall(r'(\d+) checks(?: passed)?',android_log)]
host_counts += [int(n) for n in re.findall(r'Download pool checks: (\d+)',android_log)]
io=json.loads((ROOT/'outputs/reports/folder-save-io/verification.json').read_text(encoding='utf-8'))
assert io['ok'] and io['result']['all_files_equal'] and io['result']['save_and_cleanup_progress_complete']
assert io['source_sha256']==hashlib.sha256((ROOT/'work/jmbatch-android/app/src/main/java/app/jmbatch/android/FolderSave.java').read_bytes()).hexdigest()
tools=ROOT/'work/android-tools';java=next(tools.glob('jdk-*'))/'bin/java.exe';signer=next(tools.rglob('apksigner.jar'))
certificates=[]
for version in ('0.4.7','0.4.8'):
    apk=ROOT.parent/f'Android/{version}/JMBatch-{version}-Android.apk'
    output=subprocess.run([str(java),'-jar',str(signer),'verify','--verbose','--print-certs',str(apk)],capture_output=True,check=True).stdout.decode('utf-8')
    (REPORT/f'apk-signature-{version}.txt').write_text(output,encoding='utf-8')
    certificates.append(re.search(r'Signer #1 certificate SHA-256 digest: ([a-f0-9]+)',output).group(1))
assert certificates[0]==certificates[1]
apk=ROOT.parent/'Android/0.4.8/JMBatch-0.4.8-Android.apk'
with zipfile.ZipFile(apk) as archive:
    dex=archive.read('classes.dex')
    for value in (b'Lapp/jmbatch/android/FolderSave;',b'chapterWorkers',b'publishImages',b'cleanImageCache'):
        assert value in dex,value
badging=subprocess.run([str(next(tools.rglob('aapt.exe'))),'dump','badging',str(apk)],capture_output=True,check=True).stdout.decode('utf-8',errors='replace')
assert "name='app.jmbatch.android' versionCode='408' versionName='0.4.8'" in badging
(REPORT/'apk-badging.txt').write_text(badging,encoding='utf-8')
notes=(ROOT/'work/release-038-048/release-notes.md').read_text(encoding='utf-8')
assert (ROOT/'CHANGELOG.md').read_text(encoding='utf-8').startswith(notes)
receipt=dict(ok=True,windows='0.3.8',android='0.4.8',source_files=source_count,allowed_paths=allowed,
             windows_unit_tests=148,windows_source_checks=31,windows_frozen_checks=31,android_host_checks=sum(host_counts),
             apk_certificate_sha256=certificates[0],android_device_tested=False,synthetic_save_io=io)
(REPORT/'audit.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('AUDITED',source_count,'packaged sources,',len(allowed),'allowed paths;',sum(host_counts),'Android host checks; original signature retained')
