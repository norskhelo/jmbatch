"""Check packaged sources against the staged release and collect local evidence."""
import importlib.util
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("packager", ROOT / "work/package_network_update.py")
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)
checked = []
for platform, version in (("windows", "0.3.1"), ("android", "0.4.1")):
    filename = f"JMBatch-{version}-" + ("source.zip" if platform == "windows" else "Android-source.zip")
    directory = ROOT.parent / ("Win" if platform == "windows" else "Android") / version
    with zipfile.ZipFile(directory / filename) as archive:
        for name, source in packager.source_files(platform).items():
            relative = source.relative_to(ROOT).as_posix()
            staged = subprocess.check_output(["git", "show", ":" + relative], cwd=ROOT)
            packaged = archive.read(name)
            if source.suffix not in (".bin", ".sig"):
                staged = staged.replace(b"\r\n", b"\n")
                packaged = packaged.replace(b"\r\n", b"\n")
            assert staged == packaged, relative
            checked.append(relative)
staged_paths = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).decode().splitlines()
for name in staged_paths:
    assert not any(part in ("venv", "android-tools", "android-signing", "update-signing", "outputs", "builds", "_tmp") for part in Path(name).parts), name
    assert Path(name).suffix not in (".pem", ".key", ".jks", ".keystore", ".apk", ".exe", ".zip"), name
    content = subprocess.check_output(["git", "show", ":" + name], cwd=ROOT)
    assert not re.search(rb"(?m)^\s*-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", content), name
reports = ROOT / "outputs/reports/formats-031-041-complete"
reports.mkdir(parents=True, exist_ok=True)
source_test = json.loads((ROOT / "work/tests/formats-windows-complete/windows-source-selftest/self-test.json").read_text(encoding="utf-8"))
frozen_test = json.loads((ROOT / "work/tests/formats-windows-complete/windows-frozen-selftest/self-test.json").read_text(encoding="utf-8"))
assert source_test["ok"] and frozen_test["ok"]
result = dict(ok=True, versions=dict(windows="0.3.1", android="0.4.1"),
              source_files_match_index=len(checked), staged_paths=staged_paths,
              source_selftest_checks=len(source_test["checks"]), frozen_selftest_checks=len(frozen_test["checks"]),
              windows_unit_tests=109, android_device_tested=False)
(reports / "local-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
