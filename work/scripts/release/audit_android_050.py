"""Verify Android-only artifacts, source allowlist, build evidence and trust identity."""
from pathlib import Path
import hashlib,importlib.util,json,re,subprocess,zipfile
from release_paths import PROJECT as ROOT, WORK, sha256, verify_manifest

REPORT=ROOT/'outputs/reports/throughput-050-complete';REPORT.mkdir(parents=True,exist_ok=True)
DELIVERY=ROOT.parent/'Android/0.5.0'
checks=json.loads((ROOT/'outputs/reports/throughput-050-android-verified/android-checks.json').read_text(encoding='utf-8'))
assert all(item['exit_code']==0 for item in checks)
log=(ROOT/'outputs/reports/throughput-050-android-verified/android-build-and-host-tests.log').read_text(encoding='utf-8',errors='replace')
for text in ('ImageMemoryTest: 11 checks passed','ImagePipelineTest: 111 checks passed','ImageRoutesTest: 71 checks passed','JmApiTransportTest: 45 checks passed','ResumeCacheTest:'):
    assert text in log,text
counts=[int(n) for n in re.findall(r'(\d+) checks(?: passed)?',log)]
counts += [int(n) for n in re.findall(r'Download pool checks: (\d+)',log)]
tools=WORK/'android-tools';java=next(tools.glob('jdk-*'))/'bin/java.exe';signer=next(tools.rglob('apksigner.jar'))
certs=[]
for version in ('0.4.9','0.5.0'):
    apk=ROOT.parent/f'Android/{version}/JMBatch-{version}-Android.apk'
    text=subprocess.run([str(java),'-jar',str(signer),'verify','--verbose','--print-certs',str(apk)],check=True,capture_output=True).stdout.decode('utf-8')
    (REPORT/f'apk-signature-{version}.txt').write_text(text,encoding='utf-8')
    certs.append(re.search(r'Signer #1 certificate SHA-256 digest: ([a-f0-9]+)',text).group(1))
assert certs[0]==certs[1]
apk=DELIVERY/'JMBatch-0.5.0-Android.apk'
assert apk.read_bytes()==(WORK/'builds/android-0.5.0/JMBatch-0.5.0-Android.apk').read_bytes()
with zipfile.ZipFile(apk) as archive:
    assert archive.testzip() is None
    dex=archive.read('classes.dex')
    for value in (b'Lapp/jmbatch/android/ImagePipeline;',b'Lapp/jmbatch/android/ImageMemory;',b'Lapp/jmbatch/android/ImageRoutes;',b'getContentLengthLong',b'0.5.0'):
        assert value in dex,value
badging=subprocess.run([str(next(tools.rglob('aapt.exe'))),'dump','badging',str(apk)],check=True,capture_output=True).stdout.decode('utf-8',errors='replace')
assert "name='app.jmbatch.android' versionCode='500' versionName='0.5.0'" in badging
(REPORT/'apk-badging.txt').write_text(badging,encoding='utf-8')
spec=importlib.util.spec_from_file_location('packager',WORK/'package_network_update.py')
packager=importlib.util.module_from_spec(spec);spec.loader.exec_module(packager)
files=packager.source_files('android')
with zipfile.ZipFile(DELIVERY/'JMBatch-0.5.0-Android-source.zip') as archive:
    assert set(archive.namelist())==set(files)
    assert archive.testzip() is None
    for name,path in files.items():assert archive.read(name)==path.read_bytes(),name
notes=(WORK/'release-android-050/release-notes.md').read_bytes()
assert (ROOT/'CHANGELOG.md').read_bytes().startswith(notes)
assert notes==(DELIVERY/'release-notes-android-0.5.0.md').read_bytes()==(DELIVERY/'更新日志-0.5.0.md').read_bytes()
assert verify_manifest(DELIVERY,{'android':'0.5.0'})['tag']=='release-android-0.5.0'
for line in (DELIVERY/'SHA256-android-0.5.0.txt').read_text(encoding='utf-8').splitlines():
    expected,name=line.split('  ',1);assert expected==sha256(DELIVERY/name),name
allowed=set(files.values())
allowed.update(ROOT/p for p in ('README.md','CHANGELOG.md','work/release-android-050/release-notes.md',
    'work/scripts/maintenance/prepare_android_throughput_release.py','work/scripts/maintenance/finalize_android_throughput_notes.py',
    'work/scripts/release/prepare_publication_android_050.py','work/scripts/release/publish_android_050.py',
    'work/scripts/release/make_android_050_publication_recipe.py','work/scripts/release/audit_android_050.py'))
entries=[]
for path in sorted(allowed):
    name=path.relative_to(ROOT).as_posix();data=path.read_bytes()
    assert path.suffix not in ('.jks','.pem','.key','.apk','.zip') and not path.is_symlink()
    assert not re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',data)
    entries.append(dict(path=name,sha256=hashlib.sha256(data).hexdigest()))
(REPORT/'pathspec.txt').write_bytes(b'\0'.join(e['path'].encode('utf-8') for e in entries)+b'\0')
receipt=dict(ok=True,android='0.5.0',windows_unchanged='0.3.9',android_host_checks=sum(counts),
    apk_certificate_sha256=certs[0],packaged_source_files=len(files),allowed_paths=entries,
    android_device_tested=False,delivery=[dict(name=p.name,size=p.stat().st_size,sha256=sha256(p)) for p in sorted(DELIVERY.iterdir()) if p.is_file()])
(REPORT/'audit.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('AUDITED',sum(counts),'host checks;',len(files),'packaged sources;',len(entries),'allowed source/docs paths; original signing certificate; nine delivery files')
