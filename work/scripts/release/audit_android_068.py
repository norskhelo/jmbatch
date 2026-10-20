"""Verify the reader fix, reproducible old-version failure, and signed release."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
from release_paths import PROJECT as ROOT, WORK, sha256, source_versions, verify_manifest
sys.path.insert(0, str(WORK))
from package_network_update import source_files

BASE = "b83995c0ab6b6a70cac8a691b17b4d2cc6804318"
REPORT = ROOT / "outputs/reports/reader-scroll-fix-068-complete"
REPORT.mkdir(parents=True, exist_ok=True)
DELIVERY = ROOT.parent / "Android/0.6.8"
runtime = WORK / "tests/reader-scroll-fix-runtime"
java = WORK / "jmbatch-android/app/src/main/java"
build_report = ROOT / "outputs/reports/reader-scroll-fix-068-build"


def original(path):
    return subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT)


def lf(data):
    return data.replace(b"\r\n", b"\n")


checks = json.loads((build_report / "checks.json").read_text())
assert len(checks) == 6 and all(c["exit_code"] == 0 for c in checks), checks
host_checks = 0
for name, count in [("reader-rules", 14), ("reader_pager", 32), ("reader_chrome", 73)]:
    log = (build_report / (name + ".log")).read_text(encoding="utf-8", errors="replace")
    assert f"{count} checks passed" in log
    host_checks += count
suites = {}
for name, count in [("ReaderAlbumRuntimeTest", 9), ("ReaderScrollRuntimeTest", 10)]:
    suite = ET.parse(runtime / f"target/surefire-reports/TEST-app.jmbatch.android.{name}.xml").getroot()
    values = {key: int(suite.get(key)) for key in ("tests", "failures", "errors", "skipped")}
    assert values == dict(tests=count, failures=0, errors=0, skipped=0), values
    suites[name] = values
old = ET.parse(WORK / "tests/reader-scroll-old-version-proof/target/surefire-reports/TEST-app.jmbatch.android.ReaderScrollRuntimeTest.xml").getroot()
assert old.get("tests") == "1" and old.get("failures") == "1" and old.get("errors") == "0"
assert "no repeated decode while stationary" in old.find("testcase/failure").get("message")
assert lf((WORK / "tests/reader-scroll-old-version-proof/src/main/java/app/jmbatch/android/ReaderActivity.java").read_bytes()) == lf(original("work/jmbatch-android/app/src/main/java/app/jmbatch/android/ReaderActivity.java"))

for path in java.rglob("*.java"):
    current = path.read_text(encoding="utf-8")
    tested = (runtime / "src/main/java" / path.relative_to(java)).read_text(encoding="utf-8")
    if path.name == "Core.java":
        current = current.replace('VERSION = "0.6.8"', 'VERSION = "0.6.7"')
    if path.name == "GithubUpdates.java":
        current = re.sub(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";', "", current)
        tested = re.sub(r'private static final String CURRENT_NOTES="(?:[^"\\]|\\.)*";', "", tested)
    assert current == tested, path

stability = {}
for api in (29, 35):
    for saved in (0, 1):
        data = json.loads((runtime / f"reader-measurements/natural-trace-{saved}-api{api}.json").read_text())
        before, after = data["frames"][339], data["frames"][379]
        deltas = {key: after[key] - before[key] for key in ("puts", "evictions", "layouts")}
        assert all(v == 0 for v in deltas.values())
        assert before["rows"] == after["rows"] and all(not row["loading"] for row in after["rows"])
        stability[f"api{api}-saved{saved}"] = deltas

assert source_versions() == {"windows": "0.3.27", "android": "0.6.8"}
assert not subprocess.check_output(["git", "diff", BASE, "--", "work/jmbatch"], cwd=ROOT).strip()
for name in ("work/jmbatch/update_trust.py", "work/jmbatch-android/app/src/main/java/app/jmbatch/android/UpdateTrust.java"):
    assert lf((ROOT / name).read_bytes()) == lf(original(name))
manifest_path = "work/jmbatch-android/app/src/main/AndroidManifest.xml"
current = ET.parse(ROOT / manifest_path).getroot()
old_manifest = ET.fromstring(original(manifest_path))
ns = "{http://schemas.android.com/apk/res/android}"
assert current.get(ns + "versionCode") == "608"
current.set(ns + "versionCode", old_manifest.get(ns + "versionCode"))
current.set(ns + "versionName", old_manifest.get(ns + "versionName"))
assert ET.tostring(current) == ET.tostring(old_manifest)

apk = DELIVERY / "JMBatch-0.6.8-Android.apk"
assert sha256(apk) == sha256(WORK / "builds/android-0.6.8" / apk.name)
log = (build_report / "android-build.log").read_text(encoding="utf-8", errors="replace")
assert "name='app.jmbatch.android' versionCode='608' versionName='0.6.8'" in log
tools = WORK / "android-tools"
jvm = tools / "jdk-17.0.20.1+1/bin/java.exe"
signer = next(tools.rglob("apksigner.jar"))
certs = []
for version in ("0.6.7", "0.6.8"):
    output = subprocess.check_output([str(jvm), "-jar", str(signer), "verify", "--verbose", "--print-certs",
                                     str(ROOT.parent / f"Android/{version}/JMBatch-{version}-Android.apk")])
    text = output.decode("utf-8")
    (REPORT / f"apk-signature-{version}.txt").write_text(text, encoding="utf-8")
    assert "Verified using v2 scheme (APK Signature Scheme v2): true" in text
    assert "Verified using v3 scheme (APK Signature Scheme v3): true" in text
    certs.append(re.search(r"Signer #1 certificate SHA-256 digest: ([a-f0-9]+)", text).group(1))
assert certs[0] == certs[1]
with zipfile.ZipFile(apk) as archive:
    assert archive.testzip() is None
    for marker in (b"0.6.8", b"pageSizes", b"pageHeight", b"releaseRows"):
        assert marker in archive.read("classes.dex")
files = source_files("android")
with zipfile.ZipFile(DELIVERY / "JMBatch-0.6.8-Android-source.zip") as archive:
    assert archive.testzip() is None and set(archive.namelist()) == set(files)
    for name, path in files.items():
        assert archive.read(name) == path.read_bytes(), name
notes = (WORK / "release-android-068/release-notes.md").read_bytes()
for name in ("更新日志-0.6.8.md", "release-notes-android-0.6.8.md"):
    assert (DELIVERY / name).read_bytes() == notes
assert (ROOT / "CHANGELOG.md").read_bytes().startswith(notes)
assert (DELIVERY / "安卓使用说明-0.6.8.txt").read_bytes() == (WORK / "jmbatch-android/README.txt").read_bytes()
plain = re.sub(r"^#{1,2} ", "", notes.decode("utf-8").replace("\r\n", "\n"), flags=re.M).replace("- ", "• ")
text = (java / "app/jmbatch/android/GithubUpdates.java").read_text(encoding="utf-8")
assert json.loads(re.search(r'CURRENT_NOTES=("(?:\\.|[^"\\])*");', text).group(1)) == plain
assert verify_manifest(DELIVERY, {"android": "0.6.8"})["tag"] == "release-android-0.6.8"
for line in (DELIVERY / "SHA256-android-0.6.8.txt").read_text(encoding="utf-8").splitlines():
    digest, name = line.split("  ", 1)
    assert digest == sha256(DELIVERY / name)
readme = (ROOT / "README.md").read_text(encoding="utf-8")
assert "release-android-0.6.8/JMBatch-0.6.8-Android.apk" in readme
assert "release-0.3.27-0.6.7/JMBatch-0.3.27-Windows-x64.zip" in readme
assert "JMBatch-0.6.7-Android.apk" not in readme
for name in ("JMBatch-0.6.4-Android.apk", "JMBatch-0.6.7-Android.apk"):
    assert name not in (WORK / "jmbatch-android/README.txt").read_text(encoding="utf-8")

allowed = set(path.relative_to(ROOT).as_posix() for path in files.values())
allowed.update([
    "README.md", "CHANGELOG.md", "work/release-android-068/release-notes.md",
    "work/package_network_update.py",
    "work/scripts/maintenance/run_android_runtime_tests.py",
    "work/scripts/maintenance/prepare_reader_scroll_release.py",
    "work/scripts/maintenance/make_reader_scroll_fixture.py",
    "work/scripts/maintenance/check_reader_scroll_release.py",
    "work/scripts/maintenance/verify_reader_scroll_online.py",
    "work/scripts/release/prepare_publication_android_068.py",
    "work/scripts/release/publish_android_068.py",
    "work/scripts/release/audit_android_068.py",
    "work/scripts/release/verify_reader_scroll_commit.py",
])
for name in sorted(allowed):
    path = ROOT / name
    assert path.suffix.lower() not in (".jks", ".pem", ".key", ".apk", ".zip")
    assert not path.is_symlink()
    assert not re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", path.read_bytes())
(REPORT / "pathspec.txt").write_bytes(b"\0".join(n.encode("utf-8") for n in sorted(allowed)) + b"\0")
subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, check=True)
delivery = [dict(name=p.name, size=p.stat().st_size, sha256=sha256(p)) for p in sorted(DELIVERY.iterdir()) if p.is_file()]
assert len(delivery) == 9
receipt = dict(ok=True, android="0.6.8", windows_unchanged="0.3.27", baseline=BASE,
               framework=suites, host_checks=host_checks, stability=stability,
               old_version_expected_failure=old.find("testcase/failure").get("message"),
               apk_certificate_sha256=certs[0], packaged_source_files=len(files),
               allowed_paths=sorted(allowed), delivery=delivery, android_device_tested=False)
(REPORT / "audit.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print("AUDITED", len(files), "packaged sources,", len(allowed), "source/docs files, 19 framework cases,", host_checks, "host checks, nine delivery files, original signing identity")
