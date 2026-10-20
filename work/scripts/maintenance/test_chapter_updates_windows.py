"""Focused regression with all app data and temporary files isolated."""
from pathlib import Path
import os
import subprocess
import json
ROOT = Path(__file__).resolve().parents[3]
run = ROOT / "work/tests/chapter-updates-windows-regression"
report = ROOT / "outputs/reports/chapter-updates-windows-regression"
for p in (run, report):
    p.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.update(TEMP=str(run), TMP=str(run), JM_BATCH_HOME=str(run / "home"), PYTHONDONTWRITEBYTECODE="1",
           PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONPATH=str(ROOT / "work/jmbatch"))
tests = ["test_chapter_updates", "test_chapters", "test_chapter_metadata", "test_chapter_delete", "test_library", "test_collections", "test_library_interaction"]
with (report / "tests.log").open("w", encoding="utf-8") as log:
    result = subprocess.run([str(ROOT / "work/venv/Scripts/python.exe"), "-B", "-m", "unittest", "-v", *tests],
                            cwd=ROOT / "work/jmbatch/tests", env=env, stdout=log, stderr=subprocess.STDOUT, timeout=300)
(report / "result.json").write_text(json.dumps(dict(exit_code=result.returncode, suites=tests), indent=2), encoding="utf-8")
print((report / "tests.log").read_text(encoding="utf-8")[-6500:])
raise SystemExit(result.returncode)
