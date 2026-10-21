"""Check reviewed release sources, packages and the immutable pushed commit."""
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / 'outputs/reports/bookmarks-0330-0612-complete'
REPORT.mkdir(parents=True, exist_ok=True)
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'work'))
from package_network_update import source_files
from release_paths import source_versions, delivery_dir, sha256, verify_manifest

def run(*args):
    return subprocess.check_output(args, cwd=ROOT)

def save(name, value):
    (REPORT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

mode = sys.argv[1]
if mode == 'packages':
    versions = {'windows': '0.3.30', 'android': '0.6.12'}
    assert source_versions() == versions
    tracked = set(run('git', 'ls-files', '-z').decode().split('\0'))
    names = set(run('git', 'diff', '--cached', '--name-only').decode().splitlines())
    verified = []
    directories = {p: delivery_dir(p, v) for p, v in versions.items()}
    for platform, version in versions.items():
        verify_manifest(directories[platform], versions, directories)
        sources = {name: path for name, path in source_files(platform).items() if path.relative_to(ROOT).as_posix() in tracked}
        filename = f'JMBatch-{version}-' + ('source.zip' if platform == 'windows' else 'Android-source.zip')
        with zipfile.ZipFile(directories[platform] / filename) as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == set(sources)
            for name, path in sources.items():
                relative = path.relative_to(ROOT).as_posix()
                assert archive.read(name) == path.read_bytes(), relative
                assert not path.suffix.lower() in ('.jks', '.keystore', '.key', '.pem')
                names.add(relative)
                verified.append(dict(path=relative, sha256=sha256(path)))
        build_report = ROOT / 'outputs/reports' / ('bookmarks-0330-0612-' + platform + ('-final' if platform == 'android' else ''))
        assert all(item['exit_code'] == 0 for item in json.loads((build_report / 'checks.json').read_text()))
        for path, digest in json.loads((build_report / 'source-hashes.json').read_text()).items():
            assert sha256(ROOT / path) == digest, path
    for path in ('work/jmbatch/update_trust.py', 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/UpdateTrust.java'):
        assert (ROOT / path).read_bytes().replace(b'\r\n', b'\n') == run('git', 'show', 'HEAD:' + path).replace(b'\r\n', b'\n')
    assert not any('DnsTransportAuditRuntimeTest' in n or 'TransportAuditServer' in n for n in names)
    save('audit.json', dict(ok=True, versions=versions, allowed_paths=sorted(names), packaged_sources=verified,
         update_keys_preserved=True, untracked_diagnostics_excluded=True, android_device_tested=False))
    print('Verified', len(verified), 'packaged source files and', len(names), 'reviewed commit paths')
elif mode in ('commit', 'remote'):
    audit = json.loads((REPORT / 'audit.json').read_text(encoding='utf-8'))
    head = run('git', 'rev-parse', 'HEAD').decode().strip()
    names = audit['allowed_paths']
    query = ''.join(head + ':' + name + '\n' for name in names).encode()
    stream = io.BytesIO(subprocess.run(['git', 'cat-file', '--batch'], input=query, cwd=ROOT, capture_output=True, check=True).stdout)
    checked = []
    for name in names:
        blob, kind, size = stream.readline().decode().strip().split()
        assert kind == 'blob'
        committed = stream.read(int(size)); assert stream.read(1) == b'\n'
        local = (ROOT / name).read_bytes()
        if Path(name).suffix not in ('.bin', '.sig'):
            local = local.replace(b'\r\n', b'\n'); committed = committed.replace(b'\r\n', b'\n')
        assert local == committed, name
        checked.append(dict(path=name, blob=blob))
    assert stream.read() == b''
    if mode == 'remote':
        gh = str(ROOT / 'work/github-cli/bin/gh.exe')
        assert json.loads(run(gh, 'api', 'repos/norskhelo/jmbatch/git/ref/heads/main'))['object']['sha'] == head
        tree = json.loads(run(gh, 'api', f'repos/norskhelo/jmbatch/git/trees/{head}?recursive=1'))
        assert not tree.get('truncated')
        blobs = {item['path']: item['sha'] for item in tree['tree'] if item['type'] == 'blob'}
        for item in checked:
            assert blobs[item['path']] == item['blob'], item['path']
    save(mode + '-source-verification.json', dict(ok=True, commit=head, files=checked))
    print('Verified', len(checked), 'files against', mode, head)
else:
    raise ValueError(mode)
