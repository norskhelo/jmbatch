"""Run isolated local checks; never invokes publishing or real-site downloads."""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser()
parser.add_argument('platform', choices=['windows', 'android'])
parser.add_argument('--run-id', default='check-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
parser.add_argument('--build-dir', type=Path, help='Override build directory; tests stay isolated by run-id')
args = parser.parse_args()
if any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in args.run_id):
    parser.error('run-id must be a simple folder name')
REPORT = ROOT / 'outputs/reports' / args.run_id
TEST = ROOT / 'work/tests' / args.run_id
BUILD = args.build_dir.resolve() if args.build_dir else ROOT / 'work/builds' / (args.platform + '-' + args.run_id)
PYTHON = ROOT / 'work/venv/Scripts/python.exe'
for directory in (REPORT, TEST / 'temp', BUILD):
    directory.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update(TEMP=str(TEST / 'temp'), TMP=str(TEST / 'temp'), PYTHONDONTWRITEBYTECODE='1',
           PYTHONUTF8='1', PYTHONIOENCODING='utf-8', JM_BATCH_HOME=str(TEST / 'app-home'),
           PYINSTALLER_CONFIG_DIR=str(BUILD / 'pyinstaller-cache'),
           ANDROID_USER_HOME=str(TEST / 'android-home'))
results = []


def run(name, command, cwd=ROOT, timeout=600):
    print('RUN', name, flush=True)
    start = time.monotonic()
    log = REPORT / (name + '.log')
    with log.open('w', encoding='utf-8') as stream:
        try:
            result = subprocess.run([str(c) for c in command], cwd=cwd, env=env,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
            code = result.returncode
        except subprocess.TimeoutExpired:
            stream.write('\nTIMEOUT\n')
            code = 124
    results.append(dict(name=name, exit_code=code, seconds=round(time.monotonic()-start, 2),
                        log=str(log.relative_to(ROOT))))
    (REPORT / (args.platform + '-checks.json')).write_text(
        json.dumps(results, indent=2) + '\n', encoding='utf-8')
    print(('PASS' if code == 0 else 'FAIL'), name, 'exit', code, flush=True)
    if code:
        print(log.read_text(encoding='utf-8', errors='replace')[-5000:], flush=True)
        raise SystemExit(code)


if args.platform == 'windows':
    source = TEST / 'windows-source'
    if source.exists():
        raise SystemExit('Test source snapshot already exists; use a new run-id')
    shutil.copytree(ROOT / 'work/jmbatch', source,
                    ignore=shutil.ignore_patterns('__pycache__', '_tmp', 'work', 'build', 'dist', '.venv'))
    run('python-dependency-check', [PYTHON, '-m', 'pip', 'check'])
    run('windows-unit-tests', [PYTHON, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=source)
    run('windows-source-selftest', [PYTHON, source / 'app.py', '--self-test', TEST / 'windows-source-selftest'], timeout=180)
    run('windows-build', [PYTHON, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--workpath', BUILD / 'intermediates', '--distpath', BUILD / 'dist', ROOT / 'work/JMBatch.spec'], cwd=ROOT / 'work', timeout=900)
    run('windows-frozen-selftest', [BUILD / 'dist/JMBatch/JMBatch.exe', '--self-test', TEST / 'windows-frozen-selftest'], timeout=180)
else:
    run('android-build-and-host-tests', [PYTHON, ROOT / 'work/jmbatch-android/build.py',
        '--build-dir', BUILD, '--test-dir', TEST / 'android-host'], timeout=600)
    adb = ROOT / 'work/android-tools/platform-tools/adb.exe'
    run('adb-devices', [adb, 'devices', '-l'], timeout=30)
print('All', args.platform, 'local checks passed.', flush=True)
