"""Verify the explicit Android 0.5.22 source allowlist against HEAD and GitHub."""
from pathlib import Path
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[3]
REPORT=ROOT/'outputs/reports/chapter-speed-0522-complete'
audit=json.loads((REPORT/'audit.json').read_text(encoding='utf-8'))
def run(*args):
    return subprocess.run(args,cwd=ROOT,capture_output=True,check=True).stdout
head=run('git','rev-parse','HEAD').decode().strip();checked=[]
for entry in audit['allowed_paths']:
    name=entry['path'];local=(ROOT/name).read_bytes();committed=run('git','show',head+':'+name)
    if Path(name).suffix not in ('.bin','.sig'):
        local=local.replace(b'\r\n',b'\n');committed=committed.replace(b'\r\n',b'\n')
    assert committed==local,name
    tree=run('git','ls-tree',head,'--',name).decode().strip().split()
    checked.append(dict(path=name,blob=tree[2]))
remote='--remote' in sys.argv
if remote:
    gh=str(ROOT/'work/github-cli/bin/gh.exe')
    latest=json.loads(run(gh,'api','repos/norskhelo/jmbatch/git/ref/heads/main'))['object']['sha']
    assert latest==head,(latest,head)
    tree=json.loads(run(gh,'api',f'repos/norskhelo/jmbatch/git/trees/{head}?recursive=1'));assert not tree.get('truncated')
    blobs={e['path']:e['sha'] for e in tree['tree'] if e['type']=='blob'}
    for entry in checked:assert blobs[entry['path']]==entry['blob'],entry['path']
(REPORT/('remote-source-verification.json' if remote else 'commit-source-verification.json')).write_text(json.dumps(dict(ok=True,commit=head,remote=remote,files=checked),indent=2)+'\n',encoding='utf-8')
print('VERIFIED',len(checked),'source/release files against','GitHub main' if remote else 'HEAD',head)
