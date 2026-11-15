"""Offline page-input regression using workspace dependencies and hidden processes."""
from pathlib import Path
import argparse
import io
import os
import shutil
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser()
parser.add_argument('--run-id', required=True)
parser.add_argument('--main-source', type=Path)
parser.add_argument('--tests', default='PageInputRuntimeTest,ClearHistoryRuntimeTest#taskMenu*')
args = parser.parse_args()
if not args.run_id.replace('-', '').isalnum():
    parser.error('Use a simple run ID')
run = ROOT / 'work/tests' / args.run_id
report = ROOT / 'outputs/reports' / args.run_id
tools = ROOT / 'work/android-tools'
for directory in (run, report, run / 'temp', run / 'dependencies'):
    directory.mkdir(parents=True, exist_ok=True)
source = run / 'src/main/java'
shutil.copytree(ROOT / 'work/jmbatch-android/app/src/main/java', source, dirs_exist_ok=True)
if args.main_source:
    shutil.copyfile(args.main_source, source / 'app/jmbatch/android/MainActivity.java')
(source / 'app/jmbatch/android/R.java').write_text('package app.jmbatch.android; public final class R {public static class style {public static final int AppTheme=android.R.style.Theme_Material_Light_NoActionBar;}public static class drawable {public static final int ic_launcher=android.R.drawable.ic_menu_gallery;}}', encoding='utf-8')
env = dict(os.environ, JAVA_HOME=str(tools / 'jdk-17.0.20.1+1'), JAVA_TOOL_OPTIONS='-Dfile.encoding=UTF-8', TEMP=str(run / 'temp'), TMP=str(run / 'temp'))
cmd = [tools / 'apache-maven-3.9.9/bin/mvn.cmd', '-o', '-B', '-ntp', '-f', ROOT / 'work/jmbatch-android/tests/runtime/pom.xml', '-Dmaven.repo.local=' + str(tools / 'maven-repository'), '-Dsdk.jar=' + str(tools / 'android-35/android.jar'), '-Drun.dir=' + str(run)]

def execute(name, extra):
    with (report / (name + '.log')).open('w', encoding='utf-8') as log:
        result = subprocess.run(list(map(str, cmd + extra)), cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW, timeout=600)
    print((report / (name + '.log')).read_text('utf-8', errors='replace')[-(5000 if result.returncode else 900):], flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)

execute('dependencies', ['dependency:copy-dependencies', '-DoutputDirectory=' + str(run / 'dependencies')])
for jar in (tools / 'maven-repository/org/robolectric/android-all-instrumented').glob('*/*.jar'):
    shutil.copy2(jar, run / 'dependencies' / jar.name)
for aar in (run / 'dependencies').glob('*.aar'):
    with zipfile.ZipFile(aar) as archive:
        with zipfile.ZipFile(io.BytesIO(archive.read('classes.jar'))) as classes:
            classes.extractall(run / 'aar-classes')
execute('runtime', ['test', '-Dtest=' + args.tests, '-Drobolectric.offline=true', '-Drobolectric.dependency.dir=' + str(run / 'dependencies')])
