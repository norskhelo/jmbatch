"""Check public update discovery and both signed installers without installing."""
from pathlib import Path
import sys
import json
import threading
import io
import base64

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'work/jmbatch'))
from updates import fetch_release,fetch_bulletin,DEFAULT_REPOSITORY
from update_install import prepare,transfer,verify_file
from update_trust import PUBLIC_KEY
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Signature import pkcs1_15

scratch=ROOT/'work/tests/batch_export-0317-0513-online';scratch.mkdir(parents=True,exist_ok=True)
report=ROOT/'outputs/reports/batch_export-0317-0513-online';report.mkdir(parents=True,exist_ok=True)
latest=fetch_release(DEFAULT_REPOSITORY,'0.3.16')
assert latest and latest['version']=='0.3.17'
assert fetch_release(DEFAULT_REPOSITORY,'0.3.17') is None
notes=(ROOT/'work/release-0317-0513/release-notes.md').read_text(encoding='utf-8').strip()
assert latest['history'][-1]['notes'].replace('\r\n','\n').strip()==notes
current=fetch_bulletin(DEFAULT_REPOSITORY,'0.3.17')
assert current['version']=='0.3.17' and '漫画库批量导出' in current['notes']
history=fetch_bulletin(DEFAULT_REPOSITORY,'0.3.0')
assert [entry['version'] for entry in history['history']]==[f'0.3.{n}' for n in range(1,18)]
(report/'windows-history.json').write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
print('Public update selection and matching full notes verified',flush=True)
def progress(value):
    if '%' not in value:print(value,flush=True)
ready=prepare(scratch,latest,'0.3.16',threading.Event(),progress)
base=latest['url'].rsplit('/',1)[0]+'/'
manifest,signature=io.BytesIO(),io.BytesIO()
transfer(base+'update-manifest.json',manifest,65536,threading.Event())
transfer(base+'update-manifest.sig',signature,4096,threading.Event())
pkcs1_15.new(RSA.import_key(base64.b64decode(PUBLIC_KEY))).verify(SHA256.new(manifest.getvalue()),signature.getvalue())
metadata=json.loads(manifest.getvalue())
assert metadata['tag']=='release-0.3.17-0.5.13' and metadata['repository']==DEFAULT_REPOSITORY
apk=metadata['packages']['android'];assert apk['version']=='0.5.13'
file=scratch/apk['name']
with file.open('wb') as stream:transfer(base+apk['name'],stream,apk['size'],threading.Event())
verify_file(file,apk)
receipt=dict(ok=True,repository=DEFAULT_REPOSITORY,tag=metadata['tag'],windows='0.3.17',android='0.5.13',
    windows_download_verified=True,android_download_verified=True,windows_staged=True,
    signature_verified=True,notes_verified=True,installer_launched=False,android_device_tested=False)
(report/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt),flush=True)
