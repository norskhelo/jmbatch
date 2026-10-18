"""Audit source packages, final tests and the original identities before publication."""
import ast
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[3]
REPORT=ROOT/'outputs/reports/four_columns-0321-0519-complete';REPORT.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('packager',ROOT/'work/package_network_update.py')
packager=importlib.util.module_from_spec(spec);spec.loader.exec_module(packager)
paths=set();source_count=0
for relative in ('work/jmbatch/update_trust.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/UpdateTrust.java'):
    original=subprocess.run(['git','show','d3d437c:'+relative],cwd=ROOT,capture_output=True,check=True).stdout
    assert original.replace(b'\r\n',b'\n')==(ROOT/relative).read_bytes().replace(b'\r\n',b'\n'),'Update identity changed'
for platform,version in (('windows','0.3.21'),('android','0.5.19')):
    sources=packager.source_files(platform)
    name=f'JMBatch-{version}-'+('source.zip' if platform=='windows' else 'Android-source.zip')
    with zipfile.ZipFile(ROOT.parent/('Win' if platform=='windows' else 'Android')/version/name) as archive:
        assert set(archive.namelist())==set(sources)
        for name,path in sources.items():
            assert archive.read(name)==path.read_bytes(),str(path)
            paths.add(path);source_count+=1
for name in ('.gitignore','README.md','CHANGELOG.md','CONTRIBUTING.md',
    'work/package_network_update.py','work/sign_update_release.py','work/scripts/release/release_paths.py',
    'work/scripts/release/verify_delivery.py','work/scripts/release/tests/test_release_paths.py',
    'work/release-0321-0519/release-notes.md','work/scripts/maintenance/prepare_four_columns_release.py',
    'work/scripts/maintenance/verify_four_columns_online.py','work/scripts/maintenance/verify_android_four_columns_online.py',
    'work/scripts/maintenance/run_android_runtime_tests.py',
    'work/scripts/release/audit_four_columns_release.py','work/scripts/release/verify_four_columns_commit.py',
    'work/scripts/release/prepare_publication_0321_0519.py','work/scripts/release/publish_0321_0519.py'):
    paths.add(ROOT/name)
allowed=[]
for path in sorted(paths):
    assert path.is_file() and not path.is_symlink()
    assert path.suffix.lower() not in ('.pem','.jks','.keystore','.key','.apk','.zip','.exe')
    assert not any(part in ('venv','android-tools','android-signing','update-signing','outputs','builds','__pycache__') for part in path.relative_to(ROOT).parts)
    assert not re.search(rb'(?m)^\s*-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',path.read_bytes())
    allowed.append(path.relative_to(ROOT).as_posix())
(REPORT/'pathspec.txt').write_bytes(b'\0'.join(p.encode() for p in allowed)+b'\0')
for platform in ('windows','android'):
    data=json.loads((ROOT/f'outputs/reports/four-columns-{platform}-final/{platform}-checks.json').read_text(encoding='utf-8'))
    assert len(data)==(5 if platform=='windows' else 2) and all(c['exit_code']==0 for c in data)
for kind in ('source','frozen'):
    data=json.loads((ROOT/f'work/tests/four-columns-windows-final/windows-{kind}-selftest/self-test.json').read_text(encoding='utf-8'))
    assert data['ok'] and len(data['checks'])==42
for path in (ROOT/'work/jmbatch').glob('*.py'):
    assert path.read_bytes()==(ROOT/'work/tests/four-columns-windows-final/windows-source'/path.name).read_bytes(),str(path)
wlog=(ROOT/'outputs/reports/four-columns-windows-final/windows-unit-tests.log').read_text(encoding='utf-8')
assert 'Ran 234 tests' in wlog and '\nOK\n' in wlog
alog=(ROOT/'outputs/reports/four-columns-android-final/android-build-and-host-tests.log').read_text(encoding='utf-8',errors='replace')
for expected in ('LibraryRowsTest: 29 checks passed','LibraryInteractionTest: 46 checks passed',
                 '96 synthetic font/scale/width scenarios, 11962 checks passed'):
    assert expected in alog,expected
counts=[int(n) for n in re.findall(r'(\d+) checks(?: passed)?',alog)]
counts += [int(n) for n in re.findall(r'Download pool checks: (\d+)',alog)]
tools=ROOT/'work/android-tools';java=next(tools.glob('jdk-*'))/'bin/java.exe';signer=next(tools.rglob('apksigner.jar'))
certificates=[]
for version in ('0.5.18','0.5.19'):
    apk=ROOT.parent/f'Android/{version}/JMBatch-{version}-Android.apk'
    output=subprocess.run([str(java),'-jar',str(signer),'verify','--verbose','--print-certs',str(apk)],capture_output=True,check=True).stdout.decode('utf-8')
    (REPORT/f'apk-signature-{version}.txt').write_text(output,encoding='utf-8')
    certificates.append(re.search(r'Signer #1 certificate SHA-256 digest: ([a-f0-9]+)',output).group(1))
assert certificates[0]==certificates[1]
apk=ROOT.parent/'Android/0.5.19/JMBatch-0.5.19-Android.apk'
badging=subprocess.run([str(next(tools.rglob('aapt.exe'))),'dump','badging',str(apk)],capture_output=True,check=True).stdout.decode('utf-8',errors='replace')
assert "name='app.jmbatch.android' versionCode='519' versionName='0.5.19'" in badging
(REPORT/'apk-badging.txt').write_text(badging,encoding='utf-8')
with zipfile.ZipFile(apk) as archive:
    dex=archive.read('classes.dex')
    for label in ('DisplayMode','LibraryGridView','changeDisplay'):
        assert label.encode('utf-8') in dex,label
notes=(ROOT/'work/release-0321-0519/release-notes.md').read_text(encoding='utf-8')
assert (ROOT/'CHANGELOG.md').read_text(encoding='utf-8').startswith(notes)
plain=notes.replace('## ','').replace('# ','').replace('- ','• ')
tree=ast.parse((ROOT/'work/jmbatch/updates.py').read_text(encoding='utf-8'))
current=next(node.value.value for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CURRENT_NOTES' for t in node.targets))
assert current==plain
java=(ROOT/'work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java').read_text(encoding='utf-8')
assert json.loads(re.search(r'CURRENT_NOTES=("(?:\\.|[^"\\])*");',java).group(1))==plain
receipt=dict(ok=True,windows='0.3.21',android='0.5.19',source_files=source_count,allowed_paths=allowed,
    removed_paths=['work/jmbatch-android/app/src/main/java/app/jmbatch/android/ComicLayout.java'],
    windows_unit_tests=234,windows_source_checks=42,windows_frozen_checks=42,android_host_checks=sum(counts)-11962,
    android_layout_scenarios=96,android_grid_scenarios=0,android_layout_checks=11962,
    apk_certificate_sha256=certificates[0],android_device_tested=False)
import xml.etree.ElementTree as ET
runtime=ET.parse(ROOT/'work/tests/four-columns-runtime-verified/target/surefire-reports/TEST-app.jmbatch.android.LibraryScreenRuntimeTest.xml').getroot()
assert int(runtime.attrib['tests'])==9 and int(runtime.attrib['failures'])==0 and int(runtime.attrib['errors'])==0
receipt['android_framework_tests']=9
for name in receipt['removed_paths']:assert not (ROOT/name).exists()
(REPORT/'audit.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('AUDITED',source_count,'packaged sources,',len(allowed),'allowed paths;',sum(counts),'Android host/layout checks; original signatures retained')
