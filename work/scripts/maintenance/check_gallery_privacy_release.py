"""Focused folder-save regression and complete signed Android build."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "work/tests/gallery-privacy-069-build"
REPORT = ROOT / "outputs/reports/gallery-privacy-069-build"
SOURCE = ROOT / "work/jmbatch-android"
JDK = ROOT / "work/android-tools/jdk-17.0.20.1+1"
for directory in (RUN / "temp", REPORT, RUN / "folder"):
    directory.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update(TEMP=str(RUN / "temp"), TMP=str(RUN / "temp"), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
results = []

def run(name, command):
    start = time.monotonic()
    with (REPORT / (name + ".log")).open("w", encoding="utf-8") as log:
        result = subprocess.run([str(s) for s in command], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=300)
    results.append(dict(name=name, exit_code=result.returncode, seconds=round(time.monotonic()-start, 2)))
    (REPORT / "checks.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(name, result.returncode, flush=True)
    if result.returncode:
        print((REPORT / (name + ".log")).read_text(encoding="utf-8", errors="replace")[-5000:], flush=True)
        raise SystemExit(result.returncode)

run("folder-compile", [JDK / "bin/javac.exe", "-encoding", "UTF-8", "-d", RUN / "folder",
    SOURCE / "app/src/main/java/app/jmbatch/android/FolderSave.java", SOURCE / "tests/FolderSaveTest.java"])
run("folder-save", [JDK / "bin/java.exe", "-cp", RUN / "folder", "FolderSaveTest", RUN / "data"])
run("android-build", [sys.executable, SOURCE / "build.py", "--build-only"])
