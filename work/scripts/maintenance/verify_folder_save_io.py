"""Count actual new save-path I/O on synthetic files, without Android timing claims."""
from pathlib import Path
import hashlib
import json
import subprocess
from datetime import datetime

root = Path(__file__).resolve().parents[3]
run = root / 'work/tests' / ('folder-save-io-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
report = root / 'outputs/reports/folder-save-io'
run.mkdir(parents=True, exist_ok=False)
report.mkdir(parents=True, exist_ok=True)
source_path = root / 'work/jmbatch-android/app/src/main/java/app/jmbatch/android/FolderSave.java'
source = source_path.read_text(encoding='utf-8')
source = source.replace('new FileInputStream(', 'new MeterInputStream(').replace('new FileOutputStream(', 'new MeterOutputStream(')
assert source.count('((FileOutputStream)out).getFD().sync();') == 1
source = source.replace('((FileOutputStream)out).getFD().sync();', 'countedSync((FileOutputStream)out);')
source = source.replace('public final class FolderSave {', '''public final class FolderSave {
    public static long reads,writes,syncs,inputOpens,outputOpens;
    static final class MeterInputStream extends FileInputStream {
        MeterInputStream(File f)throws IOException{super(f);inputOpens++;}
        @Override public int read(byte[] b)throws IOException{int n=super.read(b);if(n>0)reads+=n;return n;}
    }
    static final class MeterOutputStream extends FileOutputStream {
        MeterOutputStream(File f)throws IOException{super(f);outputOpens++;}
        @Override public void write(byte[] b,int o,int n)throws IOException{super.write(b,o,n);writes+=n;}
    }
    static void countedSync(FileOutputStream out)throws IOException{out.getFD().sync();syncs++;}
''')
(run / 'FolderSave.java').write_text(source, encoding='utf-8')
counts = [len(json.loads(p.read_text(encoding='utf-8'))['data']['pages']) for p in sorted(
    (root / 'work/tests/chapter-metadata-live/output/.jmbatch-work').glob('*/chapters/*.json'))]
assert len(counts)==151 and sum(counts)==7190
probe = r'''
import app.jmbatch.android.FolderSave;
import java.nio.file.*;
import java.util.*;
import java.io.*;
public class FolderIoProbe {
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]).toRealPath();Path cache=Files.createDirectory(root.resolve("synthetic-cache"));
        int[] counts={COUNTS};byte[] payload=new byte[4096];Random random=new Random(518074);
        List<FolderSave.Entry> entries=new ArrayList<>();
        for(int c=0;c<counts.length;c++){
            Path dir=Files.createDirectory(cache.resolve(String.format(Locale.ROOT,"%04d",c+1)));
            for(int p=1;p<=counts[c];p++){
                Path file=dir.resolve(String.format(Locale.ROOT,"%05d.jpg",p));random.nextBytes(payload);Files.write(file,payload);
                entries.add(new FolderSave.Entry(file.toFile(),String.format(Locale.ROOT,"%04d/%05d.jpg",c+1,p),payload.length));
            }
        }
        long total=entries.size()*4096L;int[] completed={0,0};
        long start=System.nanoTime();
        File output=FolderSave.publish(root.resolve("exports").toFile(),entries,"album",()->{},(phase,d,t,b,z)->{
            if(phase.equals("saved_verify"))completed[0]=Math.max(completed[0],d);
        });
        double seconds=(System.nanoTime()-start)/1e9;
        if(FolderSave.reads!=total*2||FolderSave.writes!=total||FolderSave.syncs!=entries.size()
                ||FolderSave.inputOpens!=entries.size()*2L||FolderSave.outputOpens!=entries.size()||completed[0]!=entries.size())
            throw new AssertionError("unexpected I/O or progress");
        for(FolderSave.Entry entry:entries)if(Files.mismatch(entry.source.toPath(),output.toPath().resolve(entry.path))!=-1)
            throw new AssertionError("different output");
        start=System.nanoTime();FolderSave.clean(cache.toFile(),root.toFile(),()->{},(phase,d,t,b,z)->completed[1]=Math.max(completed[1],d));
        double cleanup=(System.nanoTime()-start)/1e9;
        if(completed[1]!=entries.size())throw new AssertionError("incomplete cleanup progress");
        System.out.printf(Locale.ROOT,"{\"pages\":%d,\"chapters\":%d,\"payload_bytes\":%d,\"read_bytes\":%d,\"write_bytes\":%d,\"fsyncs\":%d,\"input_opens\":%d,\"output_opens\":%d,\"publish_seconds\":%.6f,\"cleanup_seconds\":%.6f,\"all_files_equal\":true,\"save_and_cleanup_progress_complete\":true}%n",
            entries.size(),counts.length,total,FolderSave.reads,FolderSave.writes,FolderSave.syncs,FolderSave.inputOpens,FolderSave.outputOpens,seconds,cleanup);
        FolderSave.clean(root.resolve("exports").toFile(),root.toFile(),()->{},(p,d,t,b,z)->{});
    }
}
'''.replace('COUNTS', ','.join(map(str, counts)))
(run / 'FolderIoProbe.java').write_text(probe, encoding='utf-8')
jdk=root/'work/android-tools/jdk-17.0.20.1+1/bin'
subprocess.run([str(jdk/'javac.exe'),'-encoding','UTF-8','-d',str(run),str(run/'FolderSave.java'),str(run/'FolderIoProbe.java')],check=True,capture_output=True)
result=subprocess.run([str(jdk/'java.exe'),'-cp',str(run),'FolderIoProbe',str(run)],check=True,capture_output=True,text=True)
counters=json.loads(result.stdout)
receipt=dict(ok=True,scope='Windows JDK 17 host, 4096-byte synthetic payloads; NOT Android device timings',
             source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),run_directory=str(run),
             instrumentation='Production FolderSave, unchanged control flow, stream byte/open counters and actual fsync count only',
             result=counters,old_logical_io='4S read + 2S write',new_logical_io='2S read + 1S write',
             note='Logical byte reduction is not a wall-clock speedup or physical flash I/O estimate. No real image download.')
(report/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
