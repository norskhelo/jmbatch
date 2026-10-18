"""Verify reader startup release, production framework checks and original identities."""
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from release_paths import PROJECT as ROOT, WORK, sha256, verify_manifest, source_versions

REPORT=ROOT/'outputs/reports/reader-startup-0520-complete';REPORT.mkdir(parents=True,exist_ok=True)
DELIVERY=ROOT.parent/'Android/0.5.20'
BASE='edf041bfa42f1c5b1ab53aa75b14f20b1a5bfb62'
checks=json.loads((ROOT/'outputs/reports/reader-startup-0520-android-final/android-checks.json').read_text(encoding='utf-8'))
assert len(checks)==2 and all(c['exit_code']==0 for c in checks)
log=(ROOT/'outputs/reports/reader-startup-0520-android-final/android-build-and-host-tests.log').read_text(encoding='utf-8',errors='replace')
assert 'Action layout: 96 synthetic font/scale/width scenarios, 11962 checks passed (not Android rendering)' in log
counts=[int(n) for n in re.findall(r'(\d+) checks(?: passed)?','\n'.join(line for line in log.splitlines() if not line.startswith('Action layout:')))]
counts += [int(n) for n in re.findall(r'Download pool checks: (\d+)',log)]
assert sum(counts)==1347,sum(counts)
assert source_versions()=={'windows':'0.3.21','android':'0.5.20'}
runtime={}
for name,total in [('LibraryScreenRuntimeTest',9),('ReaderAlbumRuntimeTest',9)]:
    tree=ET.parse(WORK/f'tests/reader-startup-0520-runtime/target/surefire-reports/TEST-app.jmbatch.android.{name}.xml').getroot()
    result={k:int(tree.attrib[k]) for k in ('tests','errors','failures','skipped')}
    assert result==dict(tests=total,errors=0,failures=0,skipped=0),result
    runtime[name]=result
production=WORK/'jmbatch-android/app/src/main/java'
for path in production.rglob('*.java'):
    assert path.read_bytes()==(WORK/'tests/reader-startup-0520-runtime/src/main/java'/path.relative_to(production)).read_bytes(),path
tools=WORK/'android-tools';java=next(tools.glob('jdk-*'))/'bin/java.exe';signer=next(tools.rglob('apksigner.jar'));certs=[]
for version in ('0.5.19','0.5.20'):
    apk=ROOT.parent/f'Android/{version}/JMBatch-{version}-Android.apk'
    text=subprocess.run([str(java),'-jar',str(signer),'verify','--verbose','--print-certs',str(apk)],check=True,capture_output=True).stdout.decode('utf-8')
    (REPORT/f'apk-signature-{version}.txt').write_text(text,encoding='utf-8')
    assert 'Verified using v2 scheme (APK Signature Scheme v2): true' in text
    assert 'Verified using v3 scheme (APK Signature Scheme v3): true' in text
    certs.append(re.search(r'Signer #1 certificate SHA-256 digest: ([a-f0-9]+)',text).group(1))
assert certs[0]==certs[1]
apk=DELIVERY/'JMBatch-0.5.20-Android.apk'
assert apk.read_bytes()==(WORK/'builds/android-0.5.20/JMBatch-0.5.20-Android.apk').read_bytes()
with zipfile.ZipFile(apk) as archive:
    assert archive.testzip() is None
    for value in (b'ReaderAlbum;',b'checkBackground',b'LibraryGridView;',b'CoverDiskCache;',b'0.5.20'):assert value in archive.read('classes.dex'),value
badging=subprocess.run([str(next(tools.rglob('aapt.exe'))),'dump','badging',str(apk)],check=True,capture_output=True).stdout.decode('utf-8',errors='replace')
assert "name='app.jmbatch.android' versionCode='520' versionName='0.5.20'" in badging
(REPORT/'apk-badging.txt').write_text(badging,encoding='utf-8')
def original(path):return subprocess.run(['git','show',BASE+':'+path],cwd=ROOT,capture_output=True,check=True).stdout
manifest=ET.parse(WORK/'jmbatch-android/app/src/main/AndroidManifest.xml').getroot();old=ET.fromstring(original('work/jmbatch-android/app/src/main/AndroidManifest.xml'));ns='{http://schemas.android.com/apk/res/android}'
assert int(manifest.get(ns+'versionCode'))>int(old.get(ns+'versionCode'))
manifest.set(ns+'versionCode',old.get(ns+'versionCode'));manifest.set(ns+'versionName',old.get(ns+'versionName'));assert ET.tostring(manifest)==ET.tostring(old)
for path in ('work/jmbatch/update_trust.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/UpdateTrust.java'):
    assert (ROOT/path).read_bytes().replace(b'\r\n',b'\n')==original(path).replace(b'\r\n',b'\n')
assert not subprocess.run(['git','diff',BASE,'--','work/jmbatch'],cwd=ROOT,capture_output=True,check=True).stdout
spec=importlib.util.spec_from_file_location('packager',WORK/'package_network_update.py');packager=importlib.util.module_from_spec(spec);spec.loader.exec_module(packager);files=packager.source_files('android')
with zipfile.ZipFile(DELIVERY/'JMBatch-0.5.20-Android-source.zip') as archive:
    assert set(archive.namelist())==set(files) and archive.testzip() is None
    assert any(n.endswith('/ReaderAlbumRuntimeTest.java') for n in files)
    for name,path in files.items():assert archive.read(name)==path.read_bytes(),name
notes=(WORK/'release-android-0520/release-notes.md').read_bytes();assert (ROOT/'CHANGELOG.md').read_bytes().startswith(notes)
assert notes==(DELIVERY/'release-notes-android-0.5.20.md').read_bytes()==(DELIVERY/'更新日志-0.5.20.md').read_bytes()
assert (DELIVERY/'安卓使用说明-0.5.20.txt').read_bytes()==(WORK/'jmbatch-android/README.txt').read_bytes()
plain=re.sub(r'^#{1,2} ','',notes.decode('utf-8').replace('\r\n','\n'),flags=re.M).replace('- ','• ')
text=(production/'app/jmbatch/android/GithubUpdates.java').read_text(encoding='utf-8');assert json.loads(re.search(r'CURRENT_NOTES=("(?:\\.|[^"\\])*");',text).group(1))==plain
assert verify_manifest(DELIVERY,{'android':'0.5.20'})['tag']=='release-android-0.5.20'
for line in (DELIVERY/'SHA256-android-0.5.20.txt').read_text(encoding='utf-8').splitlines():
    digest,name=line.split('  ',1);assert digest==sha256(DELIVERY/name),name
readme=(ROOT/'README.md').read_text(encoding='utf-8')
assert 'release-android-0.5.20/JMBatch-0.5.20-Android.apk' in readme
assert 'release-0.3.21-0.5.19/JMBatch-0.3.21-Windows-x64.zip' in readme
assert 'JMBatch-0.5.19-Android.apk' not in readme
allowed=set(files.values())
allowed.update(ROOT/p for p in ('README.md','CHANGELOG.md','work/release-android-0520/release-notes.md',
    'work/scripts/maintenance/prepare_reader_startup_release.py','work/scripts/maintenance/run_android_runtime_tests.py',
    'work/scripts/maintenance/verify_reader_startup_online.py','work/scripts/release/prepare_publication_android_0520.py',
    'work/scripts/release/publish_android_0520.py','work/scripts/release/verify_reader_startup_commit.py','work/scripts/release/audit_android_0520.py'))
entries=[]
for path in sorted(allowed):
    name=path.relative_to(ROOT).as_posix();data=path.read_bytes()
    assert path.suffix not in ('.jks','.pem','.key','.apk','.zip') and not path.is_symlink()
    assert not re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',data)
    entries.append(dict(path=name,sha256=hashlib.sha256(data).hexdigest()))
(REPORT/'pathspec.txt').write_bytes(b'\0'.join(e['path'].encode('utf-8') for e in entries)+b'\0')
receipt=dict(ok=True,android='0.5.20',windows_unchanged='0.3.21',android_host_checks=sum(counts),
    apk_certificate_sha256=certs[0],packaged_source_files=len(files),allowed_paths=entries,
    android_device_tested=False,synthetic_font_scenarios=96,synthetic_layout_checks=11962,
    android_10_runtime=runtime,delivery=[dict(name=p.name,size=p.stat().st_size,sha256=sha256(p)) for p in sorted(DELIVERY.iterdir()) if p.is_file()])
assert len(receipt['delivery'])==9
(REPORT/'audit.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('AUDITED',sum(counts),'host checks;',len(files),'packaged sources;',len(entries),'source/docs paths; 18 framework tests; original signing certificate; nine delivery files')
