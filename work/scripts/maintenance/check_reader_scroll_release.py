"""Focused reader checks and complete Android APK build/signature verification."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "work/tests/reader-scroll-fix-068-build"
REPORT = ROOT / "outputs/reports/reader-scroll-fix-068-build"
SOURCE = ROOT / "work/jmbatch-android"
JDK = ROOT / "work/android-tools/jdk-17.0.20.1+1"
for directory in (RUN / "temp", REPORT, RUN / "reader"):
    directory.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update(TEMP=str(RUN / "temp"), TMP=str(RUN / "temp"), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
results = []


def run(name, command, timeout=300):
    start = time.monotonic()
    with (REPORT / (name + ".log")).open("w", encoding="utf-8") as log:
        result = subprocess.run([str(s) for s in command], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    results.append({"name": name, "exit_code": result.returncode, "seconds": round(time.monotonic() - start, 2)})
    (REPORT / "checks.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(name, result.returncode, flush=True)
    if result.returncode:
        print((REPORT / (name + ".log")).read_text(encoding="utf-8", errors="replace")[-5000:], flush=True)
        raise SystemExit(result.returncode)


run("reader-compile", [JDK / "bin/javac.exe", "-encoding", "UTF-8", "-d", RUN / "reader",
                      SOURCE / "app/src/main/java/app/jmbatch/android/ReaderRules.java", SOURCE / "tests/ReaderTest.java"])
run("reader-rules", [JDK / "bin/java.exe", "-cp", RUN / "reader", "ReaderTest"])
for name in ("reader_pager", "reader_chrome"):
    run(name, [sys.executable, SOURCE / f"tests/test_{name}.py", JDK, RUN / name])
run("android-build", [sys.executable, SOURCE / "build.py", "--build-only"])
run("adb-devices", [ROOT / "work/android-tools/platform-tools/adb.exe", "devices", "-l"], timeout=30)
