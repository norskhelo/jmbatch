import app.jmbatch.android.CacheCleanup;
import java.io.*;
import java.nio.file.*;

public class CacheCleanupTest {
    static int checks;
    static void check(boolean value){checks++;if(!value)throw new AssertionError("check "+checks);}
    static File put(File root,String name)throws Exception{
        File file=new File(root,name);file.getParentFile().mkdirs();Files.write(file.toPath(),new byte[]{1,2,3});return file;
    }
    public static void main(String[] args)throws Exception{
        File owner=new File(args[0],"work");owner.mkdirs();File cache=new File(owner,"task");
        File image=put(cache,"images/0001/00001.jpg"),metadata=put(cache,"chapters/1.meta"),marker=put(cache,"completed.json"),unknown=put(cache,"personal.txt");
        put(cache,"images/0001/00002.jpg.partial");put(cache,"images/0001/00003.jpg.download");put(cache,"export.partial.zip");put(cache,"album-stage/00001.jpg");
        CacheCleanup.Result result=CacheCleanup.clean(cache,owner,false,false,r->{});
        check(result.files==4);check(result.bytes==12);check(result.errors==0);
        check(image.isFile());check(metadata.isFile());check(marker.isFile());check(unknown.isFile());
        result=CacheCleanup.clean(cache,owner,true,true,r->{});
        check(result.files==1);check(result.bytes==3);check(image.isFile());check(!metadata.exists());
        result=CacheCleanup.clean(cache,owner,true,false,r->{});
        check(result.files==1);check(result.bytes==3);check(!image.exists());check(marker.exists());check(unknown.exists());
        check(result.message(true).contains("自动清理"));check(result.message(false).contains("释放"));
        result=CacheCleanup.clean(cache,owner,true,false,r->{});check(result.files==0);check(result.errors==0);
        File absent=new File(owner,"absent");check(CacheCleanup.clean(absent,owner,true,false,r->{}).files==0);check(!absent.exists());
        File outside=new File(args[0],"outside");File important=put(outside,"images/0001/keep.jpg");
        result=CacheCleanup.clean(outside,owner,true,false,r->{});check(result.errors>0);check(important.exists());
        File traversal=new File(owner,"../outside");check(CacheCleanup.clean(traversal,owner,true,false,r->{}).errors>0);check(important.exists());
        // A regular file at a directory path must fail without touching unrelated files.
        File invalid=put(owner,"invalid");check(CacheCleanup.clean(invalid,owner,true,false,r->{}).errors>0);check(invalid.isFile());
        final int[] progress={0};
        for(int i=0;i<205;i++)put(cache,"images/0001/"+i+".jpg");
        result=CacheCleanup.clean(cache,owner,true,false,r->progress[0]++);
        check(result.files==205);check(result.bytes==615);check(progress[0]>=3);check(important.exists());
        File links=new File(args[1]);
        result=CacheCleanup.clean(new File(links,"work/task"),new File(links,"work"),true,false,r->{});
        check(result.files==0);check(result.errors>=2);check(new File(links,"outside/keep.jpg").length()==8);
        File locked=put(cache,"images/0001/locked.jpg");
        try(FileInputStream held=new FileInputStream(locked)){
            result=CacheCleanup.clean(cache,owner,true,false,r->{});
            check(result.files==0);check(result.errors>0);check(locked.exists());check(result.message(true).contains("未能清理"));
        }
        result=CacheCleanup.clean(cache,owner,true,false,r->{});check(result.files==1);check(result.bytes==3);check(result.errors==0);
        // Explicit cancellation removes the whole task, including complete images,
        // metadata and its marker; conservative maintenance above stays unchanged.
        put(cache,"images/0001/00001.jpg");put(cache,"chapters/1.meta");
        result=CacheCleanup.discard(cache,owner,r->{});
        check(result.errors==0);check(result.files==4);check(!cache.exists());check(important.exists());
        check(CacheCleanup.discard(cache,owner,r->{}).errors==0);check(!cache.exists());
        result=CacheCleanup.discard(new File(links,"work/task"),new File(links,"work"),r->{});
        check(result.errors>0);check(new File(links,"outside/keep.jpg").length()==8);
        System.out.println("CacheCleanupTest: "+checks+" checks passed");
    }
}
