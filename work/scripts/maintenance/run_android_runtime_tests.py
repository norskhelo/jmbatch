"""Isolated Android framework tests; dependencies remain in work/android-tools."""
from pathlib import Path
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[3]
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
parser=argparse.ArgumentParser()
parser.add_argument('--run-id', required=True)
parser.add_argument('--library-source', type=Path, help='Optional pre-fix LibraryScreen.java for regression proof')
parser.add_argument('--download-covers-source', type=Path, help='Optional pre-fix DownloadCovers.java for regression proof')
parser.add_argument('--reader-source', type=Path, help='Optional pre-fix ReaderActivity.java for regression proof')
parser.add_argument('--tests', help='Optional Maven test selector for a focused rerun')
args=parser.parse_args()
if not args.run_id.replace('-', '').replace('_', '').isalnum():
    parser.error('Use a simple run-id')
run=ROOT/'work/tests'/args.run_id
report=ROOT/'outputs/reports'/args.run_id
run.mkdir(parents=True,exist_ok=True);report.mkdir(parents=True,exist_ok=True)
tools=ROOT/'work/android-tools'
maven=tools/'apache-maven-3.9.9'
if not maven.exists():
    url='https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.9/apache-maven-3.9.9-bin.zip'
    archive=tools/'apache-maven-3.9.9-bin.zip'
    urllib.request.urlretrieve(url,archive)
    expected=urllib.request.urlopen(url+'.sha512').read().decode().strip().split()[0]
    assert hashlib.sha512(archive.read_bytes()).hexdigest()==expected
    with zipfile.ZipFile(archive) as z:z.extractall(tools)
source=run/'src/main/java'
shutil.copytree(ROOT/'work/jmbatch-android/app/src/main/java',source,dirs_exist_ok=True)
if args.library_source:
    shutil.copyfile(args.library_source,source/'app/jmbatch/android/LibraryScreen.java')
if args.download_covers_source:
    shutil.copyfile(args.download_covers_source,source/'app/jmbatch/android/DownloadCovers.java')
if args.reader_source:
    shutil.copyfile(args.reader_source,source/'app/jmbatch/android/ReaderActivity.java')
# The dialog uses framework resources only; unused app resources are compile constants.
(source/'app/jmbatch/android/R.java').write_text('package app.jmbatch.android; public final class R { public static class style { public static final int AppTheme=android.R.style.Theme_Material_Light_NoActionBar; } public static class drawable {public static final int ic_launcher=android.R.drawable.ic_menu_gallery;} }',encoding='utf-8')
env=os.environ.copy()
env['JAVA_HOME']=str(tools/'jdk-17.0.20.1+1')
env['JAVA_TOOL_OPTIONS']='-Dfile.encoding=UTF-8'
env['TEMP']=env['TMP']=str(run/'temp');(run/'temp').mkdir(exist_ok=True)
repo=tools/'maven-repository'
command=[str(maven/'bin/mvn.cmd'),'-B','-ntp','-f',str(ROOT/'work/jmbatch-android/tests/runtime/pom.xml'),
    '-Dmaven.repo.local='+str(repo),'-Dsdk.jar='+str(tools/'android-35/android.jar'),'-Drun.dir='+str(run)]
def execute(name,goals):
    with (report/(name+'.log')).open('w',encoding='utf-8') as log:
        result=subprocess.run(command+goals,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    print((report/(name+'.log')).read_text(encoding='utf-8',errors='replace')[-(6500 if name=='runtime' or result.returncode else 700):],flush=True)
    if result.returncode:raise SystemExit(result.returncode)
execute('dependencies',['dependency:copy-dependencies','-DoutputDirectory='+str(run/'dependencies')])
aar=run/'aar-classes';aar.mkdir(exist_ok=True)
for path in (run/'dependencies').glob('*.aar'):
    with zipfile.ZipFile(path) as z:
        import io
        with zipfile.ZipFile(io.BytesIO(z.read('classes.jar'))) as classes:classes.extractall(aar)
execute('runtime',['test']+(['-Dtest='+args.tests] if args.tests else []))
