"""Audit scoped evidence, final build inputs, signed packages and source allowlist."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[3]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'work'))
from package_network_update import source_files
sys.path.insert(0,str(ROOT/'work/scripts/release'))
from release_paths import source_versions,verify_manifest,sha256,delivery_dir

VERSIONS={'windows':'0.3.25','android':'0.6.5'}
REPORT=ROOT/'outputs/reports/tile-cover-0325-065-complete'
REPORT.mkdir(parents=True,exist_ok=True)
assert source_versions()==VERSIONS
assert 'Ran 15 tests' in (ROOT/'outputs/reports/tile-cover-scaling/windows-final.log').read_text(encoding='utf-8')
assert 'Tests run: 6, Failures: 0, Errors: 0, Skipped: 0' in (ROOT/'outputs/reports/tile-cover-scaling-runtime-final/runtime.log').read_text(encoding='utf-8')
# The previous focused regressions tested exactly these unchanged production files.
for name in ('work/jmbatch/display_view.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/LibraryScreen.java'):
    previous=subprocess.run(['git','show','992947e:'+name],cwd=ROOT,capture_output=True,check=True).stdout
    assert previous.replace(b'\r\n',b'\n')==(ROOT/name).read_bytes().replace(b'\r\n',b'\n'),name
for platform,count in (('windows',3),('android',1)):
    report=ROOT/f'outputs/reports/tile-cover-0325-065-{platform}'
    checks=json.loads((report/'checks.json').read_text())
    assert len(checks)==count and all(c['exit_code']==0 for c in checks)
    hashes=json.loads((report/'source-hashes.json').read_text())
    for name,digest in hashes.items():assert sha256(ROOT/name)==digest,name
for kind in ('source','frozen'):
    data=json.loads((ROOT/f'work/tests/tile-cover-0325-065-windows/{kind}-selftest/self-test.json').read_text(encoding='utf-8'))
    assert data['ok'] and len(data['checks'])==4 and data['version']=='0.3.25' and not data['network_used']
log=(ROOT/'outputs/reports/tile-cover-0325-065-android/android-build.log').read_text(encoding='utf-8',errors='replace')
assert "package: name='app.jmbatch.android' versionCode='605' versionName='0.6.5'" in log
assert 'Signer #1 certificate SHA-256 digest: cee4da716e0ac1d1b5fa3a8395e27040f18702264c433e1568c1d0b2e73d4f29' in log
assert all('Verified using '+s+': true' in log for s in ('v2 scheme (APK Signature Scheme v2)','v3 scheme (APK Signature Scheme v3)'))
notes=(ROOT/'work/release-0325-065/release-notes.md').read_text(encoding='utf-8')
assert (ROOT/'CHANGELOG.md').read_text(encoding='utf-8').startswith(notes)
plain=re.sub(r'(?m)^#{1,6} ','',notes).replace('- ','• ')
for name in ('work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java'):
    assert json.dumps(plain,ensure_ascii=False) in (ROOT/name).read_text(encoding='utf-8')
directories={p:delivery_dir(p,v) for p,v in VERSIONS.items()}
paths=set();files=[];source_count=0
for platform,version in VERSIONS.items():
    directory=directories[platform]
    assert verify_manifest(directory,VERSIONS,directories)['tag']=='release-0.3.25-0.6.5'
    assert (directory/'release-notes-0.3.25-0.6.5.md').read_text(encoding='utf-8')==notes
    source=source_files(platform)
    name=f'JMBatch-{version}-'+('source.zip' if platform=='windows' else 'Android-source.zip')
    with zipfile.ZipFile(directory/name) as archive:
        assert archive.testzip() is None and set(archive.namelist())==set(source)
        for name,path in source.items():
            assert archive.read(name)==path.read_bytes(),name
            assert path.suffix.lower() not in ('.pem','.key','.jks','.keystore'),name
            paths.add(path.relative_to(ROOT).as_posix());source_count+=1
    for line in (directory/f'SHA256-{platform}-{version}.txt').read_text(encoding='utf-8').splitlines():
        digest,name=line.split('  ',1);path=directory/name;assert sha256(path)==digest
        files.append(dict(path=str(path),size=path.stat().st_size,sha256=digest))
for name in ('update-manifest.sig','update-manifest.json'):
    assert (directories['windows']/name).read_bytes()==(directories['android']/name).read_bytes()
paths.update(['README.md','CHANGELOG.md','work/release-0325-065/release-notes.md',
    'work/scripts/maintenance/prepare_tile_cover_release.py','work/scripts/maintenance/build_tile_cover_release.py',
    'work/scripts/maintenance/audit_tile_cover_release.py','work/scripts/maintenance/verify_tile_cover_online.py',
    'work/scripts/release/prepare_publication_0325_065.py','work/scripts/release/publish_0325_065.py',
    'work/scripts/release/verify_tile_cover_commit.py','work/scripts/maintenance/run_android_runtime_tests.py',
    'work/package_network_update.py','work/sign_update_release.py','work/scripts/release/release_paths.py'])
for name in paths:assert (ROOT/name).is_file(),name
result=dict(ok=True,versions=VERSIONS,source_files=source_count,allowed_paths=sorted(paths),removed_paths=[],files=files,
    windows_regression_tests=15,windows_source_and_frozen_checks=4,android_framework_tests=6,android_row_checks=32,
    regression_baseline='992947e',android_device_tested=False)
(REPORT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(REPORT/'pathspec.txt').write_text('\n'.join(sorted(paths))+'\n',encoding='utf-8')
print('Verified',source_count,'packaged sources and',len(files),'deliverables;',len(paths),'allowed source/release paths')
