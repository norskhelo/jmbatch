"""Focused offline production-network regressions; writes only isolated test/report folders."""
from pathlib import Path
import argparse
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--run-id', required=True)
args = parser.parse_args()
assert args.run_id.replace('-', '').isalnum()
run = ROOT / 'work/tests' / args.run_id
report = ROOT / 'outputs/reports' / args.run_id
run.mkdir(parents=True, exist_ok=True)
report.mkdir(parents=True, exist_ok=True)
jdk = ROOT / 'work/android-tools/jdk-17.0.20.1+1/bin'
sdk = ROOT / 'work/android-tools/android-35/android.jar'
src = APP / 'app/src/main/java/app/jmbatch/android'
(run/'Store.java').write_text('package app.jmbatch.android; public final class Store { public static class Settings { public int retries=2,timeout=25,threads=8,slowKB=30,window=90; public boolean autoReset=true; } }', encoding='utf-8')
(run/'SystemClock.java').write_text('package android.os; public final class SystemClock { public static long elapsedRealtime(){return System.nanoTime()/1000000;} }', encoding='utf-8')
components = ('Core', 'UpdateRules', 'WorkerDrain', 'NetworkRoutes', 'ImageRoutes', 'ImagePipeline', 'ImageMemory', 'DnsWire', 'FallbackDns', 'OriginTls', 'TransferWatch', 'RealtimeSpeed', 'JmApi', 'DownloadPool', 'SinglePageRecovery', 'DownloadDisplay')
tests = ('NetworkTest', 'NetworkCauseTest', 'FallbackDnsTest', 'ImageRoutesTest', 'ImagePipelineTest', 'ImageMemoryTest', 'JmApiTransportTest', 'JmApiFallbackTest', 'JmApiCancellationTest', 'TransferWatchTest', 'RecoveryTest', 'DownloadDisplayTest')
cp = str(run) + os.pathsep + str(sdk)
def execute(name, command):
    env = dict(os.environ, JAVA_TOOL_OPTIONS='-Dfile.encoding=UTF-8')
    result = subprocess.run(list(map(str, command)), cwd=APP, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    output = result.stdout.decode('utf-8', errors='replace')
    (report/(name+'.log')).write_text(output, encoding='utf-8')
    print(name, output.strip(), flush=True)
    if result.returncode: raise SystemExit(result.returncode)
execute('compile', [jdk/'javac.exe', '-encoding', 'UTF-8', '-cp', sdk, '-d', run, *run.glob('*.java'), *[src/(n+'.java') for n in components], *[APP/'tests'/(n+'.java') for n in tests]])
for name in tests:
    package = 'app.jmbatch.android.' if 'package app.jmbatch.android;' in (APP/'tests'/(name+'.java')).read_text(encoding='utf-8') else ''
    execute(name, [jdk/'java.exe', '-cp', cp, package+name, run/name])
