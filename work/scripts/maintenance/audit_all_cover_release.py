"""Audit unchanged regression inputs, finished builds, signed packages and sources."""
from pathlib import Path
import json
import re
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'work'))
from package_network_update import source_files
sys.path.insert(0,str(ROOT/'work/scripts/release'))
from release_paths import source_versions,verify_manifest,sha256,delivery_dir

VERSIONS={'windows':'0.3.27','android':'0.6.7'}
REPORT=ROOT/'outputs/reports/all-cover-0327-067-complete';REPORT.mkdir(parents=True,exist_ok=True)
assert source_versions()==VERSIONS
previous=ROOT/'outputs/reports/all-cover-displays'
regression=json.loads((previous/'completion.json').read_text())
assert regression['ok'] and regression['windows_checks']==25 and regression['android_framework_tests']==20 and regression['android_host_checks']==37
# Only release metadata and packaged self-checks have changed since these regressions.
inputs=json.loads((previous/'source-audit.json').read_text())
reused=[]
for item in inputs['files']:
    if item['path'].startswith('work/'):
        assert sha256(ROOT/item['path'])==item['sha256'],item['path']
        reused.append(item['path'])
assert 'Tests run: 20, Failures: 0, Errors: 0, Skipped: 0' in (ROOT/'outputs/reports/all-cover-displays-runtime/runtime.log').read_text(encoding='utf-8')
for name in ('CollectionCover.java','MainActivity.java','LibraryScreen.java'):
    relative='app/jmbatch/android/'+name
    assert (ROOT/'work/tests/all-cover-displays-runtime/src/main/java'/relative).read_bytes()==(ROOT/'work/jmbatch-android/app/src/main/java'/relative).read_bytes()
for platform,count in (('windows',3),('android',1)):
    report=ROOT/f'outputs/reports/all-cover-0327-067-{platform}'
    checks=json.loads((report/'checks.json').read_text())
    assert len(checks)==count and all(c['exit_code']==0 for c in checks)
    for name,digest in json.loads((report/'source-hashes.json').read_text()).items():assert sha256(ROOT/name)==digest,name
for kind in ('source','frozen'):
    data=json.loads((ROOT/f'work/tests/all-cover-0327-067-windows/{kind}-selftest/self-test.json').read_text(encoding='utf-8'))
    assert data['ok'] and len(data['checks'])==7 and data['version']=='0.3.27' and not data['network_used']
log=(ROOT/'outputs/reports/all-cover-0327-067-android/android-build.log').read_text(encoding='utf-8',errors='replace')
assert "package: name='app.jmbatch.android' versionCode='607' versionName='0.6.7'" in log
assert 'Signer #1 certificate SHA-256 digest: cee4da716e0ac1d1b5fa3a8395e27040f18702264c433e1568c1d0b2e73d4f29' in log
assert all('Verified using '+s+': true' in log for s in ('v2 scheme (APK Signature Scheme v2)','v3 scheme (APK Signature Scheme v3)'))
notes=(ROOT/'work/release-0327-067/release-notes.md').read_text(encoding='utf-8')
assert (ROOT/'CHANGELOG.md').read_text(encoding='utf-8').startswith(notes)
plain=re.sub(r'(?m)^#{1,6} ','',notes).replace('- ','• ')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    assert json.dumps(plain,ensure_ascii=False) in (ROOT/name).read_text(encoding='utf-8')
directories={p:delivery_dir(p,v) for p,v in VERSIONS.items()}
paths=set();files=[];source_count=0
for platform,version in VERSIONS.items():
    directory=directories[platform]
    assert verify_manifest(directory,VERSIONS,directories)['tag']=='release-0.3.27-0.6.7'
    assert (directory/'release-notes-0.3.27-0.6.7.md').read_text(encoding='utf-8')==notes
    sources=source_files(platform)
    archive_name=f'JMBatch-{version}-'+('source.zip' if platform=='windows' else 'Android-source.zip')
    with zipfile.ZipFile(directory/archive_name) as archive:
        assert archive.testzip() is None and set(archive.namelist())==set(sources)
        for name,path in sources.items():
            assert archive.read(name)==path.read_bytes(),name
            assert path.suffix.lower() not in ('.pem','.key','.jks','.keystore'),name
            paths.add(path.relative_to(ROOT).as_posix());source_count+=1
    for line in (directory/f'SHA256-{platform}-{version}.txt').read_text(encoding='utf-8').splitlines():
        digest,name=line.split('  ',1);path=directory/name;assert sha256(path)==digest
        files.append(dict(path=str(path),size=path.stat().st_size,sha256=digest))
for name in ('update-manifest.sig','update-manifest.json'):
    assert (directories['windows']/name).read_bytes()==(directories['android']/name).read_bytes()
paths.update(['README.md','CHANGELOG.md','work/release-0327-067/release-notes.md',
    'work/scripts/maintenance/prepare_all_cover_release.py','work/scripts/maintenance/build_all_cover_release.py',
    'work/scripts/maintenance/audit_all_cover_release.py','work/scripts/maintenance/verify_all_cover_online.py',
    'work/scripts/release/prepare_publication_0327_067.py','work/scripts/release/publish_0327_067.py',
    'work/scripts/release/verify_all_cover_commit.py','work/scripts/maintenance/run_android_runtime_tests.py',
    'work/package_network_update.py','work/sign_update_release.py','work/scripts/release/release_paths.py'])
for name in paths:assert (ROOT/name).is_file(),name
result=dict(ok=True,versions=VERSIONS,source_files=source_count,allowed_paths=sorted(paths),removed_paths=[],files=files,
    reused_regression_inputs=reused,windows_regression_tests=25,windows_source_and_frozen_checks=7,android_framework_tests=20,android_row_checks=37,
    android_device_tested=False)
(REPORT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(REPORT/'pathspec.txt').write_text('\n'.join(sorted(paths))+'\n',encoding='utf-8')
print('Verified',source_count,'packaged sources and',len(files),'deliverables;',len(paths),'allowed paths')
