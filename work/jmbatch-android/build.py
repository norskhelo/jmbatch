"""Build with an official JDK and Android SDK build-tools; no third-party runtime."""
import argparse, os, pathlib, subprocess, zipfile, shutil, re, sys
import xml.etree.ElementTree as ET

ROOT=pathlib.Path(__file__).resolve().parent
core=ROOT/'app/src/main/java/app/jmbatch/android/Core.java'
VERSION=re.search(r'\bVERSION\s*=\s*"(\d+\.\d+\.\d+)"',core.read_text(encoding='utf-8')).group(1)
manifest=ET.parse(ROOT/'app/src/main/AndroidManifest.xml').getroot()
android_ns='{http://schemas.android.com/apk/res/android}'
VERSION_CODE=manifest.attrib[android_ns+'versionCode']
gradle=(ROOT/'app/build.gradle').read_text(encoding='utf-8')
if (manifest.attrib[android_ns+'versionName'] != VERSION or
        re.search(r"versionName\s+'([^']+)'",gradle).group(1) != VERSION or
        re.search(r'versionCode\s+(\d+)',gradle).group(1) != VERSION_CODE):
    raise ValueError('Android application versions disagree; check Core, manifest, and Gradle')
parser=argparse.ArgumentParser()
parser.add_argument('--tools',type=pathlib.Path,default=ROOT.parent/'android-tools')
parser.add_argument('--jdk',type=pathlib.Path)
parser.add_argument('--sdk',type=pathlib.Path)
parser.add_argument('--keystore',type=pathlib.Path,default=ROOT.parent/'android-signing'/'jmbatch-local.jks')
parser.add_argument('--build-dir',type=pathlib.Path,default=ROOT.parent/'builds'/('android-'+VERSION),help='Build intermediates and APK destination')
parser.add_argument('--test-dir',type=pathlib.Path,default=ROOT.parent/'tests'/('android-'+VERSION),help='Isolated host-test classes and generated data')
args=parser.parse_args()
tools=args.tools.resolve()
jdk=args.jdk or next(tools.glob('jdk-*'))
sdk=args.sdk or tools
platform=next(p for p in sdk.rglob('android.jar') if 'android-35' in str(p))
buildtools=next(sdk.rglob('aapt2.exe')).parent
build=args.build_dir.resolve();build.mkdir(parents=True,exist_ok=True)
environment=os.environ.copy();environment['JAVA_HOME']=str(jdk);environment['PATH']=str(jdk/'bin')+os.pathsep+environment.get('PATH','')
def run(*command):
    print('>',pathlib.Path(str(command[0])).name,' '.join(str(a) for a in command[1:3]),flush=True)
    subprocess.run([str(arg) for arg in command],env=environment,cwd=ROOT,check=True)

java=jdk/'bin/java.exe';javac=jdk/'bin/javac.exe'
testroot=args.test_dir.resolve()
testout=testroot/'tests';testout.mkdir(parents=True,exist_ok=True)
run(javac,'-encoding','UTF-8','-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/WorkerDrain.java')
core=ROOT/'app/src/main/java/app/jmbatch/android/Core.java'
run(javac,'-encoding','UTF-8','-d',testout,core,ROOT/'app/src/main/java/app/jmbatch/android/UpdateRules.java',ROOT/'tests/CoreTest.java')
run(java,'-Djava.awt.headless=true','-cp',testout,'CoreTest',testroot/'test-output')
run(javac,'-encoding','UTF-8','-cp',testout,'-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/UpdateHistory.java',ROOT/'tests/UpdateHistoryTest.java')
run(java,'-cp',testout,'UpdateHistoryTest')
run(javac,'-encoding','UTF-8','-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/UpdateTrust.java',ROOT/'app/src/main/java/app/jmbatch/android/UpdateCrypto.java',ROOT/'tests/UpdateCryptoTest.java')
run(java,'-cp',testout,'UpdateCryptoTest',ROOT/'tests/fixtures')
run(javac,'-encoding','UTF-8','-cp',testout,'-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/SinglePageRecovery.java',ROOT/'tests/RecoveryTest.java')
run(java,'-cp',testout,'RecoveryTest')
run(javac,'-encoding','UTF-8','-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/UpdateCertificateCheck.java',ROOT/'tests/CertificateTest.java')
run(java,'-cp',testout,'CertificateTest')

run(javac,'-encoding','UTF-8','-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/LibraryRules.java',ROOT/'tests/LibraryTest.java')
run(java,'-cp',testout,'LibraryTest',testroot/'test-output')
run(javac,'-encoding','UTF-8','-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/CoverRules.java',ROOT/'tests/CoverTest.java')
run(java,'-cp',testout,'CoverTest',testroot/'test-output')
run(javac,'-encoding','UTF-8','-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/DownloadCoverRules.java',ROOT/'tests/DownloadCoverTest.java')
run(java,'-cp',testout,'DownloadCoverTest',testroot/'test-output')

run(javac,'-encoding','UTF-8','-cp',testout,'-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/BatchOperations.java',ROOT/'tests/BatchTest.java')
run(java,'-cp',testout,'BatchTest',testroot/'test-output')

run(javac,'-encoding','UTF-8','-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/DirectoryTargets.java',ROOT/'tests/DirectoryTest.java')
run(java,'-cp',testout,'DirectoryTest')
run(sys.executable,ROOT/'tests/test_system_directory.py',jdk,testroot/'system-directory')
run(sys.executable,ROOT/'tests/test_cancel_service.py',jdk,testroot/'cancel-service')

run(javac,'-encoding','UTF-8','-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/NetworkRoutes.java',ROOT/'tests/NetworkTest.java')
run(java,'-cp',testout,'NetworkTest')

for component in ('ImageMemory', 'ImagePipeline', 'ImageRoutes'):
    run(javac,'-encoding','UTF-8','-cp',testout,'-d',testout,ROOT/'app/src/main/java/app/jmbatch/android'/(component+'.java'),ROOT/'tests'/(component+'Test.java'))
    run(java,'-cp',testout,component+'Test',testroot/component)

# Exercise production HTTP/CDN code without Android runtime, sockets or user data.
transport=testroot/'transport-host';transport.mkdir(exist_ok=True)
stubs=transport/'stubs';stubs.mkdir(exist_ok=True)
(stubs/'Store.java').write_text('package app.jmbatch.android; public final class Store { public static class Settings { public int retries=2,timeout=25; } }',encoding='utf-8')
(stubs/'SystemClock.java').write_text('package android.os; public final class SystemClock { public static long elapsedRealtime(){return System.nanoTime()/1000000;} }',encoding='utf-8')
run(javac,'-encoding','UTF-8','-cp',str(testout)+os.pathsep+str(platform),'-d',transport,stubs/'Store.java',stubs/'SystemClock.java',ROOT/'app/src/main/java/app/jmbatch/android/JmApi.java',ROOT/'tests/JmApiTransportTest.java')
run(java,'-cp',str(transport)+os.pathsep+str(testout)+os.pathsep+str(platform),'app.jmbatch.android.JmApiTransportTest',transport/'data')
run(javac,'-encoding','UTF-8','-cp',str(transport)+os.pathsep+str(testout)+os.pathsep+str(platform),'-d',transport,ROOT/'app/src/main/java/app/jmbatch/android/DownloadPool.java',ROOT/'tests/JmApiCancellationTest.java')
run(java,'-cp',str(transport)+os.pathsep+str(testout)+os.pathsep+str(platform),'app.jmbatch.android.JmApiCancellationTest',transport/'cancellation')

run(javac,'-encoding','UTF-8','-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/DownloadDisplay.java',ROOT/'tests/DownloadDisplayTest.java')
run(java,'-cp',testout,'DownloadDisplayTest')
run(javac,'-encoding','UTF-8','-cp',testout,'-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/CacheCleanup.java',ROOT/'tests/CacheCleanupTest.java')
# Windows junction fixtures exercise the same canonical-path guard used on Android.
import _winapi
links=testroot/'cleanup-links';outside=links/'outside';outside.mkdir(parents=True,exist_ok=True)
(outside/'keep.jpg').write_bytes(b'preserve')
linked_task=links/'work/task';linked_task.mkdir(parents=True,exist_ok=True)
for link in (linked_task/'images',linked_task/'album-stage'):
    if not link.exists():_winapi.CreateJunction(str(outside),str(link))
run(java,'-cp',testout,'CacheCleanupTest',testroot/'cache-cleanup',links)

run(javac,'-encoding','UTF-8','-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/DownloadPool.java',ROOT/'tests/DownloadPoolTest.java')
run(java,'-cp',testout,'DownloadPoolTest')

run(javac,'-encoding','UTF-8','-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/ResumeCache.java',ROOT/'tests/ResumeCacheTest.java')
run(java,'-Djava.awt.headless=true','-cp',testout,'ResumeCacheTest',testroot/'resume-cache')

run(javac,'-encoding','UTF-8','-cp',testout,'-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/AlbumRules.java',ROOT/'tests/AlbumTest.java')
run(java,'-Djava.awt.headless=true','-cp',testout,'AlbumTest',testroot/'album-output')
run(javac,'-encoding','UTF-8','-cp',testout,'-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/ArchivePages.java',ROOT/'tests/ArchivePagesTest.java')
run(java,'-cp',testout,'ArchivePagesTest',testroot/'archive-output')

resources=build/'resources.zip';generated=build/'generated';generated.mkdir(exist_ok=True)
run(javac,'-encoding','UTF-8','-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/ChapterRules.java',ROOT/'tests/ChapterTest.java')
run(java,'-cp',testout,'ChapterTest')
run(javac,'-encoding','UTF-8','-cp',testout,'-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/ChapterMetadata.java',ROOT/'tests/ChapterMetadataTest.java')
run(java,'-cp',testout,'ChapterMetadataTest',testroot/'chapter-metadata')
run(javac,'-encoding','UTF-8','-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/FolderSave.java',ROOT/'tests/FolderSaveTest.java')
run(java,'-cp',testout,'FolderSaveTest',testroot/'folder-save')
run(javac,'-encoding','UTF-8','-d',testout,ROOT/'app/src/main/java/app/jmbatch/android/ReaderRules.java',ROOT/'tests/ReaderTest.java')
run(java,'-cp',testout,'ReaderTest')
run(sys.executable,ROOT/'tests/test_reader_pager.py',jdk,testroot/'reader-pager')
run(buildtools/'aapt2.exe','compile','--dir',ROOT/'app/src/main/res','-o',resources)
run(buildtools/'aapt2.exe','link','-I',platform,'--manifest',ROOT/'app/src/main/AndroidManifest.xml','--java',generated,'--min-sdk-version','26','--target-sdk-version','34','--version-code',VERSION_CODE,'--version-name',VERSION,'-o',build/'resources.apk',resources)
classes=build/'classes';classes.mkdir(exist_ok=True)
sources=list((ROOT/'app/src/main/java').rglob('*.java'))+list(generated.rglob('*.java'))
argumentfile=build/'sources.txt';argumentfile.write_text('\n'.join('"'+p.as_posix()+'"' for p in sources),encoding='utf-8')
run(javac,'-encoding','UTF-8','-source','8','-target','8','-bootclasspath',platform,'-classpath',buildtools/'core-lambda-stubs.jar','-d',classes,'@'+str(argumentfile))
jar=build/'classes.jar'
with zipfile.ZipFile(jar,'w') as archive:
    for path in classes.rglob('*.class'):archive.write(path,path.relative_to(classes).as_posix())
dex=build/'dex';dex.mkdir(exist_ok=True)
run(java,'-cp',buildtools/'lib/d8.jar','com.android.tools.r8.D8','--min-api','26','--lib',platform,'--output',dex,jar)
unsigned=build/'unsigned.apk'
shutil.copyfile(build/'resources.apk',unsigned)
with zipfile.ZipFile(unsigned,'a',zipfile.ZIP_DEFLATED) as archive:
    for path in dex.glob('*.dex'):archive.write(path,path.name)
    assets=ROOT/'app/src/main/assets'
    if assets.exists():
        for path in assets.rglob('*'):
            if path.is_file():archive.write(path,'assets/'+path.relative_to(assets).as_posix())
run(buildtools/'zipalign.exe','-f','4',unsigned,build/'aligned.apk')
keystore=args.keystore.resolve();keystore.parent.mkdir(parents=True,exist_ok=True)
if not keystore.exists():
    raise RuntimeError('Existing Android release keystore is required; refusing to replace signing identity')
apk=build/f'JMBatch-{VERSION}-Android.apk'
run(java,'-jar',buildtools/'lib/apksigner.jar','sign','--ks',keystore,'--ks-key-alias','jmbatch-local','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,build/'aligned.apk')
run(java,'-jar',buildtools/'lib/apksigner.jar','verify','--verbose','--print-certs',apk)
run(buildtools/'aapt.exe','dump','badging',apk)
print('APK_READY',apk)
