"""Verify native file-manager release, source contents, signing identity and push allowlist."""
from pathlib import Path
import hashlib,importlib.util,json,re,subprocess,zipfile
import xml.etree.ElementTree as ET
from release_paths import PROJECT as ROOT, WORK, sha256, verify_manifest

REPORT=ROOT/'outputs/reports/native-052-complete';REPORT.mkdir(parents=True,exist_ok=True)
DELIVERY=ROOT.parent/'Android/0.5.2'
checks=json.loads((ROOT/'outputs/reports/native-052-android-final/android-checks.json').read_text(encoding='utf-8'))
assert all(item['exit_code']==0 for item in checks)
log=(ROOT/'outputs/reports/native-052-android-final/android-build-and-host-tests.log').read_text(encoding='utf-8',errors='replace')
for text in ('System directory selection and fallback: 36 checks passed','SystemDirectoryHostTest: 52 checks passed','ImagePipelineTest: 111 checks passed','ResumeCacheTest:'):
    assert text in log,text
counts=[int(n) for n in re.findall(r'(\d+) checks(?: passed)?',log)]
counts += [int(n) for n in re.findall(r'Download pool checks: (\d+)',log)]
tools=WORK/'android-tools';java=next(tools.glob('jdk-*'))/'bin/java.exe';signer=next(tools.rglob('apksigner.jar'))
certs=[]
for version in ('0.5.1','0.5.2'):
    apk=ROOT.parent/f'Android/{version}/JMBatch-{version}-Android.apk'
    text=subprocess.run([str(java),'-jar',str(signer),'verify','--verbose','--print-certs',str(apk)],check=True,capture_output=True).stdout.decode('utf-8')
    (REPORT/f'apk-signature-{version}.txt').write_text(text,encoding='utf-8')
    certs.append(re.search(r'Signer #1 certificate SHA-256 digest: ([a-f0-9]+)',text).group(1))
assert certs[0]==certs[1]
apk=DELIVERY/'JMBatch-0.5.2-Android.apk'
assert apk.read_bytes()==(WORK/'builds/android-0.5.2/JMBatch-0.5.2-Android.apk').read_bytes()
with zipfile.ZipFile(apk) as archive:
    assert archive.testzip() is None
    dex=archive.read('classes.dex')
    for value in (b'Lapp/jmbatch/android/SystemDirectory;',b'openFileManager',b'openManagers',b'makeMainSelectorActivity',b'com.huawei.hidisk',b'android.intent.category.APP_FILES',b'0.5.2'):
        assert value in dex,value
    assert b'getLaunchIntentForPackage' not in dex
    assert b'com.hihonor.filemanager' not in dex and b'com.honor.filemanager' not in dex
badging=subprocess.run([str(next(tools.rglob('aapt.exe'))),'dump','badging',str(apk)],check=True,capture_output=True).stdout.decode('utf-8',errors='replace')
assert "name='app.jmbatch.android' versionCode='502' versionName='0.5.2'" in badging
(REPORT/'apk-badging.txt').write_text(badging,encoding='utf-8')
manifest=ET.parse(WORK/'jmbatch-android/app/src/main/AndroidManifest.xml').getroot()
old=ET.fromstring(subprocess.run(['git','show','25be036685cc98fda76d28686906f69936115df2:work/jmbatch-android/app/src/main/AndroidManifest.xml'],cwd=ROOT,capture_output=True,check=True).stdout)
ns='{http://schemas.android.com/apk/res/android}'
assert {p.get(ns+'name') for p in manifest.findall('uses-permission')}=={p.get(ns+'name') for p in old.findall('uses-permission')}
assert manifest.find("queries/package[@"+ns+"name='com.huawei.hidisk']") is None
spec=importlib.util.spec_from_file_location('packager',WORK/'package_network_update.py')
packager=importlib.util.module_from_spec(spec);spec.loader.exec_module(packager)
files=packager.source_files('android')
with zipfile.ZipFile(DELIVERY/'JMBatch-0.5.2-Android-source.zip') as archive:
    assert set(archive.namelist())==set(files)
    assert archive.testzip() is None
    assert any(n.endswith('/tests/test_system_directory.py') for n in files)
    for name,path in files.items():assert archive.read(name)==path.read_bytes(),name
notes=(WORK/'release-android-052/release-notes.md').read_bytes()
assert (ROOT/'CHANGELOG.md').read_bytes().startswith(notes)
assert notes==(DELIVERY/'release-notes-android-0.5.2.md').read_bytes()==(DELIVERY/'更新日志-0.5.2.md').read_bytes()
assert verify_manifest(DELIVERY,{'android':'0.5.2'})['tag']=='release-android-0.5.2'
for line in (DELIVERY/'SHA256-android-0.5.2.txt').read_text(encoding='utf-8').splitlines():
    expected,name=line.split('  ',1);assert expected==sha256(DELIVERY/name),name
allowed=set(files.values())
allowed.update(ROOT/p for p in ('README.md','CHANGELOG.md','work/release-android-052/release-notes.md',
    'work/package_network_update.py','work/scripts/maintenance/prepare_android_native_files_release.py',
    'work/scripts/maintenance/verify_android_native_files_online.py',
    'work/scripts/release/prepare_publication_android_052.py','work/scripts/release/publish_android_052.py',
    'work/scripts/release/verify_native_files_commit.py','work/scripts/release/audit_android_052.py'))
entries=[]
for path in sorted(allowed):
    name=path.relative_to(ROOT).as_posix();data=path.read_bytes()
    assert path.suffix not in ('.jks','.pem','.key','.apk','.zip') and not path.is_symlink()
    assert not re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',data)
    entries.append(dict(path=name,sha256=hashlib.sha256(data).hexdigest()))
(REPORT/'pathspec.txt').write_bytes(b'\0'.join(e['path'].encode('utf-8') for e in entries)+b'\0')
receipt=dict(ok=True,android='0.5.2',windows_unchanged='0.3.9',android_host_checks=sum(counts),
    apk_certificate_sha256=certs[0],packaged_source_files=len(files),allowed_paths=entries,
    android_device_tested=False,delivery=[dict(name=p.name,size=p.stat().st_size,sha256=sha256(p)) for p in sorted(DELIVERY.iterdir()) if p.is_file()])
(REPORT/'audit.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('AUDITED',sum(counts),'host checks;',len(files),'packaged sources;',len(entries),'allowed source/docs paths; original signing certificate; nine delivery files')
