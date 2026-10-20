"""Audit focused tests, unchanged trust, packaged sources and Android delivery."""
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
from release_paths import PROJECT as ROOT, WORK, sha256, source_versions, verify_manifest
sys.path.insert(0, str(WORK))
from package_network_update import source_files

BASE = "0226cc822f1fd8af515c0da7ae7726e3ceaa60a7"
REPORT = ROOT / "outputs/reports/gallery-privacy-069-complete"
REPORT.mkdir(parents=True, exist_ok=True)
DELIVERY = ROOT.parent / "Android/0.6.9"
RUNTIME = WORK / "tests/gallery-privacy-runtime-final"
JAVA = WORK / "jmbatch-android/app/src/main/java"
BUILD = ROOT / "outputs/reports/gallery-privacy-069-build"

def original(path):
    return subprocess.check_output(["git", "show", BASE + ":" + path], cwd=ROOT)

def lf(data):
    return data.replace(b"\r\n", b"\n")

checks = json.loads((BUILD / "checks.json").read_text())
assert len(checks) == 3 and all(c["exit_code"] == 0 for c in checks)
assert "50 checks passed" in (BUILD / "folder-save.log").read_text(encoding="utf-8")
suites = {}
for name, count in [("GalleryPrivacyRuntimeTest", 18), ("ChapterDeletionRuntimeTest", 14), ("ReaderAlbumRuntimeTest", 9)]:
    suite = ET.parse(RUNTIME / f"target/surefire-reports/TEST-app.jmbatch.android.{name}.xml").getroot()
    values = {k: int(suite.get(k)) for k in ("tests", "failures", "errors", "skipped")}
    assert values == dict(tests=count, failures=0, errors=0, skipped=0), values
    suites[name] = values
for path in JAVA.rglob("*.java"):
    assert lf(path.read_bytes()) == lf((RUNTIME / "src/main/java" / path.relative_to(JAVA)).read_bytes()), path
assert source_versions() == dict(windows="0.3.27", android="0.6.9")
assert not subprocess.check_output(["git", "diff", BASE, "--", "work/jmbatch"], cwd=ROOT).strip()
for path in ("work/jmbatch/update_trust.py", "work/jmbatch-android/app/src/main/java/app/jmbatch/android/UpdateTrust.java"):
    assert lf((ROOT / path).read_bytes()) == lf(original(path))
manifest_path = "work/jmbatch-android/app/src/main/AndroidManifest.xml"
current = ET.parse(ROOT / manifest_path).getroot()
old = ET.fromstring(original(manifest_path))
ns = "{http://schemas.android.com/apk/res/android}"
assert current.get(ns + "versionCode") == "609" and current.get(ns + "versionName") == "0.6.9"
for key in ("versionCode", "versionName"):
    current.set(ns + key, old.get(ns + key))
assert ET.tostring(current) == ET.tostring(old), "Permissions and package identity must be unchanged"
apk = DELIVERY / "JMBatch-0.6.9-Android.apk"
assert sha256(apk) == sha256(WORK / "builds/android-0.6.9" / apk.name)
log = (BUILD / "android-build.log").read_text(encoding="utf-8", errors="replace")
assert "name='app.jmbatch.android' versionCode='609' versionName='0.6.9'" in log
tools = WORK / "android-tools"
jvm = tools / "jdk-17.0.20.1+1/bin/java.exe"
signer = next(tools.rglob("apksigner.jar"))
certs = []
for version in ("0.6.8", "0.6.9"):
    result = subprocess.check_output([str(jvm), "-jar", str(signer), "verify", "--verbose", "--print-certs",
        str(ROOT.parent / f"Android/{version}/JMBatch-{version}-Android.apk")]).decode("utf-8")
    (REPORT / f"apk-signature-{version}.txt").write_text(result, encoding="utf-8")
    assert "Verified using v2 scheme (APK Signature Scheme v2): true" in result
    assert "Verified using v3 scheme (APK Signature Scheme v3): true" in result
    certs.append(re.search(r"Signer #1 certificate SHA-256 digest: ([a-f0-9]+)", result).group(1))
assert certs[0] == certs[1]
with zipfile.ZipFile(apk) as archive:
    assert archive.testzip() is None
    for marker in (b"0.6.9", b"GalleryPrivacy", b"ensureNoMedia", b".nomedia"):
        assert marker in archive.read("classes.dex")
files = source_files("android")
with zipfile.ZipFile(DELIVERY / "JMBatch-0.6.9-Android-source.zip") as archive:
    assert archive.testzip() is None and set(archive.namelist()) == set(files)
    for name, path in files.items():
        assert archive.read(name) == path.read_bytes(), name
notes = (WORK / "release-android-069/release-notes.md").read_bytes()
for name in ("更新日志-0.6.9.md", "release-notes-android-0.6.9.md"):
    assert (DELIVERY / name).read_bytes() == notes
assert (ROOT / "CHANGELOG.md").read_bytes().startswith(notes)
assert (DELIVERY / "安卓使用说明-0.6.9.txt").read_bytes() == (WORK / "jmbatch-android/README.txt").read_bytes()
plain = re.sub(r"^#{1,2} ", "", notes.decode("utf-8").replace("\r\n","\n"), flags=re.M).replace("- ", "• ")
text = (JAVA / "app/jmbatch/android/GithubUpdates.java").read_text(encoding="utf-8")
assert json.loads(re.search(r'CURRENT_NOTES=("(?:\\.|[^"\\])*");', text).group(1)) == plain
assert verify_manifest(DELIVERY, {"android":"0.6.9"})["tag"] == "release-android-0.6.9"
for line in (DELIVERY / "SHA256-android-0.6.9.txt").read_text(encoding="utf-8").splitlines():
    digest, name = line.split("  ", 1)
    assert digest == sha256(DELIVERY / name)
readme = (ROOT / "README.md").read_text(encoding="utf-8")
assert "release-android-0.6.9/JMBatch-0.6.9-Android.apk" in readme
assert "release-0.3.27-0.6.7/JMBatch-0.3.27-Windows-x64.zip" in readme
assert "JMBatch-0.6.8-Android.apk" not in readme
allowed = set(p.relative_to(ROOT).as_posix() for p in files.values())
allowed.update([
    "README.md", "CHANGELOG.md", "work/release-android-069/release-notes.md",
    "work/scripts/maintenance/prepare_gallery_privacy_release.py",
    "work/scripts/maintenance/check_gallery_privacy_release.py",
    "work/scripts/maintenance/verify_gallery_privacy_online.py",
    "work/scripts/release/prepare_publication_android_069.py",
    "work/scripts/release/publish_android_069.py",
    "work/scripts/release/audit_android_069.py",
    "work/scripts/release/verify_gallery_privacy_commit.py",
])
for name in allowed:
    path = ROOT / name
    assert path.suffix.lower() not in (".jks", ".pem", ".key", ".apk", ".zip")
    assert not path.is_symlink()
    assert not re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", path.read_bytes())
changed = set(subprocess.check_output(["git", "diff", "--name-only", BASE], cwd=ROOT).decode().splitlines())
assert changed <= allowed, changed - allowed
(REPORT / "pathspec.txt").write_bytes(b"\0".join(n.encode("utf-8") for n in sorted(allowed)) + b"\0")
subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, check=True)
delivery = [dict(name=p.name, size=p.stat().st_size, sha256=sha256(p)) for p in sorted(DELIVERY.iterdir()) if p.is_file()]
assert len(delivery) == 9
receipt = dict(ok=True, android="0.6.9", windows_unchanged="0.3.27", baseline=BASE, framework=suites,
    host_checks=50, apk_certificate_sha256=certs[0], packaged_source_files=len(files),
    allowed_paths=sorted(allowed), delivery=delivery, android_device_tested=False)
(REPORT / "audit.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print("AUDITED", len(files), "packaged sources,", len(allowed), "source/docs files, 41 framework cases, 50 host checks, nine delivery files, original signing identity")
