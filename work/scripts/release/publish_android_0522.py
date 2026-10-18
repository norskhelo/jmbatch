"""Explicitly authorized Android 0.5.22 publication recipe."""
from pathlib import Path
import base64
import json
import re
import subprocess
import sys
import urllib.request

sys.dont_write_bytecode = True
from release_paths import PROJECT, WORK, source_versions, sha256, trusted_key, verify_manifest
from Crypto.Hash import SHA256
from Crypto.Signature import pkcs1_15

REPO = 'norskhelo/jmbatch'
TAG = 'release-android-0.5.22'
VERSIONS = {'windows': '0.3.22', 'android': '0.5.22'}
OUT = WORK / 'builds/android-0.5.22/packages'
REPORT = PROJECT / 'outputs/reports/publication/android-0.5.22'
NOTES = 'release-notes-android-0.5.22.md'
NAMES = ['JMBatch-0.5.22-Android.apk', NOTES,
         'update-manifest.json', 'update-manifest.sig', 'SHA256-release-android-0.5.22.txt']
GH = str(WORK / 'github-cli/bin/gh.exe')
REPORT.mkdir(parents=True, exist_ok=True)

def run(args):
    result = subprocess.run(args, cwd=PROJECT, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))
    return result.stdout

def gh(*args):
    return run([GH, *args])

def public(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'JMBatch-Release-Verification', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()

def api(path):
    return json.loads(gh('api', f'repos/{REPO}/{path}'))

def save(name, value):
    (REPORT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def preflight():
    parent = api('git/ref/heads/main')['object']['sha']
    paths = {'windows': 'work/jmbatch/core.py', 'android': 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java'}
    remote = {}
    for platform, path in paths.items():
        src = base64.b64decode(api(f'contents/{path}?ref={parent}')['content']).decode('utf-8-sig')
        remote[platform] = re.search(r'\bVERSION\s*=\s*[\"\x27]([^\"\x27]+)', src).group(1)
    gradle = base64.b64decode(api(f'contents/work/jmbatch-android/app/build.gradle?ref={parent}')['content']).decode('utf-8-sig')
    remote_code = int(re.search(r'versionCode\s+(\d+)', gradle).group(1))
    assert remote_code <= 522
    assert re.search(r"versionName\s+'([^']+)'", gradle).group(1) == remote['android']
    assert remote['windows'] == '0.3.22' and remote['android'] in ('0.5.21', '0.5.22'), remote
    assert remote_code == {'0.5.21':521, '0.5.22':522}[remote['android']]
    run(['git', 'merge-base', '--is-ancestor', parent, 'HEAD'])
    released = {}
    for page in range(1, 11):
        batch = api(f'releases?per_page=100&page={page}')
        for release in batch:
            if release['draft'] or release['prerelease']: continue
            for asset in release['assets']:
                match = re.fullmatch(r'JMBatch-(\d+\.\d+\.\d+)-(Android\.apk|Windows-x64\.zip)', asset['name'])
                if not match: continue
                platform = 'android' if match[2] == 'Android.apk' else 'windows'
                if platform not in released or tuple(map(int, match[1].split('.'))) > tuple(map(int, released[platform].split('.'))):
                    released[platform] = match[1]
        if len(batch) < 100: break
    else: raise AssertionError('Release history exceeds verification limit')
    assert set(released) == set(VERSIONS)
    assert released['windows'] == '0.3.22' and released['android'] in ('0.5.21', '0.5.22'), released
    for platform, number in released.items():
        assert tuple(map(int, number.split('.'))) <= tuple(map(int, VERSIONS[platform].split('.')))
    latest = api('releases/latest')
    manifest_assets = {a['name']: a for a in latest['assets']}
    raw = gh('api', f'repos/{REPO}/releases/assets/{manifest_assets["update-manifest.json"]["id"]}', '-H', 'Accept: application/octet-stream')
    sig = gh('api', f'repos/{REPO}/releases/assets/{manifest_assets["update-manifest.sig"]["id"]}', '-H', 'Accept: application/octet-stream')
    pkcs1_15.new(trusted_key()).verify(SHA256.new(raw), sig)
    manifest = json.loads(raw)
    assert manifest['tag'] == latest['tag_name']
    assert source_versions() == VERSIONS
    for platform, number in remote.items():
        assert tuple(map(int, number.split('.'))) <= tuple(map(int, VERSIONS[platform].split('.'))), remote
    assert not latest['draft'] and not latest['prerelease']
    for platform, package in manifest['packages'].items():
        assert tuple(map(int, package['version'].split('.'))) <= tuple(map(int, VERSIONS[platform].split('.')))
    result = dict(remote_commit=parent, remote_versions=remote, remote_android_version_code=remote_code,
                  released_versions=released, local_versions=source_versions(),
                  latest_tag=latest['tag_name'], latest_manifest=manifest,
                  latest_tag_ref=api('git/ref/tags/' + latest['tag_name'])['object'])
    save('remote-preflight.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result

def check_assets(release):
    assert release['tag_name'] == TAG
    assert release['body'].replace('\r\n', '\n').strip() == (OUT / NOTES).read_text(encoding='utf-8').strip()
    assert {a['name'] for a in release['assets']} == set(NAMES)
    for asset in release['assets']:
        local = OUT / asset['name']
        assert asset['state'] == 'uploaded' and asset['size'] == local.stat().st_size
        assert asset['digest'] == 'sha256:' + sha256(local), asset['name']
    assert verify_manifest(OUT, {'android': '0.5.22'})['tag'] == TAG

mode = sys.argv[1]
if mode == 'preflight':
    preflight()
elif mode == 'draft':
    state = preflight()
    head = run(['git', 'rev-parse', 'HEAD']).decode().strip()
    assert state['remote_commit'] == head and state['remote_versions'] == VERSIONS, 'Push and verify release documentation first'
    assert not any(r['tag_name'] == TAG for r in api('releases?per_page=100')), 'Release already exists; inspect before retrying'
    assert verify_manifest(OUT, {'android': '0.5.22'})['tag'] == TAG
    print(gh('release', 'create', TAG, *[str(OUT / n) for n in NAMES], '--repo', REPO,
             '--target', head, '--draft', '--title', 'Android 0.5.22 — 大漫画章节删除提速',
             '--notes-file', str(OUT / NOTES)).decode(), flush=True)
    release = next(r for r in api('releases?per_page=100') if r['tag_name'] == TAG)
    check_assets(release)
    assert release['draft'] and not release['prerelease']
    save('github-draft.json', release)
    save('release-target.json', dict(commit=head, tag=TAG))
    print('Draft and all five assets verified', flush=True)
elif mode == 'verify-draft':
    release = next(r for r in api('releases?per_page=100') if r['tag_name'] == TAG)
    check_assets(release)
    assert release['draft'] and not release['prerelease']
    target = run(['git', 'rev-parse', 'HEAD']).decode().strip()
    assert release['target_commitish'] == target
    save('github-draft.json', release)
    save('release-target.json', dict(commit=target, tag=TAG))
    print('Existing draft and all five assets verified', flush=True)
elif mode in ('publish', 'verify-published'):
    state = preflight()
    target = json.loads((REPORT / 'release-target.json').read_text())['commit']
    assert state['remote_commit'] == target and state['remote_versions'] == VERSIONS
    release = next(r for r in api('releases?per_page=100') if r['tag_name'] == TAG)
    check_assets(release)
    if mode == 'publish':
        assert release['draft'] and not release['prerelease']
        print(gh('release', 'edit', TAG, '--repo', REPO, '--draft=false', '--latest').decode(), flush=True)
    published = api('releases/tags/' + TAG)
    check_assets(published)
    assert not published['draft'] and not published['prerelease'] and published['published_at']
    assert api('releases/latest')['tag_name'] == TAG
    target = json.loads((REPORT / 'release-target.json').read_text())['commit']
    assert api('git/ref/tags/' + TAG)['object']['sha'] == target
    save('github-published.json', published)
    save('publication-verification.json', dict(url=published['html_url'], tag=TAG, commit=target,
         published_at=published['published_at'], draft=False, prerelease=False, latest=True,
         versions=VERSIONS, assets=[dict(name=a['name'], size=a['size'], digest=a['digest'], url=a['browser_download_url']) for a in published['assets']]))
    print('Published and verified: ' + published['html_url'], flush=True)
else:
    raise ValueError(mode)
