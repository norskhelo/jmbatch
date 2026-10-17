"""Download signed public assets through all production routes; never install."""
import argparse
import base64
import io
import json
from pathlib import Path
import subprocess
import sys
import threading
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'work/jmbatch'))
import update_download
from update_install import verify_file
from update_trust import PUBLIC_KEY
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

parser = argparse.ArgumentParser()
parser.add_argument('--tag', default='release-0.3.13-0.5.7')
parser.add_argument('--run-id', default='update-mirror-routes-0313-057')
args = parser.parse_args()
assert all(c.isalnum() or c in '-_.' for c in args.tag) and '..' not in args.tag
assert all(c.isalnum() or c in '-_' for c in args.run_id)
scratch = ROOT / 'work/tests' / args.run_id; scratch.mkdir(parents=True, exist_ok=True)
report = ROOT / 'outputs/reports' / args.run_id; report.mkdir(parents=True, exist_ok=True)
base = 'https://github.com/norskhelo/jmbatch/releases/download/' + args.tag + '/'
real_builder = update_download.urllib.request.build_opener
receipts = []
for fail_before in range(3):
    route_name = update_download.MIRRORS[fail_before][0]
    directory = scratch / route_name; directory.mkdir(exist_ok=True)
    def build_opener(*handlers):
        opener = real_builder(*handlers)
        class Gated:
            def open(self, request, **kwargs):
                address = request.full_url
                if fail_before > 0 and address.startswith('https://github.com/') or fail_before > 1 and address.startswith('https://ghfast.top/'):
                    raise TimeoutError('Controlled unavailable route for fallback verification')
                return opener.open(request, **kwargs)
        return Gated()
    def fetch(name, limit):
        routes = []
        target = directory / name
        with patch.object(update_download.urllib.request, 'build_opener', side_effect=build_opener), target.open('wb') as stream:
            update_download.transfer(base + name, stream, limit, threading.Event(), route_notice=routes.append)
        assert routes == [name for name, _ in update_download.MIRRORS[:fail_before+1]], routes
        return target
    raw = fetch('update-manifest.json', 65536).read_bytes()
    sig = fetch('update-manifest.sig', 4096).read_bytes()
    pkcs1_15.new(RSA.import_key(base64.b64decode(PUBLIC_KEY))).verify(SHA256.new(raw), sig)
    manifest = json.loads(raw)
    assert manifest['repository'] == 'norskhelo/jmbatch' and manifest['tag'] == args.tag
    for platform, package in manifest['packages'].items():
        target = fetch(package['name'], package['size'])
        verify_file(target, package)
        receipts.append(dict(runtime='Python', platform=platform, route=route_name, size=target.stat().st_size, sha256=package['sha256'], signature_verified=True))
        print('VERIFIED Python', platform, route_name, flush=True)

# The original URL context retains the JDK HTTPS handler. Only selected earlier
# routes fail synthetically; the selected route performs real HTTPS requests.
java = r'''import app.jmbatch.android.*;import java.io.*;import java.net.*;import java.nio.file.*;import java.util.*;import java.util.concurrent.atomic.AtomicBoolean;
public class LiveUpdateMirrors {
static int failBefore;static URL direct;
public static void main(String[] args)throws Exception {
direct=new URL("https://github.com/");
URL.setURLStreamHandlerFactory(protocol->protocol.equals("https")?new URLStreamHandler(){protected URLConnection openConnection(URL url)throws IOException {
 if(failBefore>0&&url.getHost().equals("github.com")||failBefore>1&&url.getHost().equals("ghfast.top"))throw new SocketTimeoutException("Controlled unavailable route");
 return new URL(direct,url.toExternalForm()).openConnection();
}}:null);
Path root=Paths.get(args[0]);String base=args[1];String[] names={"GitHub","GHFast","GH-Proxy"};
for(failBefore=0;failBefore<3;failBefore++){
 Path folder=root.resolve("java-"+names[failBefore]);Files.createDirectories(folder);
 for(String name:Arrays.asList("update-manifest.json","update-manifest.sig",args[2])){
  List<String> routes=new ArrayList<>();File file=folder.resolve(name).toFile();
  UpdateDownload.transfer(base+name,()->new FileOutputStream(file),name.equals(args[2])?Long.parseLong(args[3]):65536,new AtomicBoolean(),(route,n)->{if(n==0)routes.add(route);});
  if(!routes.equals(Arrays.asList(names).subList(0,failBefore+1)))throw new AssertionError(routes);
 }
 UpdateCrypto.verify(Files.readAllBytes(folder.resolve("update-manifest.json")),Files.readAllBytes(folder.resolve("update-manifest.sig")));
 UpdateCrypto.verifyFile(folder.resolve(args[2]).toFile(),Long.parseLong(args[3]),args[4]);
 System.out.println("VERIFIED Java Android "+names[failBefore]);
}
}}
'''
program = scratch / 'LiveUpdateMirrors.java'; program.write_text(java, encoding='utf-8')
src = ROOT / 'work/jmbatch-android/app/src/main/java/app/jmbatch/android'
jdk = next((ROOT / 'work/android-tools').glob('jdk-*'))
subprocess.run([str(jdk/'bin/javac.exe'), '-encoding', 'UTF-8', '-d', str(scratch), *[str(src/(name+'.java')) for name in ('UpdateDownload','UpdateCrypto','UpdateTrust')], str(program)], check=True)
apk = manifest['packages']['android']
subprocess.run([str(jdk/'bin/java.exe'), '-cp', str(scratch), 'LiveUpdateMirrors', str(scratch), base, apk['name'], str(apk['size']), apk['sha256']], check=True)
for name, _ in update_download.MIRRORS:
    receipts.append(dict(runtime='Java', platform='android', route=name, signature_verified=True, sha256=apk['sha256']))
(report/'verification.json').write_text(json.dumps(dict(ok=True, tag=args.tag, checks=receipts, earlier_route_failures_simulated=True, selected_route_real_https=True, installer_launched=False), indent=2)+'\n', encoding='utf-8')
print('All production transports verified against signed public assets; no installation', flush=True)
