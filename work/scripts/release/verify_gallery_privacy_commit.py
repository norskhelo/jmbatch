"""Compare local release sources to the immutable commit and optional remote tree."""
from pathlib import Path
import io
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
REPORT=ROOT/'outputs/reports/gallery-privacy-069-complete'
audit=json.loads((REPORT/'audit.json').read_text(encoding='utf-8'))
def run(*args):return subprocess.check_output(args,cwd=ROOT)
head=run('git','rev-parse','HEAD').decode().strip()
tree={line.split('\t',1)[1]:line.split()[2] for line in run('git','ls-tree','-r',head).decode().splitlines()}
names=audit['allowed_paths']
query=''.join(head+':'+name+'\n' for name in names).encode()
output=subprocess.run(['git','cat-file','--batch'],input=query,cwd=ROOT,capture_output=True,check=True).stdout
stream=io.BytesIO(output);checked=[]
for name in names:
    blob,kind,size=stream.readline().decode().strip().split()
    assert kind=='blob' and tree[name]==blob,name
    committed=stream.read(int(size));assert stream.read(1)==b'\n'
    local=(ROOT/name).read_bytes()
    if Path(name).suffix not in ('.bin','.sig'):
        local=local.replace(b'\r\n',b'\n');committed=committed.replace(b'\r\n',b'\n')
    assert local==committed,name
    checked.append(dict(path=name,blob=blob))
assert stream.read()==b''
remote='--remote' in sys.argv
if remote:
    gh=str(ROOT/'work/github-cli/bin/gh.exe')
    assert json.loads(run(gh,'api','repos/norskhelo/jmbatch/git/ref/heads/main'))['object']['sha']==head
    response=json.loads(run(gh,'api',f'repos/norskhelo/jmbatch/git/trees/{head}?recursive=1'))
    assert not response.get('truncated')
    blobs={entry['path']:entry['sha'] for entry in response['tree'] if entry['type']=='blob'}
    for item in checked:assert blobs[item['path']]==item['blob'],item['path']
receipt=dict(ok=True,commit=head,remote=remote,files=checked)
(REPORT/('remote-source-verification.json' if remote else 'commit-source-verification.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print('Verified',len(checked),'source/release files against', 'GitHub main' if remote else 'HEAD',head)
