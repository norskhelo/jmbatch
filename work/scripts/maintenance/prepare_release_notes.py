"""Synchronize a local release bulletin without publishing."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--notes', required=True)
parser.add_argument('--windows', required=True)
parser.add_argument('--android', required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[3]
notes = (root / args.notes).read_text(encoding='utf-8')
plain = '\n'.join(line.lstrip('# ') if line.startswith('#') else '• ' + line[2:] if line.startswith('- ') else line for line in notes.splitlines()) + '\n'
for relative, prefix, assignment in [
    ('work/jmbatch/updates.py', 'CURRENT_NOTES = ', 'CURRENT_NOTES = ' + repr(plain)),
    ('work/jmbatch-android/app/src/main/java/app/jmbatch/android/GithubUpdates.java',
     '    private static final String CURRENT_NOTES=', '    private static final String CURRENT_NOTES=' + json.dumps(plain, ensure_ascii=False) + ';'),
]:
    path = root / relative
    lines = path.read_text(encoding='utf-8').splitlines()
    found = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    assert len(found) == 1
    lines[found[0]] = assignment
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
for source, version in [('jmbatch', args.windows), ('jmbatch-android', args.android)]:
    path = root / 'work' / source / 'README.txt'
    old = path.read_text(encoding='utf-8')
    if old.startswith('JM Batch ' + version):
        old = old.split('以下为历史说明：\n\n', 1)[-1]
    path.write_text('JM Batch ' + version + ' — 当前版本使用说明\n\n' + plain + '\n以下为历史说明：\n\n' + old, encoding='utf-8')
path = root / 'CHANGELOG.md'
old = path.read_text(encoding='utf-8')
if not old.startswith(notes.splitlines()[0]):
    path.write_text(notes + '\n' + old, encoding='utf-8')
print('Local notes synchronized.')
