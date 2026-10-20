"""Verify focused evidence, original signing identities and exact release sources."""
import json
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from release_paths import PROJECT as ROOT, WORK, source_versions, sha256, verify_manifest

sys.dont_write_bytecode = True
sys.path.insert(0, str(WORK))
from package_network_update import source_files

BASE = "a0282c7f8b7e16c58ebb385531ccf8987caf08d2"
VERSIONS = dict(windows="0.3.29", android="0.6.11")
REPORT = ROOT / "outputs/reports/chapter-updates-0329-0611-complete"
REPORT.mkdir(parents=True, exist_ok=True)
assert source_versions() == VERSIONS
suites = {}
for run, name, count in (("final", "ChapterUpdatesRuntimeTest", 16), ("normal", "LibraryScreenRuntimeTest", 13), ("normal", "CollectionRuntimeTest", 15)):
    suite = ET.parse(WORK / f"tests/chapter-updates-runtime-{run}/target/surefire-reports/TEST-app.jmbatch.android.{name}.xml").getroot()
    values = {key: int(suite.get(key)) for key in ("tests", "failures", "errors", "skipped")}
    assert values == dict(tests=count, failures=0, errors=0, skipped=0)
    suites[name] = values
runtime = WORK / "tests/chapter-updates-runtime-final/src/main/java"
for path in (WORK / "jmbatch-android/app/src/main/java").rglob("*.java"):
    assert path.read_bytes() == (runtime / path.relative_to(WORK / "jmbatch-android/app/src/main/java")).read_bytes(), path
unit = ROOT / "outputs/reports/chapter-updates-windows-regression"
assert json.loads((unit / "result.json").read_text())["exit_code"] == 0
assert "Ran 67 tests" in (unit / "tests.log").read_text(encoding="utf-8")
for platform, suffix, count in (("windows", "-final", 3), ("android", "", 1)):
    folder = ROOT / f"outputs/reports/chapter-updates-0329-0611-{platform}{suffix}"
    checks = json.loads((folder / "checks.json").read_text())
    assert len(checks) == count and all(item["exit_code"] == 0 for item in checks)
    for path, digest in json.loads((folder / "source-hashes.json").read_text()).items():
        assert sha256(ROOT / path) == digest, path
for kind in ("source", "frozen"):
    data = json.loads((WORK / f"tests/chapter-updates-0329-0611-windows-final/{kind}-selftest/self-test.json").read_text(encoding="utf-8"))
    assert data["ok"] and data["version"] == VERSIONS["windows"] and len(data["checks"]) == 4 and not data["network_used"]
for name in ("work/jmbatch/update_trust.py", "work/jmbatch-android/app/src/main/java/app/jmbatch/android/UpdateTrust.java"):
    original = subprocess.check_output(["git", "show", BASE + ":" + name], cwd=ROOT)
    assert original.replace(b"\r\n", b"\n") == (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
manifest_path = "work/jmbatch-android/app/src/main/AndroidManifest.xml"
old = ET.fromstring(subprocess.check_output(["git", "show", BASE + ":" + manifest_path], cwd=ROOT))
current = ET.parse(ROOT / manifest_path).getroot()
ns = "{http://schemas.android.com/apk/res/android}"
assert current.get(ns + "versionCode") == "611" and current.get(ns + "versionName") == "0.6.11"
for key in ("versionCode", "versionName"):
    current.set(ns + key, old.get(ns + key))
assert ET.tostring(current) == ET.tostring(old)
directories = {"windows": ROOT.parent / "Win/0.3.29", "android": ROOT.parent / "Android/0.6.11"}
jvm = WORK / "android-tools/jdk-17.0.20.1+1/bin/java.exe"
signer = next((WORK / "android-tools").rglob("apksigner.jar"))
certificates = []
for version in ("0.6.10", "0.6.11"):
    output = subprocess.check_output([str(jvm), "-jar", str(signer), "verify", "--verbose", "--print-certs",
                                    str(ROOT.parent / f"Android/{version}/JMBatch-{version}-Android.apk")]).decode("utf-8")
    (REPORT / f"apk-signature-{version}.txt").write_text(output, encoding="utf-8")
    assert all(f"Verified using {scheme} scheme (APK Signature Scheme {scheme}): true" in output for scheme in ("v2", "v3"))
    certificates.append(re.search(r"Signer #1 certificate SHA-256 digest: ([a-f0-9]+)", output)[1])
assert certificates[0] == certificates[1]
with zipfile.ZipFile(directories["android"] / "JMBatch-0.6.11-Android.apk") as archive:
    assert archive.testzip() is None
    for marker in (b"0.6.11", b"chapter-updates.json", b"checkUpdates", b"addChapterUpdate"):
        assert marker in archive.read("classes.dex")
notes = (WORK / "release-0329-0611/release-notes.md").read_bytes()
assert (ROOT / "CHANGELOG.md").read_bytes().startswith(notes)
plain = re.sub(r"^#{1,6} ", "", notes.decode("utf-8").replace("\r\n", "\n"), flags=re.M).replace("- ", "• ")
for name in ("work/jmbatch/updates.py", "work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java"):
    assert json.loads(re.search(r'CURRENT_NOTES\s*=\s*("(?:\\.|[^"\\])*")', (ROOT / name).read_text(encoding="utf-8"))[1]) == plain
allowed = set()
packaged = 0
deliveries = {}
for platform, version in VERSIONS.items():
    folder = directories[platform]
    files = source_files(platform)
    allowed.update(path.relative_to(ROOT).as_posix() for path in files.values())
    suffix = "source.zip" if platform == "windows" else "Android-source.zip"
    with zipfile.ZipFile(folder / f"JMBatch-{version}-{suffix}") as archive:
        assert archive.testzip() is None and set(archive.namelist()) == set(files)
        for name, path in files.items():
            assert archive.read(name) == path.read_bytes(), name
    packaged += len(files)
    for name in ("更新日志-0.3.29-0.6.11.md", "release-notes-0.3.29-0.6.11.md"):
        assert (folder / name).read_bytes() == notes
    assert verify_manifest(folder, VERSIONS, directories)["tag"] == "release-0.3.29-0.6.11"
    for line in (folder / f"SHA256-{platform}-{version}.txt").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        assert digest == sha256(folder / name)
    deliveries[platform] = [dict(name=p.name, size=p.stat().st_size, sha256=sha256(p)) for p in sorted(folder.iterdir()) if p.is_file()]
for name in ("update-manifest.json", "update-manifest.sig"):
    assert (directories["windows"] / name).read_bytes() == (directories["android"] / name).read_bytes()
allowed.update(("README.md", "CHANGELOG.md", "work/release-0329-0611/release-notes.md",
    "work/scripts/maintenance/prepare_chapter_updates_release.py", "work/scripts/maintenance/build_chapter_updates_release.py",
    "work/scripts/maintenance/test_chapter_updates_windows.py", "work/scripts/maintenance/verify_chapter_updates_online.py",
    "work/scripts/release/prepare_publication_0329_0611.py", "work/scripts/release/publish_0329_0611.py",
    "work/scripts/release/audit_chapter_updates_release.py", "work/scripts/release/verify_chapter_updates_commit.py"))
for name in allowed:
    path = ROOT / name
    assert path.suffix.lower() not in (".jks", ".pem", ".key", ".apk", ".zip") and not path.is_symlink()
    assert not re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", path.read_bytes())
changed = set(subprocess.check_output(["git", "diff", "--name-only", BASE], cwd=ROOT).decode().splitlines())
assert changed <= allowed, changed - allowed
subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True, capture_output=True)
(REPORT / "pathspec.txt").write_bytes(b"\0".join(name.encode("utf-8") for name in sorted(allowed)) + b"\0")
receipt = dict(ok=True, baseline=BASE, versions=VERSIONS, framework=suites, windows_tests=67,
    apk_certificate_sha256=certificates[0], packaged_source_files=packaged, allowed_paths=sorted(allowed),
    delivery=deliveries, android_device_tested=False)
(REPORT / "audit.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print("AUDITED", packaged, "packaged sources,", len(allowed), "publishable files, original trust and signed deliveries")
