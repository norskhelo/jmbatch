"""Package this release with its original signing identities and matching notes."""
import subprocess
import sys
from release_paths import PROJECT, WORK, delivery_dir, sha256, distribute, verify_manifest

VERSIONS = {'windows': '0.3.8', 'android': '0.4.8'}
TAG = 'release-0.3.8-0.4.8'
OUT = WORK / 'builds/windows-0.3.8-android-0.4.8/packages'
NOTES = 'release-notes-0.3.8-0.4.8.md'
notes = WORK / 'release-038-048/release-notes.md'
assert (PROJECT / 'CHANGELOG.md').read_text(encoding='utf-8').startswith(notes.read_text(encoding='utf-8'))
subprocess.run([sys.executable, str(WORK / 'package_network_update.py'), '--notes', str(notes), '--tag', TAG], check=True, cwd=PROJECT)
(OUT / NOTES).write_bytes(notes.read_bytes())
names = ['JMBatch-0.3.8-Windows-x64.zip', 'JMBatch-0.4.8-Android.apk', NOTES, 'update-manifest.json', 'update-manifest.sig']
checksum = 'SHA256-release-0.3.8-0.4.8.txt'
(OUT / checksum).write_text(''.join(sha256(OUT / name) + '  ' + name + '\n' for name in names), encoding='utf-8')
directories = {p: delivery_dir(p,v) for p,v in VERSIONS.items()}
distribute([(OUT/name, directory/name) for directory in directories.values() for name in (NOTES, checksum)])
for platform,directory in directories.items():
    path = directory / f'SHA256-{platform}-{VERSIONS[platform]}.txt'
    existing = [line.split('  ',1)[1] for line in path.read_text(encoding='utf-8').splitlines()]
    names = list(dict.fromkeys(existing + [NOTES, checksum]))
    path.write_text(''.join(sha256(directory/name)+'  '+name+'\n' for name in names),encoding='utf-8')
    verify_manifest(directory,VERSIONS,directories)
print('Prepared six release assets and matching platform deliverables')
