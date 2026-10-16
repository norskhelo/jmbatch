"""Verify the public update path in isolation; never launches an installer."""
from pathlib import Path
import sys, json, threading, io, base64, subprocess, urllib.request

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'work/jmbatch'))
from updates import fetch_release, fetch_bulletin, announcement_text, DEFAULT_REPOSITORY
from update_install import prepare, transfer, verify_file
from update_trust import PUBLIC_KEY
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Signature import pkcs1_15

scratch=ROOT/'work/tests/history-fix-033-043-online'
report=ROOT/'outputs/reports/history-fix-033-043-online'
scratch.mkdir(parents=True,exist_ok=True);report.mkdir(parents=True,exist_ok=True)
latest=fetch_release(DEFAULT_REPOSITORY,'0.3.2')
assert latest and latest['version']=='0.3.3'
assert fetch_release(DEFAULT_REPOSITORY,'0.3.3') is None
notes=(ROOT/'work/release-033-043/release-notes.md').read_text(encoding='utf-8').strip()
assert latest['history'][-1]['notes'].replace('\r\n', '\n').strip()==notes
current=fetch_bulletin(DEFAULT_REPOSITORY,'0.3.3')
assert current['version']=='0.3.3' and '跨版本更新公告修复' in current['notes']
history=fetch_bulletin(DEFAULT_REPOSITORY,'0.2.2')
expected=['0.2.3','0.2.4','0.3.0','0.3.1','0.3.2','0.3.3']
assert [entry['version'] for entry in history['history']]==expected
shown=announcement_text(history,DEFAULT_REPOSITORY,'0.3.3',notes,'0.2.2')
assert '本次升级：0.2.2 → 0.3.3' in shown and '可用更新：' not in shown
for entry in history['history']:assert entry['notes'] in shown
(report/'windows-completed-upgrade.txt').write_text(shown,encoding='utf-8')
(report/'windows-history.json').write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
print('Public update selection and six-release completed upgrade notes verified',flush=True)

# Exercise the same Android history rules with real published assets and bodies.
# This is a host check, not a device/UI test.
releases=[]
for page in range(1,11):
    request=urllib.request.Request(f'https://api.github.com/repos/{DEFAULT_REPOSITORY}/releases?per_page=100&page={page}',
                                   headers={'User-Agent':'JMBatch-Release-Verification'})
    with urllib.request.urlopen(request,timeout=30) as response: batch=json.load(response)
    releases.extend(batch)
    if len(batch)<100:break
else:raise AssertionError('Release list was truncated')
rows=[]
for release in releases:
    for asset in release['assets']:
        if not asset['name'].endswith('-Android.apk'):continue
        values=[asset['name'],asset['browser_download_url'],asset['state'],str(asset['size']),
                str(release['draft']).lower(),str(release['prerelease']).lower(),
                release.get('body') or '',release.get('published_at') or '']
        rows.append('\t'.join(base64.b64encode(value.encode('utf-8')).decode('ascii') for value in values))
(scratch/'android-releases.tsv').write_text('\n'.join(rows),encoding='utf-8')
runner=scratch/'LiveHistory.java'
runner.write_text(r'''
import app.jmbatch.android.UpdateHistory;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
public class LiveHistory {
    public static void main(String[] args)throws Exception{
        String repo="norskhelo/jmbatch";
        List<UpdateHistory.Entry> entries=new ArrayList<>();
        for(String row:Files.readAllLines(Paths.get(args[0]),StandardCharsets.UTF_8)){
            String[] fields=row.split("\t",-1);
            for(int i=0;i<fields.length;i++)fields[i]=new String(Base64.getDecoder().decode(fields[i]),StandardCharsets.UTF_8);
            entries.add(UpdateHistory.candidate(repo,fields[0],fields[1],fields[2],Long.parseLong(fields[3]),
                Boolean.parseBoolean(fields[4]),Boolean.parseBoolean(fields[5]),fields[6],fields[7]));
        }
        UpdateHistory.Selection selected=UpdateHistory.select(entries,"0.3.2");
        List<String> expected=Arrays.asList("0.3.3","0.3.4","0.4.0","0.4.1","0.4.2","0.4.3");
        List<String> actual=new ArrayList<>();
        for(UpdateHistory.Entry entry:selected.history)actual.add(entry.version);
        if(!actual.equals(expected)||!selected.latest.version.equals("0.4.3"))throw new AssertionError(actual);
        String shown=UpdateHistory.announcement(repo,repo,selected.fromVersion,selected.latest.version,
            "0.4.3",selected.history,"local","0.3.2");
        if(!shown.startsWith("本次升级：0.3.2 → 0.4.3")||shown.contains("可用更新："))throw new AssertionError(shown);
        for(UpdateHistory.Entry entry:selected.history)if(!shown.contains(entry.notes))throw new AssertionError(entry.version);
        Files.write(Paths.get(args[1]),shown.getBytes(StandardCharsets.UTF_8));
        System.out.println("Android published six-release upgrade history verified: "+actual);
    }
}
''',encoding='utf-8')
jdk=next((ROOT/'work/android-tools').glob('jdk-*'))/'bin'
java_source=ROOT/'work/jmbatch-android/app/src/main/java/app/jmbatch/android'
classes=scratch/'classes';classes.mkdir(exist_ok=True)
subprocess.run([str(jdk/'javac.exe'),'-encoding','UTF-8','-d',str(classes),str(java_source/'UpdateRules.java'),
                str(java_source/'UpdateHistory.java'),str(runner)],check=True)
subprocess.run([str(jdk/'java.exe'),'-cp',str(classes),'LiveHistory',str(scratch/'android-releases.tsv'),
                str(report/'android-completed-upgrade.txt')],check=True)
def progress(value):
    if '%' not in value:print(value,flush=True)
ready=prepare(scratch,latest,'0.3.2',threading.Event(),progress)
base=latest['url'].rsplit('/',1)[0]+'/'
manifest,signature=io.BytesIO(),io.BytesIO()
transfer(base+'update-manifest.json',manifest,65536,threading.Event())
transfer(base+'update-manifest.sig',signature,4096,threading.Event())
pkcs1_15.new(RSA.import_key(base64.b64decode(PUBLIC_KEY))).verify(SHA256.new(manifest.getvalue()),signature.getvalue())
metadata=json.loads(manifest.getvalue())
assert metadata['tag']=='release-0.3.3-0.4.3' and metadata['repository']==DEFAULT_REPOSITORY
apk=metadata['packages']['android'];assert apk['version']=='0.4.3'
file=scratch/apk['name']
with file.open('wb') as stream:transfer(base+apk['name'],stream,apk['size'],threading.Event())
verify_file(file,apk)
receipt=dict(ok=True,repository=DEFAULT_REPOSITORY,tag=metadata['tag'],windows='0.3.3',android='0.4.3',
             windows_download_verified=True,android_download_verified=True,windows_staged=True,
             signature_verified=True,notes_verified=True,windows_upgrade_history=expected,
             android_upgrade_history=['0.3.3','0.3.4','0.4.0','0.4.1','0.4.2','0.4.3'],
             installer_launched=False,android_device_tested=False)
(report/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt),flush=True)
