"""Audit the exact local Android 0.6.0 delivery and explicit source allowlist."""
from pathlib import Path
import hashlib,json,re,sys,zipfile,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[3]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'work'))
from package_network_update import source_files
sys.path.insert(0,str(ROOT/'work/scripts/release'))
from release_paths import verify_manifest,source_versions,sha256
REPORT=ROOT/'outputs/reports/permissions-060-complete';REPORT.mkdir(parents=True,exist_ok=True)
build_report=ROOT/'outputs/reports/permissions-060-android-first'
checks=json.loads((build_report/'android-checks.json').read_text());assert len(checks)==2 and all(c['exit_code']==0 for c in checks)
build=(build_report/'android-build-and-host-tests.log').read_text(encoding='utf-8',errors='replace')
assert 'Network cause classification: 38 checks passed' in build
assert 'Probe engine: 16 checks passed' in build
assert "package: name='app.jmbatch.android' versionCode='600' versionName='0.6.0'" in build
assert 'Signer #1 certificate SHA-256 digest: cee4da716e0ac1d1b5fa3a8395e27040f18702264c433e1568c1d0b2e73d4f29' in build
assert all('Verified using '+s+': true' in build for s in ['v2 scheme (APK Signature Scheme v2)','v3 scheme (APK Signature Scheme v3)'])
assert '96 synthetic font/scale/width scenarios, 11962 checks passed' in build
runtime=ROOT/'outputs/reports/permissions-060-runtime-final/runtime.log'
assert 'Tests run: 57, Failures: 0, Errors: 0, Skipped: 0' in runtime.read_text(encoding='utf-8')
# Runtime snapshot must match feature code; application version/notes were already final.
java=ROOT/'work/jmbatch-android/app/src/main/java'
snapshot=ROOT/'work/tests/permissions-060-runtime-final/src/main/java'
for p in java.rglob('*.java'):assert p.read_bytes()==(snapshot/p.relative_to(java)).read_bytes(),p
assert source_versions()=={'windows':'0.3.22','android':'0.6.0'}
ns='{http://schemas.android.com/apk/res/android}'
manifest=ET.parse(ROOT/'work/jmbatch-android/app/src/main/AndroidManifest.xml').getroot()
perms={p.get(ns+'name') for p in manifest.findall('uses-permission')}
assert not {'android.permission.MANAGE_EXTERNAL_STORAGE','android.permission.READ_PHONE_STATE','android.permission.ACCESS_FINE_LOCATION'} & perms
assert next(a for a in manifest.find('application').findall('activity') if a.get(ns+'name')=='.PermissionActivity').get(ns+'exported')=='false'
dest=ROOT.parent/'Android/0.6.0';signed=verify_manifest(dest,{'android':'0.6.0'});assert signed['tag']=='release-android-0.6.0'
source=source_files('android')
with zipfile.ZipFile(dest/'JMBatch-0.6.0-Android-source.zip') as z:
    assert z.testzip() is None and set(z.namelist())==set(source)
    for name,p in source.items():assert z.read(name)==p.read_bytes(),name
paths=set(p.relative_to(ROOT).as_posix() for p in source.values())
paths.update(['README.md','CHANGELOG.md','work/release-android-060/release-notes.md','work/scripts/maintenance/prepare_permissions_release.py','work/scripts/maintenance/audit_permissions_release.py','work/scripts/maintenance/verify_permissions_online.py','work/scripts/release/prepare_publication_android_060.py','work/scripts/release/publish_android_060.py','work/scripts/release/verify_permissions_commit.py'])
for name in ('work/package_network_update.py','work/sign_update_release.py','work/scripts/release/release_paths.py','work/scripts/maintenance/check_development.py','work/scripts/maintenance/run_android_runtime_tests.py'):paths.add(name)
for p in dest.glob('SHA256*.txt'):
    for line in p.read_text(encoding='utf-8').splitlines():
        expected,name=line.split('  ',1);assert sha256(dest/name)==expected,name
host=sum(int(m.group(1)) for line in build.splitlines() if not line.startswith('Action layout:') for m in [re.search(r'(\d+) checks',line)] if m)+25
audit={'main_host_checks':host,'new_network_cause_checks':38,'network_probe_checks':16,'runtime_tests':57,'permission_runtime_tests':24,'layout_scenarios':96,'layout_assertions':11962,'source_package_files':len(source),'android':'0.6.0','versionCode':600,'windows':'0.3.22','real_device_tested':False,'published':False,'allowed_paths':[{'path':n,'sha256':sha256(ROOT/n)} for n in sorted(paths)],'delivery_files':[{'name':p.name,'size':p.stat().st_size,'sha256':sha256(p)} for p in sorted(dest.iterdir()) if p.is_file()]}
(REPORT/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in audit.items() if k not in ('allowed_paths','delivery_files')},ensure_ascii=False));print('Allowed source files',len(paths),'delivery files',len(audit['delivery_files']))
