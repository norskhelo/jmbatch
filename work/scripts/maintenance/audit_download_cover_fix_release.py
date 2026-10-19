"""Verify final test snapshots, signed packages and an explicit source allowlist."""
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

VERSIONS={'windows':'0.3.24','android':'0.6.4'}
REPORT=ROOT/'outputs/reports/download-cover-fix-0324-064-complete'
REPORT.mkdir(parents=True,exist_ok=True)
assert source_versions()==VERSIONS
for platform,count in [('windows',5),('android',2)]:
    checks=json.loads((ROOT/f'outputs/reports/download-cover-fix-{platform}-final/{platform}-checks.json').read_text())
    assert len(checks)==count and all(c['exit_code']==0 for c in checks),(platform,checks)
for name in ('source','frozen'):
    result=json.loads((ROOT/f'work/tests/download-cover-fix-windows-final/windows-{name}-selftest/self-test.json').read_text(encoding='utf-8'))
    assert result['ok'] and len(result['checks'])==42 and not result['network_used']
assert 'Ran 254 tests' in (ROOT/'outputs/reports/download-cover-fix-windows-final/windows-unit-tests.log').read_text(encoding='utf-8')
build=(ROOT/'outputs/reports/download-cover-fix-android-final/android-build-and-host-tests.log').read_text(encoding='utf-8',errors='replace')
assert "package: name='app.jmbatch.android' versionCode='604' versionName='0.6.4'" in build
assert 'Signer #1 certificate SHA-256 digest: cee4da716e0ac1d1b5fa3a8395e27040f18702264c433e1568c1d0b2e73d4f29' in build
assert all('Verified using '+s+': true' in build for s in ['v2 scheme (APK Signature Scheme v2)','v3 scheme (APK Signature Scheme v3)'])
assert '96 synthetic font/scale/width scenarios, 11962 checks passed' in build
runtime=(ROOT/'outputs/reports/download-cover-fix-runtime-final/runtime.log').read_text(encoding='utf-8')
assert 'Tests run: 102, Failures: 0, Errors: 0, Skipped: 0' in runtime
for source,snapshot,pattern in [
    (ROOT/'work/jmbatch',ROOT/'work/tests/download-cover-fix-windows-final/windows-source','*.py'),
    (ROOT/'work/jmbatch-android/app/src/main/java',ROOT/'work/tests/download-cover-fix-runtime-final/src/main/java','**/*.java')]:
    for path in source.glob(pattern):assert path.read_bytes()==(snapshot/path.relative_to(source)).read_bytes(),path
notes=(ROOT/'work/release-0324-064/release-notes.md').read_text(encoding='utf-8')
assert (ROOT/'CHANGELOG.md').read_text(encoding='utf-8').startswith(notes)
plain=re.sub(r'(?m)^#{1,6} ','',notes).replace('- ','• ')
for name in ['work/jmbatch/updates.py','work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java']:
    assert json.dumps(plain,ensure_ascii=False) in (ROOT/name).read_text(encoding='utf-8')
directories={p:delivery_dir(p,v) for p,v in VERSIONS.items()}
paths=set();files=[];source_count=0
for platform,version in VERSIONS.items():
    directory=directories[platform]
    assert verify_manifest(directory,VERSIONS,directories)['tag']=='release-0.3.24-0.6.4'
    assert (directory/'release-notes-0.3.24-0.6.4.md').read_text(encoding='utf-8')==notes
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
paths.update(['README.md','CHANGELOG.md','work/release-0324-064/release-notes.md',
    'work/scripts/maintenance/prepare_download_cover_fix_release.py',
    'work/scripts/maintenance/audit_download_cover_fix_release.py','work/scripts/maintenance/verify_download_cover_fix_online.py',
    'work/scripts/release/prepare_publication_0324_064.py','work/scripts/release/publish_0324_064.py',
    'work/scripts/release/verify_download_cover_fix_commit.py','work/scripts/maintenance/run_android_runtime_tests.py',
    'work/package_network_update.py','work/sign_update_release.py','work/scripts/release/release_paths.py'])
for name in paths:assert (ROOT/name).is_file(),name
result=dict(ok=True,versions=VERSIONS,source_files=source_count,allowed_paths=sorted(paths),removed_paths=[],files=files,
    windows_tests=254,windows_selftest_checks=42,android_host_checks=1630,android_framework_tests=102,android_device_tested=False)
(REPORT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(REPORT/'pathspec.txt').write_text('\n'.join(sorted(paths))+'\n',encoding='utf-8')
print('Verified',source_count,'packaged sources and',len(files),'deliverables;',len(paths),'allowed source/release paths')
