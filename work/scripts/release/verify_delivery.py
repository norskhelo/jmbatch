"""Verify the current per-platform local deliverables without network access."""
import argparse
import ast
import json
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
from release_paths import (PROJECT, WORK, delivery_dir, package_name, sha256,
                           source_versions, verify_manifest)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--original-release', type=Path, help='Also prove original signed installers were preserved')
args = parser.parse_args()
versions = source_versions()
directories = {p: delivery_dir(p, v) for p, v in versions.items()}
files = []
for platform, directory in directories.items():
    verify_manifest(directory, versions, directories)
    checksum = directory / f'SHA256-{platform}-{versions[platform]}.txt'
    checked = []
    for line in checksum.read_text(encoding='utf-8').splitlines():
        digest, name = line.split('  ', 1)
        if Path(name).name != name or sha256(directory / name) != digest:
            raise ValueError('Invalid delivery checksum: ' + line)
        checked.append(name)
    expected = {package_name(platform, versions[platform]), 'update-manifest.json', 'update-manifest.sig'}
    if not expected.issubset(checked):
        raise ValueError('Delivery checksum omits a signed asset')
    for name in checked + [checksum.name]:
        path = directory / name
        files.append(dict(platform=platform, path=str(path), sha256=sha256(path), size=path.stat().st_size))
        if path.suffix in ('.zip', '.apk'):
            with zipfile.ZipFile(path) as bundle:
                if bundle.testzip() is not None:
                    raise ValueError('Invalid ZIP CRC: ' + name)
                for entry in bundle.namelist():
                    item = Path(entry)
                    if (item.suffix.lower() in ('.jks', '.keystore', '.key') or
                            item.name.lower() == 'release-private.pem'):
                        raise ValueError('Private signing asset found: ' + entry)
                    if item.suffix.lower() == '.pem' and b'PRIVATE KEY' in bundle.read(entry):
                        raise ValueError('Private PEM found: ' + entry)
                    if name.endswith('source.zip') and ('.venv' in item.parts or '__pycache__' in item.parts):
                        raise ValueError('Unexpected source cache: ' + entry)
for name in ('update-manifest.json', 'update-manifest.sig'):
    data = [(directory / name).read_bytes() for directory in directories.values()]
    if len(set(data)) != 1:
        raise ValueError('Shared signed bytes differ: ' + name)
if args.original_release:
    verify_manifest(args.original_release, versions)
    for platform, number in versions.items():
        for name in (package_name(platform, number), 'update-manifest.json', 'update-manifest.sig'):
            if sha256(directories[platform] / name) != sha256(args.original_release / name):
                raise ValueError('Original signed bytes changed: ' + name)
    historical_manifest = json.loads((PROJECT / 'FILE_MANIFEST.json').read_text(encoding='utf-8-sig'))
    original_files = [e for e in historical_manifest['files']
                      if Path(e['path']).parent == Path('outputs')]
    for entry in original_files:
        if sha256(PROJECT / entry['path']) != entry['sha256']:
            raise ValueError('Historical output changed: ' + entry['path'])
sources = list((WORK / 'scripts/release').rglob('*.py'))
sources += [WORK / name for name in ('package_network_update.py', 'sign_update_release.py',
            'run_frozen_selftest_0111.py', 'publish_network_update.py', 'live_network_update_check.py',
            'jmbatch-android/build.py', 'scripts/maintenance/check_development.py')]
for path in sources:
    ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
result = dict(ok=True, versions=versions, files=files, shared_signed_bytes_identical=True,
              original_release_preserved=bool(args.original_release),
              private_signing_assets_absent=True, python_sources_parsed=len(sources),
              pushed=False, published=False)
report = PROJECT / 'outputs/reports/delivery' / '-'.join(f'{p}-{v}' for p, v in versions.items())
report.mkdir(parents=True, exist_ok=True)
(report / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('VERIFIED', len(files), 'delivery files;', len(sources), 'Python scripts;', report / 'verification.json')
