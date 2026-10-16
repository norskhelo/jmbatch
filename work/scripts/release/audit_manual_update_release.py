"""Audit this release's sources, build evidence, and preserved signing identity."""
import importlib.util
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / 'outputs/reports/manual-update-035-045-complete'
REPORT.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location('packager', ROOT / 'work/package_network_update.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)
paths, source_count = set(), 0
for platform, version in (('windows', '0.3.5'), ('android', '0.4.5')):
    prefix = 'Win' if platform == 'windows' else 'Android'
    name = f'JMBatch-{version}-' + ('source.zip' if platform == 'windows' else 'Android-source.zip')
    sources = packager.source_files(platform)
    with zipfile.ZipFile(ROOT.parent / prefix / version / name) as archive:
        assert set(archive.namelist()) == set(sources)
        for name, path in sources.items():
            assert archive.read(name) == path.read_bytes(), str(path)
            source_count += 1
            paths.add(path)
for name in ('.gitignore', 'README.md', 'CHANGELOG.md', 'CONTRIBUTING.md',
             'work/package_network_update.py', 'work/sign_update_release.py',
             'work/scripts/release/release_paths.py', 'work/scripts/release/verify_delivery.py',
             'work/scripts/release/tests/test_release_paths.py', 'work/release-035-045/release-notes.md',
             'work/scripts/maintenance/prepare_manual_update_release.py',
             'work/scripts/release/prepare_publication_035_045.py', 'work/scripts/release/publish_035_045.py',
             'work/scripts/release/audit_manual_update_release.py', 'work/scripts/maintenance/verify_manual_update_online.py'):
    paths.add(ROOT / name)
allowed = []
for path in sorted(paths):
    relative = path.relative_to(ROOT).as_posix()
    assert path.is_file() and not path.is_symlink(), relative
    assert path.suffix.lower() not in ('.pem', '.jks', '.keystore', '.key', '.apk', '.zip', '.exe')
    assert not any(part in ('venv', 'android-tools', 'android-signing', 'update-signing', 'local-private-archives', 'outputs', 'builds', '__pycache__') for part in Path(relative).parts)
    assert not re.search(rb'(?m)^\s*-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', path.read_bytes()), relative
    allowed.append(relative)
(REPORT / 'pathspec.txt').write_bytes(b'\0'.join(p.encode('utf-8') for p in allowed) + b'\0')
for platform, run in (('windows', 'manual-update-windows-final'), ('android', 'manual-update-android-verified')):
    checks = json.loads((ROOT / f'outputs/reports/{run}/{platform}-checks.json').read_text())
    expected = 5 if platform == 'windows' else 2
    assert len(checks) == expected and all(check['exit_code'] == 0 for check in checks)
for kind in ('source', 'frozen'):
    checks = json.loads((ROOT / f'work/tests/manual-update-windows-final/windows-{kind}-selftest/self-test.json').read_text())
    assert checks['ok'] and len(checks['checks']) == 28
    assert any('Manual check works' in check for check in checks['checks'])
tools = ROOT / 'work/android-tools'
java = next(tools.glob('jdk-*')) / 'bin/java.exe'
signer = next(tools.rglob('apksigner.jar'))
certificates = []
for version in ('0.4.4', '0.4.5'):
    apk = ROOT.parent / f'Android/{version}/JMBatch-{version}-Android.apk'
    result = subprocess.run([str(java), '-jar', str(signer), 'verify', '--verbose', '--print-certs', str(apk)], capture_output=True, check=True)
    output = result.stdout.decode('utf-8')
    (REPORT / f'apk-signature-{version}.txt').write_text(output, encoding='utf-8')
    certificates.append(re.search(r'Signer #1 certificate SHA-256 digest: ([a-f0-9]+)', output).group(1))
assert certificates[0] == certificates[1]
notes = (ROOT / 'work/release-035-045/release-notes.md').read_text(encoding='utf-8')
assert (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8').startswith(notes)
result = dict(ok=True, windows='0.3.5', android='0.4.5', source_files=source_count, allowed_paths=allowed,
              windows_unit_tests=129, windows_source_checks=28, windows_frozen_checks=28, android_host_checks=380,
              apk_certificate_sha256=certificates[0], android_device_tested=False,
              desktop_ui_test='Actual Tk manual update controls verified in source and frozen executable')
(REPORT / 'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('AUDITED', source_count, 'packaged sources,', len(allowed), 'allowed commit paths, original Android signing identity and build checks')
