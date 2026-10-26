"""Focused offline sharing regressions and original-key local build; no publication."""
from pathlib import Path
import hashlib, io, json, os, re, shutil, subprocess, sys, zipfile

sys.stdout.reconfigure(encoding='utf-8',errors='replace')
ROOT=Path(__file__).resolve().parents[3]
RUN=ROOT/'work/tests/share-fix-20261026'
REPORT=ROOT/'outputs/reports/share-fix-20261026'
TOOLS=ROOT/'work/android-tools'
for p in (RUN,REPORT,RUN/'temp'):p.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,JAVA_HOME=str(TOOLS/'jdk-17.0.20.1+1'),JAVA_TOOL_OPTIONS='-Dfile.encoding=UTF-8',PYTHONUTF8='1',PYTHONIOENCODING='utf-8',TEMP=str(RUN/'temp'),TMP=str(RUN/'temp'))

def execute(name,cmd):
    with (REPORT/(name+'.log')).open('w',encoding='utf-8') as log:
        result=subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,timeout=600)
    print(name,'exit',result.returncode,flush=True)
    if result.returncode:
        print((REPORT/(name+'.log')).read_text('utf-8',errors='replace')[-7500:]);raise SystemExit(result.returncode)

if '--build' in sys.argv:
    version=re.search(r'\bVERSION\s*=\s*"([^"]+)"',(ROOT/'work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java').read_text('utf-8')).group(1)
    files=[p for p in (ROOT/'work/jmbatch-android/app/src').rglob('*') if p.is_file()]
    hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (REPORT/'build-source-hashes.json').write_text(json.dumps(hashes,indent=2),'utf-8')
    execute('android-build',[ROOT/'work/venv/Scripts/python.exe',ROOT/'work/jmbatch-android/build.py','--build-only','--build-dir',ROOT/'work/builds'/('android-'+version+'-share-fix'),'--test-dir',RUN/'host'])
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
else:
    source=RUN/'src/main/java';shutil.copytree(ROOT/'work/jmbatch-android/app/src/main/java',source,dirs_exist_ok=True)
    (source/'app/jmbatch/android/R.java').write_text('package app.jmbatch.android; public final class R {public static class style {public static final int AppTheme=android.R.style.Theme_Material_Light_NoActionBar;}public static class drawable {public static final int ic_launcher=android.R.drawable.ic_menu_gallery;}}','utf-8')
    tests=RUN/'src/test/java/app/jmbatch/android';tests.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'work/jmbatch-android/tests/runtime/src/test/java/app/jmbatch/android/FileSharingRuntimeTest.java',tests/'FileSharingRuntimeTest.java')
    pom=(ROOT/'work/jmbatch-android/tests/runtime/pom.xml').read_text('utf-8').replace('<systemPropertyVariables>','<systemPropertyVariables><robolectric.offline>true</robolectric.offline><robolectric.dependency.dir>'+str(RUN/'dependencies')+'</robolectric.dependency.dir>')
    (RUN/'pom.xml').write_text(pom,'utf-8')
    cmd=[TOOLS/'apache-maven-3.9.9/bin/mvn.cmd','-o','-B','-ntp','-f',RUN/'pom.xml','-Dmaven.repo.local='+str(TOOLS/'maven-repository'),'-Dsdk.jar='+str(TOOLS/'android-35/android.jar'),'-Drun.dir='+str(RUN)]
    execute('dependencies',cmd+['dependency:copy-dependencies','-DoutputDirectory='+str(RUN/'dependencies')])
    for f in (TOOLS/'maven-repository/org/robolectric/android-all-instrumented').glob('*/*.jar'):
        dest=RUN/'dependencies'/f.name
        if not dest.exists():shutil.copy2(f,dest)
    for f in (RUN/'dependencies').glob('*.aar'):
        with zipfile.ZipFile(f) as z:
            with zipfile.ZipFile(io.BytesIO(z.read('classes.jar'))) as c:c.extractall(RUN/'aar-classes')
    execute('runtime',cmd+['test','-Dtest=FileSharingRuntimeTest'])
    print((REPORT/'runtime.log').read_text('utf-8',errors='replace')[-1700:])
