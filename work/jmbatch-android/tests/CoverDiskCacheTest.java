import app.jmbatch.android.CoverDiskCache;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

public final class CoverDiskCacheTest {
    static int checks;
    static void check(boolean value){checks++;if(!value)throw new AssertionError("Cache check "+checks);}
    public static void main(String[] args)throws Exception {
        File root=new File(args[0]);root.mkdirs();File cacheDir=new File(root,"covers");
        CoverDiskCache cache=new CoverDiskCache(cacheDir);
        Map<String,String> versions=new ConcurrentHashMap<>();versions.put("comic","1");versions.put("first","a");
        CoverDiskCache.Stamps stamps=uri->{String value=versions.get(uri);if(value==null)throw new FileNotFoundException(uri);return value;};
        AtomicInteger reads=new AtomicInteger();
        CoverDiskCache.Loader loader=()->{reads.incrementAndGet();return new CoverDiskCache.Value(new byte[]{1,2,3},"first",stamps.get("first"));};
        check(Arrays.equals(cache.get("zip|comic","comic",stamps,loader),new byte[]{1,2,3}));
        for(int i=0;i<3;i++)check(new CoverDiskCache(cacheDir).get("zip|comic","comic",stamps,loader).length==3);
        check(reads.get()==1);
        versions.put("comic","2");cache.get("zip|comic","comic",stamps,loader);check(reads.get()==2);
        versions.put("first","b");cache.get("zip|comic","comic",stamps,loader);check(reads.get()==3);
        File cached=cacheDir.listFiles()[0];Files.write(cached.toPath(),new byte[]{0});
        cache.get("zip|comic","comic",stamps,loader);check(reads.get()==4);
        versions.remove("comic");try{cache.get("zip|comic","comic",stamps,loader);throw new AssertionError();}catch(FileNotFoundException expected){check(true);}
        versions.put("comic","3");
        cache.forget("zip|comic");check(cacheDir.listFiles().length==0);
        check(cache.get("zip|comic","comic",stamps,()->null)==null);check(cacheDir.listFiles().length==0);
        cache.get("zip|comic","comic",stamps,loader);check(reads.get()==5);
        File blocked=new File(root,"blocked");Files.write(blocked.toPath(),new byte[]{0});
        check(new CoverDiskCache(new File(blocked,"covers")).get("other","comic",stamps,loader).length==3);
        cache.forget("zip|comic");reads.set(0);
        ExecutorService pool=Executors.newFixedThreadPool(4);
        try{
            List<Future<byte[]>> results=new ArrayList<>();
            for(int i=0;i<8;i++)results.add(pool.submit(()->new CoverDiskCache(cacheDir).get("zip|comic","comic",stamps,loader)));
            for(Future<byte[]> result:results)check(result.get().length==3);
            check(reads.get()==1);
        }finally{pool.shutdownNow();}
        // A changed source during extraction must not commit a stale thumbnail.
        cache.forget("zip|comic");
        cache.get("zip|comic","comic",stamps,()->{versions.put("comic","4");return loader.load();});
        check(cacheDir.listFiles().length==0);
        // Disk budget removes only cache files, leaving unrelated contents alone.
        File keep=new File(cacheDir,"keep.txt");Files.write(keep.toPath(),new byte[]{7});
        for(int i=0;i<CoverDiskCache.MAX_ENTRIES;i++)Files.write(new File(cacheDir,String.format("%064x.cover",i)).toPath(),new byte[]{0});
        cache.get("zip|comic","comic",stamps,loader);
        check(cacheDir.listFiles((d,n)->n.endsWith(".cover")).length==CoverDiskCache.MAX_ENTRIES);
        check(keep.isFile());check(cacheDir.listFiles((d,n)->n.endsWith(".tmp")).length==0);
        System.out.println("Persistent cover cache: "+checks+" checks passed");
    }
}
