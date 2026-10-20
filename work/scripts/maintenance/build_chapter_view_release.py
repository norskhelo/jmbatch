"""Build this release with focused checks; no publishing or external downloads."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
platform=sys.argv[1]
assert platform in ('windows','android')
number={'windows':'0.3.28','android':'0.6.10'}[platform]
build=ROOT/'work/builds'/f'{platform}-{number}'
test=ROOT/'work/tests'/f'chapter-view-0328-0610-{platform}'
report=ROOT/'outputs/reports'/f'chapter-view-0328-0610-{platform}'
for p in (build,test/'temp',report):p.mkdir(parents=True,exist_ok=True)
env=os.environ.copy()
env.update(TEMP=str(test/'temp'),TMP=str(test/'temp'),PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',
           PYTHONIOENCODING='utf-8',JM_BATCH_HOME=str(test/'app-home'),PYINSTALLER_CONFIG_DIR=str(build/'pyinstaller-cache'))
python=ROOT/'work/venv/Scripts/python.exe'
results=[]
def run(name,args,cwd=ROOT,timeout=900):
    print('RUN',name,flush=True);start=time.monotonic()
    with (report/(name+'.log')).open('w',encoding='utf-8') as stream:
        result=subprocess.run([str(a) for a in args],cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
    results.append(dict(name=name,exit_code=result.returncode,seconds=round(time.monotonic()-start,2)))
    (report/'checks.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    print('PASS' if result.returncode==0 else 'FAIL',name,flush=True)
    if result.returncode:
        print((report/(name+'.log')).read_text(encoding='utf-8',errors='replace')[-5000:])
        raise SystemExit(result.returncode)
source=ROOT/'work'/('jmbatch' if platform=='windows' else 'jmbatch-android')
paths=list(source.glob('*.py')) if platform=='windows' else list((source/'app/src').rglob('*.java'))
snapshot={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
(report/'source-hashes.json').write_text(json.dumps(snapshot,indent=2)+'\n')
if platform=='windows':
    run('source-chapter-view-selftest',[python,source/'app.py','--self-test-chapter-view',test/'source-selftest'])
    run('windows-build',[python,'-m','PyInstaller','--noconfirm','--clean','--workpath',build/'intermediates','--distpath',build/'dist',ROOT/'work/JMBatch.spec'],cwd=ROOT/'work')
    run('frozen-chapter-view-selftest',[build/'dist/JMBatch/JMBatch.exe','--self-test-chapter-view',test/'frozen-selftest'])
    for kind in ('source','frozen'):
        data=json.loads((test/(kind+'-selftest')/'self-test.json').read_text(encoding='utf-8'))
        assert data['ok'] and len(data['checks'])==6 and data['version']==number and not data['network_used']
else:
    run('android-build',[python,source/'build.py','--build-only','--build-dir',build,'--test-dir',test/'android-host'])
    log=(report/'android-build.log').read_text(encoding='utf-8',errors='replace')
    assert "package: name='app.jmbatch.android' versionCode='610' versionName='0.6.10'" in log
    assert 'Signer #1 certificate SHA-256 digest: cee4da716e0ac1d1b5fa3a8395e27040f18702264c433e1568c1d0b2e73d4f29' in log
    assert all('Verified using '+s+': true' in log for s in ('v2 scheme (APK Signature Scheme v2)','v3 scheme (APK Signature Scheme v3)'))
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in snapshot.items())
print('Build and focused checks complete:',platform,number,flush=True)
