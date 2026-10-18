"""Audit final installers, tested source snapshots, identities and publication paths."""
import ast
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from release_paths import PROJECT as ROOT, WORK, source_versions, verify_manifest, sha256

REPORT=ROOT/'outputs/reports/chapter-delete-0322-0521-complete'
REPORT.mkdir(parents=True,exist_ok=True)
VERSIONS={'windows':'0.3.22','android':'0.5.21'}
assert source_versions()==VERSIONS
spec=importlib.util.spec_from_file_location('packager',WORK/'package_network_update.py')
packager=importlib.util.module_from_spec(spec);spec.loader.exec_module(packager)
paths=set();source_count=0
for relative in ('work/jmbatch/update_trust.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/UpdateTrust.java'):
    old=subprocess.run(['git','show','3209f4c:'+relative],cwd=ROOT,capture_output=True,check=True).stdout
    assert old.replace(b'\r\n',b'\n')==(ROOT/relative).read_bytes().replace(b'\r\n',b'\n')
directories={p:ROOT.parent/('Win' if p=='windows' else 'Android')/v for p,v in VERSIONS.items()}
for platform,version in VERSIONS.items():
    sources=packager.source_files(platform)
    source_name=f'JMBatch-{version}-'+('source.zip' if platform=='windows' else 'Android-source.zip')
    with zipfile.ZipFile(directories[platform]/source_name) as archive:
        assert set(archive.namelist())==set(sources) and archive.testzip() is None
        for name,path in sources.items():
            assert archive.read(name)==path.read_bytes(),name
            paths.add(path);source_count+=1
    verify_manifest(directories[platform],VERSIONS,directories)
for name in ('README.md','CHANGELOG.md','work/release-0322-0521/release-notes.md',
             'work/scripts/maintenance/prepare_chapter_delete_release.py',
             'work/scripts/maintenance/verify_chapter_delete_online.py',
             'work/scripts/maintenance/verify_android_chapter_delete_online.py',
             'work/scripts/maintenance/run_android_runtime_tests.py',
             'work/scripts/release/prepare_publication_0322_0521.py',
             'work/scripts/release/publish_0322_0521.py',
             'work/scripts/release/verify_chapter_delete_commit.py',
             'work/scripts/release/audit_chapter_delete_release.py'):
    paths.add(ROOT/name)
allowed=[]
for path in sorted(paths):
    assert path.is_file() and not path.is_symlink()
    assert path.suffix.lower() not in ('.pem','.key','.jks','.keystore','.zip','.apk','.exe')
    assert not re.search(rb'(?m)^\s*-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',path.read_bytes())
    allowed.append(path.relative_to(ROOT).as_posix())
(REPORT/'pathspec.txt').write_bytes(b'\0'.join(name.encode('utf-8') for name in allowed)+b'\0')
runs={'windows':'chapter-delete-windows-verified','android':'chapter-delete-android-final'}
for platform,run in runs.items():
    checks=json.loads((ROOT/f'outputs/reports/{run}/{platform}-checks.json').read_text(encoding='utf-8'))
    assert len(checks)==(5 if platform=='windows' else 2) and all(c['exit_code']==0 for c in checks)
for kind in ('source','frozen'):
    report=json.loads((WORK/f'tests/{runs["windows"]}/windows-{kind}-selftest/self-test.json').read_text(encoding='utf-8'))
    assert report['ok'] and len(report['checks'])==42
for path in (WORK/'jmbatch').glob('*.py'):
    assert path.read_bytes()==(WORK/f'tests/{runs["windows"]}/windows-source'/path.name).read_bytes(),path
wlog=(ROOT/f'outputs/reports/{runs["windows"]}/windows-unit-tests.log').read_text(encoding='utf-8')
assert 'Ran 242 tests' in wlog and '\nOK\n' in wlog
alog=(ROOT/f'outputs/reports/{runs["android"]}/android-build-and-host-tests.log').read_text(encoding='utf-8',errors='replace')
assert '96 synthetic font/scale/width scenarios, 11962 checks passed' in alog
counts=[int(n) for n in re.findall(r'(\d+) checks(?: passed)?','\n'.join(line for line in alog.splitlines() if not line.startswith('Action layout:')))]
counts += [int(n) for n in re.findall(r'Download pool checks: (\d+)',alog)]
assert sum(counts)==1347,sum(counts)
runtime_run=WORK/'tests/chapter-delete-runtime-ui-final'
runtime={}
for name,count in [('ChapterDeletionRuntimeTest',8),('LibraryScreenRuntimeTest',10),('ReaderAlbumRuntimeTest',9)]:
    root=ET.parse(runtime_run/f'target/surefire-reports/TEST-app.jmbatch.android.{name}.xml').getroot()
    result={k:int(root.attrib[k]) for k in ('tests','failures','errors','skipped')}
    assert result==dict(tests=count,failures=0,errors=0,skipped=0),result
    runtime[name]=result
for path in (WORK/'jmbatch-android/app/src/main/java').rglob('*.java'):
    assert path.read_bytes()==(runtime_run/'src/main/java'/path.relative_to(WORK/'jmbatch-android/app/src/main/java')).read_bytes(),path
tools=WORK/'android-tools';java=next(tools.glob('jdk-*'))/'bin/java.exe';signer=next(tools.rglob('apksigner.jar'));certificates=[]
for version in ('0.5.20','0.5.21'):
    apk=ROOT.parent/f'Android/{version}/JMBatch-{version}-Android.apk'
    output=subprocess.run([str(java),'-jar',str(signer),'verify','--verbose','--print-certs',str(apk)],capture_output=True,check=True).stdout.decode('utf-8')
    (REPORT/f'apk-signature-{version}.txt').write_text(output,encoding='utf-8')
    assert 'Verified using v2 scheme (APK Signature Scheme v2): true' in output and 'Verified using v3 scheme (APK Signature Scheme v3): true' in output
    certificates.append(re.search(r'Signer #1 certificate SHA-256 digest: ([a-f0-9]+)',output).group(1))
assert certificates[0]==certificates[1]
apk=directories['android']/'JMBatch-0.5.21-Android.apk'
assert apk.read_bytes()==(WORK/'builds/android-0.5.21/JMBatch-0.5.21-Android.apk').read_bytes()
badging=subprocess.run([str(next(tools.rglob('aapt.exe'))),'dump','badging',str(apk)],capture_output=True,check=True).stdout.decode('utf-8',errors='replace')
assert "name='app.jmbatch.android' versionCode='521' versionName='0.5.21'" in badging
(REPORT/'apk-badging.txt').write_text(badging,encoding='utf-8')
with zipfile.ZipFile(apk) as archive:
    dex=archive.read('classes.dex')
    for word in (b'ChapterDeletion;',b'replaceChapters',b'deleteChapters',b'0.5.21'):assert word in dex
with zipfile.ZipFile(directories['windows']/'JMBatch-0.3.22-Windows-x64.zip') as archive:
    executables=[name for name in archive.namelist() if name.endswith('/JMBatch.exe')]
    assert len(executables)==1
    assert archive.read(executables[0])==(WORK/'builds/windows-0.3.22/dist/JMBatch/JMBatch.exe').read_bytes()
from PyInstaller.archive.readers import CArchiveReader
reader=CArchiveReader(str(WORK/'builds/windows-0.3.22/dist/JMBatch/JMBatch.exe'))
pyz=reader.open_embedded_archive(next(name for name in reader.toc if name.endswith('.pyz')))
for name in ('chapter_delete','chapter_delete_ui'):assert name in pyz.toc
notes=(WORK/'release-0322-0521/release-notes.md').read_text(encoding='utf-8')
assert (ROOT/'CHANGELOG.md').read_text(encoding='utf-8').startswith(notes)
plain=notes.replace('## ','').replace('# ','').replace('- ','• ')
tree=ast.parse((WORK/'jmbatch/updates.py').read_text(encoding='utf-8'))
assert next(n.value.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CURRENT_NOTES' for t in n.targets))==plain
text=(WORK/'jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java').read_text(encoding='utf-8')
assert json.loads(re.search(r'CURRENT_NOTES=("(?:\\.|[^"\\])*");',text).group(1))==plain
delivery=[]
for platform,directory in directories.items():
    assert (directory/'release-notes-0.3.22-0.5.21.md').read_text(encoding='utf-8')==notes
    for line in (directory/f'SHA256-{platform}-{VERSIONS[platform]}.txt').read_text(encoding='utf-8').splitlines():
        digest,name=line.split('  ',1);assert digest==sha256(directory/name)
    delivery.extend(dict(platform=platform,name=p.name,sha256=sha256(p),size=p.stat().st_size) for p in sorted(directory.iterdir()) if p.is_file())
assert len(delivery)==18
receipt=dict(ok=True,versions=VERSIONS,source_files=source_count,allowed_paths=allowed,removed_paths=[],
    windows_unit_tests=242,windows_source_checks=42,windows_frozen_checks=42,android_host_checks=sum(counts),
    android_layout_checks=11962,android_framework=runtime,apk_certificate_sha256=certificates[0],
    android_device_tested=False,delivery=delivery)
(REPORT/'audit.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('AUDITED',source_count,'packaged sources;',len(allowed),'commit paths; 18 delivery files; original signing identity')
