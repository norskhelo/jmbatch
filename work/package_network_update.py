"""Package locally and deliver to ../Win/<version> and ../Android/<version>.

--output retains the explicit, combined staging-only mode.
--reuse-release preserves already-signed installers byte for byte.
No operation in this script pushes, uploads, or publishes.
"""
import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'scripts/release'))
from release_paths import (PROJECT, build_dir, delivery_dir, distribute,
                           package_name, sha256, source_versions, verify_manifest)


def archive(files, target):
    """Explicit entries, deterministic source archives, no signing credentials."""
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name, path in sorted(files.items()):
            if (path.is_symlink() or path.suffix.lower() in ('.jks', '.keystore', '.key')
                    or path.name.lower() == 'release-private.pem'):
                raise ValueError('Forbidden archive entry: ' + str(path))
            data = path.read_bytes()
            if path.suffix.lower() == '.pem' and b'PRIVATE KEY' in data:
                raise ValueError('Private PEM cannot be packaged')
            entry = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            bundle.writestr(entry, data)
    with zipfile.ZipFile(target) as bundle:
        if bundle.testzip() is not None:
            raise ValueError('Archive CRC check failed: ' + str(target))


def source_files(platform):
    source = ROOT / ('jmbatch' if platform == 'windows' else 'jmbatch-android')
    if platform == 'windows':
        paths = list(source.glob('*.py'))
        paths += [source / n for n in ('README.txt', 'requirements.txt', 'build.ps1')]
        paths += list((source / 'tests').glob('test_*.py'))
        paths += [p for p in (source / 'THIRD_PARTY_LICENSES').rglob('*') if p.is_file()]
        # Preserve the project layout so build.ps1 and the existing spec still work.
        files = {'JMBatch-source/work/jmbatch/' + p.relative_to(source).as_posix(): p for p in paths}
        for name in ('work/JMBatch.spec', 'work/scripts/maintenance/check_development.py',
                     'tools/setup_windows.ps1'):
            files['JMBatch-source/' + name] = PROJECT / name
        return files
    paths = [source / n for n in ('build.py', 'build.gradle', 'settings.gradle',
                                  'README.txt', 'THIRD_PARTY_NOTICES.txt', 'app/build.gradle')]
    if (source / '.gitignore').is_file():
        paths.append(source / '.gitignore')
    paths += [p for p in (source / 'app/src').rglob('*') if p.suffix in ('.java', '.xml', '.txt')]
    paths += list((source / 'tests').glob('*.java'))
    paths += list((source / 'tests').glob('test_*.py'))
    paths.append(source / 'tests/run_network_tests.py')
    paths += [source / 'tests/runtime' / n for n in ('pom.xml', 'README.md', 'READER_SCROLL_REPRO.txt')]
    paths += list((source / 'tests/runtime/src/test/java').rglob('*.java'))
    paths += [source / 'tests/fixtures' / n for n in ('manifest.bin', 'manifest.sig')]
    return {'JMBatch-Android/' + p.relative_to(source).as_posix(): p for p in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=('both', 'windows', 'android'), default='both')
    parser.add_argument('--output', type=Path, help='Combined staging only; skip platform delivery')
    parser.add_argument('--windows-dist', type=Path)
    parser.add_argument('--android-apk', type=Path)
    parser.add_argument('--notes', type=Path, help='User-facing release notes for these versions')
    parser.add_argument('--tag', help='Tag to record in a freshly signed LOCAL manifest')
    parser.add_argument('--reuse-release', type=Path, help='Existing signed combined release directory')
    parser.add_argument('--tracked-sources-only', action='store_true', help='Include only reviewed Git-tracked/staged source files, excluding unrelated local diagnostics')
    args = parser.parse_args()
    tracked = None
    if args.tracked_sources_only:
        tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=PROJECT).decode('utf-8').split('\0'))
    if args.reuse_release and args.tag:
        parser.error('--reuse-release and --tag are mutually exclusive')
    if not args.output and not (args.tag or args.reuse_release):
        parser.error('Final delivery requires --tag or --reuse-release; --output allows staging only')
    versions = source_versions()
    if args.platform != 'both':
        versions = {args.platform: versions[args.platform]}
    combination = '-'.join(f'{p}-{v}' for p, v in versions.items())
    out = (args.output or ROOT / 'builds' / combination / 'packages').resolve()
    all_versions = source_versions()
    notes = args.notes or ROOT / ('release-' + '-'.join(v.replace('.', '') for v in all_versions.values())) / 'release-notes.md'
    if not notes.is_file():
        parser.error('Release notes are required; supply --notes')
    if args.reuse_release:
        args.reuse_release = args.reuse_release.resolve()
        if out == args.reuse_release:
            parser.error('Staging must differ from the original signed release')
        verify_manifest(args.reuse_release, versions)
    out.mkdir(parents=True, exist_ok=True)
    platform_files = {}
    notes_name = '更新日志-' + '-'.join(versions.values()) + '.md'
    shutil.copy2(notes, out / notes_name)
    for platform, number in versions.items():
        name = package_name(platform, number)
        if args.reuse_release:
            shutil.copy2(args.reuse_release / name, out / name)
        elif platform == 'windows':
            dist = (args.windows_dist or build_dir(platform, number) / 'dist/JMBatch').resolve()
            if not (dist / 'JMBatch.exe').is_file():
                raise FileNotFoundError(dist / 'JMBatch.exe')
            files = {'JMBatch/' + p.relative_to(dist).as_posix(): p for p in dist.rglob('*') if p.is_file()}
            files['JMBatch/README.txt'] = ROOT / 'jmbatch/README.txt'
            files['JMBatch/CHANGELOG.md'] = notes
            licenses = ROOT / 'jmbatch/THIRD_PARTY_LICENSES'
            files.update({'JMBatch/THIRD_PARTY_LICENSES/' + p.relative_to(licenses).as_posix(): p
                          for p in licenses.rglob('*') if p.is_file()})
            archive(files, out / name)
        else:
            apk = args.android_apk or build_dir(platform, number) / name
            with zipfile.ZipFile(apk) as bundle:
                if bundle.testzip() is not None or 'classes.dex' not in bundle.namelist():
                    raise ValueError('Invalid Android package')
            shutil.copy2(apk, out / name)
        source_name = f'JMBatch-{number}-' + ('source.zip' if platform == 'windows' else 'Android-source.zip')
        sources = source_files(platform)
        if tracked is not None:
            sources = {name: path for name, path in sources.items() if path.relative_to(PROJECT).as_posix() in tracked}
        archive(sources, out / source_name)
        readme = ('使用说明-' if platform == 'windows' else '安卓使用说明-') + number + '.txt'
        shutil.copy2(ROOT / ('jmbatch' if platform == 'windows' else 'jmbatch-android') / 'README.txt', out / readme)
        platform_files[platform] = [name, source_name, readme, notes_name]
    if args.reuse_release:
        for name in ('update-manifest.json', 'update-manifest.sig'):
            shutil.copy2(args.reuse_release / name, out / name)
    elif args.tag:
        command = [sys.executable, str(ROOT / 'sign_update_release.py'), '--output', str(out), '--tag', args.tag]
        for platform, number in versions.items():
            command.extend(['--' + platform, number])
        subprocess.run(command, check=True)
    signed = bool(args.tag or args.reuse_release)
    manifest = verify_manifest(out, versions) if signed else None
    plan = []
    for platform, names in platform_files.items():
        number = versions[platform]
        if signed:
            names.extend(['update-manifest.json', 'update-manifest.sig'])
        checksum = f'SHA256-{platform}-{number}.txt'
        (out / checksum).write_text(''.join(sha256(out / n) + '  ' + n + '\n' for n in names), encoding='utf-8')
        names.append(checksum)
        destination = out if args.output else delivery_dir(platform, number)
        plan.extend((out / n, destination / n) for n in names)
    if not args.output:
        distribute(plan)
        destinations = {p: delivery_dir(p, v) for p, v in versions.items()}
        for directory in destinations.values():
            verify_manifest(directory, versions, destinations)
    report = PROJECT / 'outputs/reports/delivery' / combination
    report.mkdir(parents=True, exist_ok=True)
    (report / ('staging.json' if args.output else 'delivery.json')).write_text(json.dumps(
        dict(versions=versions, reused_signed_installers=bool(args.reuse_release),
             manifest=manifest, pushed=False, published=False,
             files=[dict(path=str(t), sha256=sha256(t), size=t.stat().st_size) for s, t in plan]),
        ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for platform, names in platform_files.items():
        destination = out if args.output else delivery_dir(platform, versions[platform])
        print('STAGED' if args.output else 'DELIVERED', platform, destination, len(names), 'files')
    print('Local packaging complete; nothing pushed or published.')


if __name__ == '__main__':
    main()
