"""Verify packaged sources, test receipts, original identities and commit allowlist."""
import ast
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[3]
REPORT=ROOT/'outputs/reports/library_interaction-0316-0512-complete';REPORT.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('packager',ROOT/'work/package_network_update.py')
packager=importlib.util.module_from_spec(spec);spec.loader.exec_module(packager)
paths=set();source_count=0
for relative in ('work/jmbatch/update_trust.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/UpdateTrust.java'):
    original=subprocess.run(['git','show','f33ca00:'+relative],cwd=ROOT,capture_output=True,check=True).stdout
    assert original.replace(b'\r\n',b'\n')==(ROOT/relative).read_bytes().replace(b'\r\n',b'\n'),'Update identity changed'
for platform,version in (('windows','0.3.16'),('android','0.5.12')):
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
    'work/release-0316-0512/release-notes.md','work/scripts/maintenance/prepare_library_interaction_release.py','work/scripts/maintenance/preview_library_interaction.py',
    'work/scripts/maintenance/verify_library_interaction_online.py','work/scripts/maintenance/verify_android_library_interaction_online.py',
    'work/scripts/release/audit_library_interaction_release.py','work/scripts/release/verify_library_interaction_commit.py',
    'work/scripts/release/prepare_publication_0316_0512.py','work/scripts/release/publish_0316_0512.py'):
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
    data=json.loads((ROOT/(f'outputs/reports/library-{platform}-' + ('complete' if platform=='windows' else 'verified') + f'/{platform}-checks.json')).read_text(encoding='utf-8'))
    assert len(data)==(5 if platform=='windows' else 2) and all(c['exit_code']==0 for c in data)
for kind in ('source','frozen'):
    data=json.loads((ROOT/f'work/tests/library-windows-complete/windows-{kind}-selftest/self-test.json').read_text(encoding='utf-8'))
    assert data['ok'] and len(data['checks'])==39
    assert any('Library real Tk events' in text for text in data['checks'])
for path in (ROOT/'work/jmbatch').glob('*.py'):
    assert path.read_bytes()==(ROOT/'work/tests/library-windows-complete/windows-source'/path.name).read_bytes(),str(path)
wlog=(ROOT/'outputs/reports/library-windows-complete/windows-unit-tests.log').read_text(encoding='utf-8')
assert 'Ran 203 tests' in wlog and '\nOK\n' in wlog
alog=(ROOT/'outputs/reports/library-android-verified/android-build-and-host-tests.log').read_text(encoding='utf-8',errors='replace')
assert 'LibraryInteractionTest: 31 checks passed' in alog
assert '96 synthetic font/scale/width scenarios, 11962 checks passed' in alog
counts=[int(n) for n in re.findall(r'(\d+) checks(?: passed)?',alog)]
counts += [int(n) for n in re.findall(r'Download pool checks: (\d+)',alog)]
tools=ROOT/'work/android-tools';java=next(tools.glob('jdk-*'))/'bin/java.exe';signer=next(tools.rglob('apksigner.jar'))
certificates=[]
for version in ('0.5.11','0.5.12'):
    apk=ROOT.parent/f'Android/{version}/JMBatch-{version}-Android.apk'
    output=subprocess.run([str(java),'-jar',str(signer),'verify','--verbose','--print-certs',str(apk)],capture_output=True,check=True).stdout.decode('utf-8')
    (REPORT/f'apk-signature-{version}.txt').write_text(output,encoding='utf-8')
    certificates.append(re.search(r'Signer #1 certificate SHA-256 digest: ([a-f0-9]+)',output).group(1))
assert certificates[0]==certificates[1]
apk=ROOT.parent/'Android/0.5.12/JMBatch-0.5.12-Android.apk'
badging=subprocess.run([str(next(tools.rglob('aapt.exe'))),'dump','badging',str(apk)],capture_output=True,check=True).stdout.decode('utf-8',errors='replace')
assert "name='app.jmbatch.android' versionCode='512' versionName='0.5.12'" in badging
(REPORT/'apk-badging.txt').write_text(badging,encoding='utf-8')
with zipfile.ZipFile(apk) as archive:
    dex=archive.read('classes.dex')
    for label in ('点击漫画开始阅读，长按进入批量处理。','更多操作','完成'):
        assert label.encode('utf-8') in dex,label
notes=(ROOT/'work/release-0316-0512/release-notes.md').read_text(encoding='utf-8')
assert (ROOT/'CHANGELOG.md').read_text(encoding='utf-8').startswith(notes)
plain=notes.replace('## ','').replace('# ','').replace('- ','• ')
tree=ast.parse((ROOT/'work/jmbatch/updates.py').read_text(encoding='utf-8'))
current=next(node.value.value for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CURRENT_NOTES' for t in node.targets))
assert current==plain
java=(ROOT/'work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java').read_text(encoding='utf-8')
assert json.loads(re.search(r'CURRENT_NOTES=("(?:\\.|[^"\\])*");',java).group(1))==plain
receipt=dict(ok=True,windows='0.3.16',android='0.5.12',source_files=source_count,allowed_paths=allowed,
    windows_unit_tests=203,windows_source_checks=39,windows_frozen_checks=39,android_host_checks=sum(counts)-11962,
    android_layout_scenarios=96,android_layout_checks=11962,
    apk_certificate_sha256=certificates[0],android_device_tested=False)
(REPORT/'audit.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('AUDITED',source_count,'packaged sources,',len(allowed),'allowed paths;',sum(counts),'Android host/layout checks; original signatures retained')
