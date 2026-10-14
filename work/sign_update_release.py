"""Sign exact local package bytes with the existing update trust identity.
Default: read/write ../Win/<version> and ../Android/<version>.
--output: read/write one explicit combined staging directory. Never publishes.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Signature import pkcs1_15

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'scripts/release'))
from release_paths import (delivery_dir, distribute, package_name, sha256,
                           trusted_key, verify_manifest, version)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--windows', type=version)
    parser.add_argument('--android', type=version)
    parser.add_argument('--repository', default='norskhelo/jmbatch', choices=['norskhelo/jmbatch'])
    parser.add_argument('--output', type=Path, help='Explicit combined staging directory')
    parser.add_argument('--key', type=Path, default=ROOT / 'update-signing/release-private.pem')
    args = parser.parse_args()
    versions = {p: v for p, v in [('windows', args.windows), ('android', args.android)] if v}
    if not versions:
        parser.error('Specify --windows and/or --android')
    directories = {p: args.output.resolve() if args.output else delivery_dir(p, v) for p, v in versions.items()}
    packages = {}
    for platform, number in versions.items():
        name = package_name(platform, number)
        path = directories[platform] / name
        packages[platform] = dict(version=number, name=name, size=path.stat().st_size, sha256=sha256(path))
    raw = (json.dumps(dict(schema=1, repository=args.repository, tag=args.tag, packages=packages),
                      ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    key = RSA.import_key(args.key.read_bytes())
    if key.public_key().export_key(format='DER') != trusted_key().export_key(format='DER'):
        raise ValueError('Signing key does not match the embedded client trust key')
    signature = pkcs1_15.new(key).sign(SHA256.new(raw))
    pkcs1_15.new(trusted_key()).verify(SHA256.new(raw), signature)
    staging = ROOT / 'builds' / '-'.join(f'{p}-{v}' for p, v in versions.items()) / 'signing'
    staging.mkdir(parents=True, exist_ok=True)
    for name, data in [('update-manifest.json', raw), ('update-manifest.sig', signature)]:
        (staging / name).write_bytes(data)
    plan = [(staging / n, d / n) for d in dict.fromkeys(directories.values())
            for n in ('update-manifest.json', 'update-manifest.sig')]
    # Refuse to replace any existing manifest with different bytes, including staging.
    distribute(plan)
    for directory in dict.fromkeys(directories.values()):
        verify_manifest(directory, versions, directories)
    print('Signed local manifest for', args.tag, 'key fingerprint',
          hashlib.sha256(key.public_key().export_key(format='DER')).hexdigest()[:16])


if __name__ == '__main__':
    main()
