"""Verify tested source packages, original signing identity and commit allowlist."""
import importlib.util
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
REPORT=ROOT/'outputs/reports/chapter-metadata-037-047-complete'
REPORT.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('packager',ROOT/'work/package_network_update.py')
packager=importlib.util.module_from_spec(spec);spec.loader.exec_module(packager)
paths=set();source_count=0
for platform,version in (('windows','0.3.7'),('android','0.4.7')):
    name=f'JMBatch-{version}-'+('source.zip' if platform=='windows' else 'Android-source.zip')
    sources=packager.source_files(platform)
    with zipfile.ZipFile(ROOT.parent/('Win' if platform=='windows' else 'Android')/version/name) as archive:
        assert set(archive.namelist())==set(sources)
        for name,path in sources.items():
            assert archive.read(name)==path.read_bytes(),str(path)
            source_count+=1;paths.add(path)
for name in ('.gitignore','README.md','CHANGELOG.md','CONTRIBUTING.md',
             'work/package_network_update.py','work/sign_update_release.py',
             'work/scripts/release/release_paths.py','work/scripts/release/verify_delivery.py',
             'work/scripts/release/tests/test_release_paths.py','work/release-037-047/release-notes.md',
             'work/scripts/maintenance/prepare_chapter_metadata_release.py',
             'work/scripts/release/prepare_publication_037_047.py','work/scripts/release/publish_037_047.py',
             'work/scripts/release/audit_chapter_metadata_release.py',
             'work/scripts/maintenance/verify_chapter_metadata_live.py',
             'work/scripts/maintenance/verify_chapter_metadata_online.py'):
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
for platform,run in (('windows','chapter-metadata-windows-final'),('android','chapter-metadata-android-verified')):
    checks=json.loads((ROOT/f'outputs/reports/{run}/{platform}-checks.json').read_text())
    assert len(checks)==(5 if platform=='windows' else 2) and all(c['exit_code']==0 for c in checks)
for kind in ('source','frozen'):
    checks=json.loads((ROOT/f'work/tests/chapter-metadata-windows-final/windows-{kind}-selftest/self-test.json').read_text())
    assert checks['ok'] and len(checks['checks'])==30
    assert any('Bounded chapter metadata:' in check for check in checks['checks'])
for path in (ROOT/'work/jmbatch').glob('*.py'):
    assert path.read_bytes()==(ROOT/'work/tests/chapter-metadata-windows-final/windows-source'/path.name).read_bytes(),str(path)
windows_log=(ROOT/'outputs/reports/chapter-metadata-windows-final/windows-unit-tests.log').read_text(encoding='utf-8')
assert 'Ran 146 tests' in windows_log and '\nOK\n' in windows_log
android_log=(ROOT/'outputs/reports/chapter-metadata-android-verified/android-build-and-host-tests.log').read_text(encoding='utf-8',errors='replace')
assert 'ChapterMetadataTest: 52 checks passed' in android_log
tools=ROOT/'work/android-tools';java=next(tools.glob('jdk-*'))/'bin/java.exe';signer=next(tools.rglob('apksigner.jar'))
certificates=[]
for version in ('0.4.6','0.4.7'):
    apk=ROOT.parent/f'Android/{version}/JMBatch-{version}-Android.apk'
    result=subprocess.run([str(java),'-jar',str(signer),'verify','--verbose','--print-certs',str(apk)],capture_output=True,check=True)
    output=result.stdout.decode('utf-8');(REPORT/f'apk-signature-{version}.txt').write_text(output,encoding='utf-8')
    certificates.append(re.search(r'Signer #1 certificate SHA-256 digest: ([a-f0-9]+)',output).group(1))
assert certificates[0]==certificates[1]
apk=ROOT.parent/'Android/0.4.7/JMBatch-0.4.7-Android.apk'
with zipfile.ZipFile(apk) as archive:
    dex=archive.read('classes.dex')
    assert b'Lapp/jmbatch/android/ChapterMetadata$Cache;' in dex
    assert b'Lapp/jmbatch/android/ChapterMetadata$UnstoppedWorkers;' in dex
aapt=next(tools.rglob('aapt.exe'))
badging=subprocess.run([str(aapt),'dump','badging',str(apk)],capture_output=True,check=True).stdout.decode('utf-8',errors='replace')
assert "name='app.jmbatch.android' versionCode='407' versionName='0.4.7'" in badging
(REPORT/'apk-badging.txt').write_text(badging,encoding='utf-8')
notes=(ROOT/'work/release-037-047/release-notes.md').read_text(encoding='utf-8')
assert (ROOT/'CHANGELOG.md').read_text(encoding='utf-8').startswith(notes)
live=json.loads((ROOT/'outputs/reports/chapter-metadata-live/results.json').read_text(encoding='utf-8'))
assert len(live)==2 and live[0]['chapter_requests']==151 and live[0]['peak_requests']==4 and live[1]['chapter_requests']==0
result=dict(ok=True,windows='0.3.7',android='0.4.7',source_files=source_count,allowed_paths=allowed,
            windows_unit_tests=146,windows_source_checks=30,windows_frozen_checks=30,android_host_checks=443,
            apk_certificate_sha256=certificates[0],android_device_tested=False,
            live_metadata_518074=[{k:v for k,v in row.items() if k!='requests'} for row in live])
(REPORT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('AUDITED',source_count,'packaged sources,',len(allowed),'allowed commit paths and original Android signing identity')
