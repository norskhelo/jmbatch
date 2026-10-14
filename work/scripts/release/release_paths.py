"""Local release paths and integrity checks shared by packaging/signing tools."""
import ast
import base64
import hashlib
import json
import re
import shutil
from pathlib import Path

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

PROJECT = Path(__file__).resolve().parents[3]
WORK = PROJECT / 'work'
WORKSPACE = PROJECT.parent
PLATFORMS = {'windows': 'Win', 'android': 'Android'}


def version(value):
    if not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('Expected a numeric application version: ' + value)
    return value


def python_constant(path, name):
    for node in ast.parse(path.read_text(encoding='utf-8-sig')).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError(f'Missing {name} in {path}')


def source_versions():
    java = (WORK / 'jmbatch-android/app/src/main/java/app/jmbatch/android/Core.java').read_text(encoding='utf-8')
    return {'windows': version(python_constant(WORK / 'jmbatch/core.py', 'VERSION')),
            'android': version(re.search(r'\bVERSION\s*=\s*"([^"]+)"', java).group(1))}


def build_dir(platform, number):
    return WORK / 'builds' / f'{platform}-{version(number)}'


def delivery_dir(platform, number, workspace=WORKSPACE):
    return workspace / PLATFORMS[platform] / version(number)


def package_name(platform, number):
    suffix = {'windows': 'Windows-x64.zip', 'android': 'Android.apk'}[platform]
    return f'JMBatch-{version(number)}-{suffix}'


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def trusted_key():
    encoded = python_constant(WORK / 'jmbatch/update_trust.py', 'PUBLIC_KEY')
    java = (WORK / 'jmbatch-android/app/src/main/java/app/jmbatch/android/UpdateTrust.java').read_text(encoding='utf-8')
    if re.search(r'PUBLIC_KEY\s*=\s*"([^"]+)"', java).group(1) != encoded:
        raise ValueError('Windows and Android update trust keys differ')
    return RSA.import_key(base64.b64decode(encoded))


def verify_manifest(directory, versions, package_dirs=None):
    raw = (directory / 'update-manifest.json').read_bytes()
    signature = (directory / 'update-manifest.sig').read_bytes()
    pkcs1_15.new(trusted_key()).verify(SHA256.new(raw), signature)
    manifest = json.loads(raw)
    if manifest['schema'] != 1 or manifest['repository'] != 'norskhelo/jmbatch':
        raise ValueError('Unexpected manifest schema or repository')
    for platform, number in versions.items():
        meta = manifest['packages'][platform]
        name = package_name(platform, number)
        path = (package_dirs[platform] if package_dirs else directory) / name
        if (meta['version'] != number or meta['name'] != name or
                meta['size'] != path.stat().st_size or meta['sha256'] != sha256(path)):
            raise ValueError('Manifest does not match ' + str(path))
    return manifest


def distribute(plan):
    """Preflight every destination; existing identical files are safe to reuse."""
    plan = list(plan)
    seen = set()
    for source, target in plan:
        if not source.is_file():
            raise FileNotFoundError(source)
        if target in seen:
            raise ValueError('Duplicate delivery destination: ' + str(target))
        seen.add(target)
        if any(p.is_symlink() or p.is_junction() for p in (target, *target.parents)):
            raise ValueError('Linked delivery destination is not allowed: ' + str(target))
        if target.exists() and (not target.is_file() or sha256(target) != sha256(source)):
            raise FileExistsError('Existing delivery differs; use a new version: ' + str(target))
    for source, target in plan:
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open('rb') as incoming, target.open('xb') as outgoing:
            shutil.copyfileobj(incoming, outgoing)
        if sha256(target) != sha256(source):
            raise IOError('Delivery copy verification failed: ' + str(target))
