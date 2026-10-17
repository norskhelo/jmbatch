import app.jmbatch.android.FolderSave;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.*;

public class FolderSaveTest {
    static int checks;
    static void check(boolean value){checks++;if(!value)throw new AssertionError("check "+checks);}
    interface Run { void run() throws Exception; }
    static void fails(Run run)throws Exception{try{run.run();throw new AssertionError("Expected failure");}catch(IOException expected){check(true);}}
    static final FolderSave.Check CONTINUE=()->{};
    static final FolderSave.Progress QUIET=(p,d,t,b,z)->{};
    static class MemoryTarget implements FolderSave.Target {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();int mode;long readBytes;int syncs;
        MemoryTarget(int mode){this.mode=mode;}
        public OutputStream write()throws Exception{
            if(mode==4)throw new IOException("disk full");return bytes;
        }
        public void sync(OutputStream out)throws Exception{syncs++;if(mode==5)throw new IOException("sync failure");}
        public InputStream read(){
            byte[] data=bytes.toByteArray();
            if(mode==1)data[0]^=1;
            if(mode==2)data=Arrays.copyOf(data,data.length-1);
            if(mode==3)data=Arrays.copyOf(data,data.length+1);
            return new ByteArrayInputStream(data){public synchronized int read(byte[] b,int o,int n){int size=super.read(b,o,n);if(size>0)readBytes+=size;return size;}};
        }
    }
    public static void main(String[] args)throws Exception{
        Path root=Files.createDirectories(Path.of(args[0]));Path sources=Files.createDirectory(root.resolve("sources"));
        byte[] data=new byte[180001];new Random(42).nextBytes(data);
        File first=Files.write(sources.resolve("first.jpg"),data).toFile();
        File second=Files.write(sources.resolve("second.jpg"),new byte[]{7,8,9}).toFile();
        FolderSave.Entry entry=new FolderSave.Entry(first,"0002/00001.jpg",data.length);
        MemoryTarget memory=new MemoryTarget(0);List<String> events=new ArrayList<>();
        FolderSave.transfer(entry,memory,CONTINUE,(phase,done,total,bytes,size)->{
            check(bytes>=0&&bytes<=size&&done>=0&&done<=total);events.add(phase+":"+done);
        },0,1,0,data.length);
        check(Arrays.equals(data,memory.bytes.toByteArray()));check(memory.readBytes==data.length);check(memory.syncs==1);
        check(events.contains("save:0")&&events.get(events.size()-1).equals("saved_verify:1"));
        for(int mode=1;mode<=5;mode++){
            MemoryTarget bad=new MemoryTarget(mode);fails(()->FolderSave.transfer(entry,bad,CONTINUE,QUIET,0,1,0,data.length));
        }
        // Pause while the first image is still being written: original bytes must remain.
        AtomicInteger calls=new AtomicInteger();
        fails(()->FolderSave.transfer(entry,new MemoryTarget(0),()->{if(calls.incrementAndGet()==3)throw new IOException("PAUSE");},QUIET,0,1,0,data.length));
        check(Arrays.equals(Files.readAllBytes(first.toPath()),data));
        fails(()->new FolderSave.Entry(first,"../00001.jpg",data.length));
        fails(()->FolderSave.validate(Arrays.asList(entry,entry)));
        fails(()->FolderSave.validate(Arrays.asList(new FolderSave.Entry(first,"00001.jpg",data.length+1))));
        List<FolderSave.Entry> entries=Arrays.asList(entry,new FolderSave.Entry(second,"0009/00001.jpg",3));
        Path exports=Files.createDirectory(root.resolve("exports"));
        List<Integer> completed=new ArrayList<>();
        File result=FolderSave.publish(exports.toFile(),entries,"album",CONTINUE,(phase,done,total,bytes,size)->{
            if(phase.equals("saved_verify")&&bytes==(done==1?data.length:data.length+3))completed.add(done);
        });
        check(Arrays.equals(Files.readAllBytes(result.toPath().resolve(entry.path)),data));
        check(Files.readAllBytes(result.toPath().resolve("0009/00001.jpg"))[0]==7);
        check(first.exists()&&second.exists());check(completed.contains(1)&&completed.contains(2));
        fails(()->FolderSave.publish(exports.toFile(),entries,"album",CONTINUE,QUIET));
        check(Files.readAllBytes(result.toPath().resolve("0009/00001.jpg"))[0]==7);
        AtomicBoolean stop=new AtomicBoolean();
        fails(()->FolderSave.publish(exports.toFile(),entries,"paused",()->{if(stop.get())throw new IOException("PAUSE");},
            (phase,done,total,bytes,size)->{if(phase.equals("saved_verify")&&done==1)stop.set(true);}));
        try(java.util.stream.Stream<Path> files=Files.list(exports)){check(files.count()==1);}
        check(first.exists()&&second.exists());
        File retried=FolderSave.publish(exports.toFile(),entries,"retry",CONTINUE,QUIET);check(retried.isDirectory());
        // Flat single-chapter layout and cleanup progress are independent of original source paths.
        List<File> owned=new ArrayList<>();
        File flat=FolderSave.publish(exports.toFile(),Arrays.asList(new FolderSave.Entry(second,"00001.jpg",3)),"flat",CONTINUE,QUIET,owned::add);
        check(new File(flat,"00001.jpg").isFile());
        check(owned.size()==2);check(owned.get(0).getName().endsWith(".partial"));check(owned.get(1).equals(flat));
        owned.clear();
        fails(()->FolderSave.publish(exports.toFile(),Arrays.asList(new FolderSave.Entry(second,"00001.jpg",3)),"cancel-owned",CONTINUE,
            (phase,done,total,bytes,size)->{if(phase.equals("save"))throw new IOException("cancel");},owned::add));
        check(owned.size()==2);check(owned.get(1)==null);check(!owned.get(0).exists());
        fails(()->FolderSave.clean(sources.toFile(),exports.toFile(),CONTINUE,QUIET));check(first.exists());
        List<Integer> cleaned=new ArrayList<>();
        FolderSave.clean(sources.toFile(),root.toFile(),CONTINUE,(phase,done,total,bytes,size)->{if(total>0){check(total==2);cleaned.add(done);}});
        check(cleaned.equals(Arrays.asList(0,1,2)));check(!Files.exists(sources));check(result.isDirectory());
        FolderSave.clean(exports.toFile(),root.toFile(),CONTINUE,QUIET);check(!Files.exists(exports));
        System.out.println("FolderSaveTest: "+checks+" checks passed");
    }
}
