"""Read-only recovery audit for the two versions displaced by this release."""
from pathlib import Path
import hashlib
import json
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "outputs/reports/dns-recovery-retention"
REPORT.mkdir(parents=True, exist_ok=True)
GH = ROOT / "work/github-cli/bin/gh.exe"
def run(*args):
    return subprocess.check_output(args, cwd=ROOT)
def api(path):
    return json.loads(run(str(GH), "api", "repos/norskhelo/jmbatch/" + path))
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
targets = []
for platform, version, tag in (("Win", "0.3.26", "release-0.3.26-0.6.6"), ("Android", "0.6.9", "release-android-0.6.9")):
    folder = ROOT.parent / platform / version
    newest = sorted([p.name for p in folder.parent.iterdir() if p.is_dir() and len(p.name.split(".")) == 3
                     and all(s.isdigit() for s in p.name.split("."))], key=lambda v: tuple(map(int, v.split("."))), reverse=True)[:5]
    assert version not in newest
    release = api("releases/tags/" + tag)
    assert not release["draft"] and not release["prerelease"]
    commit = api("git/ref/tags/" + tag)["object"]["sha"]
    run("git", "cat-file", "-e", commit + "^{commit}")
    assets = {a["name"]: a for a in release["assets"]}
    local = {p.name: p for p in folder.iterdir()}
    assert all(p.is_file() and not p.is_symlink() for p in local.values())
    installer = f"JMBatch-{version}-" + ("Windows-x64.zip" if platform == "Win" else "Android.apk")
    remote = assets[installer]
    assert remote["digest"] == "sha256:" + sha(local[installer]) and remote["size"] == local[installer].stat().st_size
    request = urllib.request.Request(remote["browser_download_url"], method="HEAD", headers={"User-Agent": "JMBatch-Recovery-Check"})
    with urllib.request.urlopen(request, timeout=45) as response:
        assert response.status == 200
        assert int(response.headers["Content-Length"]) == remote["size"]
    source = local[f"JMBatch-{version}-" + ("source.zip" if platform == "Win" else "Android-source.zip")]
    with zipfile.ZipFile(source) as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            if platform == "Win":
                relative = name.removeprefix("JMBatch-source/")
            else:
                assert name.startswith("JMBatch-Android/")
                relative = "work/jmbatch-android/" + name.removeprefix("JMBatch-Android/")
            blob = run("git", "show", commit + ":" + relative)
            saved = archive.read(name)
            assert blob.replace(b"\r\n", b"\n") == saved.replace(b"\r\n", b"\n"), relative
        readme = next(archive.read(name) for name in archive.namelist() if name.endswith("/README.txt"))
    receipts = []
    for name, path in local.items():
        digest = sha(path)
        if name in assets:
            assert assets[name]["digest"] == "sha256:" + digest, name
            recovery = "GitHub Release asset"
        elif name.endswith("source.zip"):
            recovery = "Verified source files at Git commit " + commit
        elif name.startswith("更新日志-"):
            assert path.read_text(encoding="utf-8").strip() == release["body"].replace("\r\n", "\n").strip()
            recovery = "GitHub Release body"
        elif "使用说明-" in name:
            assert path.read_bytes() == readme
            recovery = "README.txt at Git commit " + commit
        elif name.startswith("SHA256-"):
            for line in path.read_text(encoding="utf-8").splitlines():
                expected, target = line.split("  ", 1)
                assert (sha(local[target]) if target in local else assets[target]["digest"].removeprefix("sha256:")) == expected
            recovery = "Derived checksum list"
        else:
            raise AssertionError("Unverified extra file: " + name)
        receipts.append(dict(path=str(path), sha256=digest, size=path.stat().st_size, recovery=recovery))
    targets.append(dict(path=str(folder), retained=newest, commit=commit, release=release["html_url"], files=receipts))
result = dict(ok=True, targets=targets)
(REPORT / "recovery.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(dict(ok=True, targets=[dict(path=t["path"], retained=t["retained"]) for t in targets]), ensure_ascii=False))
