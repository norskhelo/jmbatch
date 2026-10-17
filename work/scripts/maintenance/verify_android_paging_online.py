"""Read public releases and exercise production Android selection/signature/hash rules."""
from pathlib import Path
import json,re,subprocess,sys,threading,urllib.request

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'work/jmbatch'))
from updates import fetch_release,fetch_bulletin,DEFAULT_REPOSITORY
from update_install import transfer

scratch=ROOT/'work/tests/paging-055-online';scratch.mkdir(parents=True,exist_ok=True)
report=ROOT/'outputs/reports/paging-055-online';report.mkdir(parents=True,exist_ok=True)
def public(url):
    request=urllib.request.Request(url,headers={'User-Agent':'JMBatch-Public-Update-Check','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request,timeout=45) as response:return response.read()
releases=[]
for page in range(1,11):
    batch=json.loads(public(f'https://api.github.com/repos/{DEFAULT_REPOSITORY}/releases?per_page=100&page={page}'))
    releases.extend(batch)
    if len(batch)<100:break
else:raise AssertionError('Update history too large')
latest=json.loads(public(f'https://api.github.com/repos/{DEFAULT_REPOSITORY}/releases/latest'))
assert latest['tag_name']=='release-0.3.11-0.5.5' and not latest['draft'] and not latest['prerelease']
notes=(ROOT/'work/release-0311-055/release-notes.md').read_text(encoding='utf-8').strip()
assert latest['body'].replace('\r\n','\n').strip()==notes
assets={a['name']:a for a in latest['assets']}
for name,limit in [('update-manifest.json',65536),('update-manifest.sig',4096)]:
    with (scratch/name).open('wb') as stream:transfer(assets[name]['browser_download_url'],stream,limit,threading.Event())
metadata=json.loads((scratch/'update-manifest.json').read_bytes())
assert metadata['tag']==latest['tag_name'] and metadata['repository']==DEFAULT_REPOSITORY
apk=metadata['packages']['android'];assert apk['version']=='0.5.5'
with (scratch/apk['name']).open('wb') as stream:transfer(assets[apk['name']]['browser_download_url'],stream,apk['size'],threading.Event())
(scratch/'notes.txt').write_text(notes,encoding='utf-8')
entries=[]
for release in releases:
    for asset in release['assets']:
        if re.fullmatch(r'JMBatch-[0-9.]+-Android\.apk',asset['name']):
            values=[DEFAULT_REPOSITORY,asset['name'],asset['browser_download_url'],asset['state']]
            args=','.join(json.dumps(v,ensure_ascii=True) for v in values)
            args+=f",{asset['size']}L,{str(release['draft']).lower()},{str(release['prerelease']).lower()},"
            args+=json.dumps(release['body'] or '',ensure_ascii=True)+','+json.dumps(release['published_at'] or '')
            entries.append('entries.add(UpdateHistory.candidate('+args+'));')
java='''import app.jmbatch.android.*;import java.util.*;import java.nio.file.*;
public class LiveCancelUpdate {public static void main(String[] args)throws Exception {
List<UpdateHistory.Entry> entries=new ArrayList<>();
'''+ '\n'.join(entries)+'''
UpdateHistory.Selection next=UpdateHistory.select(entries,"0.5.4");
if(next==null||!next.latest.version.equals("0.5.5")||next.history.size()!=1)throw new AssertionError("upgrade selection");
Path root=Paths.get(args[0]);String notes=new String(Files.readAllBytes(root.resolve("notes.txt")),"UTF-8").replace("\\r\\n","\\n").trim();
if(!next.latest.notes.replace("\\r\\n","\\n").trim().equals(notes))throw new AssertionError("release notes");
UpdateHistory.Selection installed=UpdateHistory.select(entries,"0.5.5");
if(UpdateRules.compare(installed.latest.version,"0.5.5")!=0)throw new AssertionError("installed update");
String announcement=UpdateHistory.announcement("norskhelo/jmbatch","norskhelo/jmbatch","0.5.4","0.5.5","0.5.5",next.history,"local");
if(!announcement.contains("左右翻页流畅度修复"))throw new AssertionError("announcement");
UpdateHistory.Selection history=UpdateHistory.select(entries,"0.4.0");
if(history.history.size()!=15)throw new AssertionError("full history "+history.history.size());
UpdateCrypto.verify(Files.readAllBytes(root.resolve("update-manifest.json")),Files.readAllBytes(root.resolve("update-manifest.sig")));
UpdateCrypto.verifyFile(root.resolve(args[1]).toFile(),Long.parseLong(args[2]),args[3]);
System.out.println("Production Android update selection, 15-release history, notes, RSA signature and downloaded APK hash verified");}}
'''
program=scratch/'LiveCancelUpdate.java';program.write_text(java,encoding='utf-8')
src=ROOT/'work/jmbatch-android/app/src/main/java/app/jmbatch/android'
jdk=next((ROOT/'work/android-tools').glob('jdk-*'))
subprocess.run([str(jdk/'bin/javac.exe'),'-encoding','UTF-8','-d',str(scratch),*[str(src/(name+'.java')) for name in ('UpdateRules','UpdateHistory','UpdateCrypto','UpdateTrust')],str(program)],check=True)
subprocess.run([str(jdk/'bin/java.exe'),'-cp',str(scratch),'LiveCancelUpdate',str(scratch),apk['name'],str(apk['size']),apk['sha256']],check=True)
assert fetch_release(DEFAULT_REPOSITORY,'0.3.10')['version']=='0.3.11'
assert fetch_bulletin(DEFAULT_REPOSITORY,'0.3.11')['version']=='0.3.11'
receipt=dict(ok=True,tag=latest['tag_name'],android='0.5.5',windows='0.3.11',
    production_android_rules_checked=True,public_apk_download_verified=True,signature_verified=True,
    full_history_versions=15,installer_launched=False,android_device_tested=False)
(report/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(report/'public-release.json').write_text(json.dumps(latest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt),flush=True)
