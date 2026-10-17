"""Package the authorized Android-only release; preserve Windows 0.3.9 artifacts."""
import subprocess,sys
from release_paths import PROJECT, WORK, delivery_dir, sha256, distribute, verify_manifest

TAG='release-android-0.5.2'
OUT=WORK/'builds/android-0.5.2/packages'
NOTES='release-notes-android-0.5.2.md'
notes=WORK/'release-android-052/release-notes.md'
assert (PROJECT/'CHANGELOG.md').read_text(encoding='utf-8').startswith(notes.read_text(encoding='utf-8'))
subprocess.run([sys.executable,str(WORK/'package_network_update.py'),'--platform','android','--notes',str(notes),'--tag',TAG],check=True,cwd=PROJECT)
(OUT/NOTES).write_bytes(notes.read_bytes())
names=['JMBatch-0.5.2-Android.apk',NOTES,'update-manifest.json','update-manifest.sig']
checksum='SHA256-release-android-0.5.2.txt'
(OUT/checksum).write_text(''.join(sha256(OUT/name)+'  '+name+'\n' for name in names),encoding='utf-8')
directory=delivery_dir('android','0.5.2')
distribute([(OUT/name,directory/name) for name in (NOTES,checksum)])
path=directory/'SHA256-android-0.5.2.txt'
existing=[line.split('  ',1)[1] for line in path.read_text(encoding='utf-8').splitlines()]
names=list(dict.fromkeys(existing+[NOTES,checksum]))
path.write_text(''.join(sha256(directory/name)+'  '+name+'\n' for name in names),encoding='utf-8')
verify_manifest(directory,{'android':'0.5.2'})
print('Prepared five release assets and nine Android delivery files')
