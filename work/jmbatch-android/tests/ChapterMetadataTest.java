import app.jmbatch.android.ChapterMetadata;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public class ChapterMetadataTest {
    static int checks;
    static void check(boolean value){checks++;if(!value)throw new AssertionError("check "+checks);}
    static ChapterMetadata.Detail detail(String id)throws Exception{return new ChapterMetadata.Detail(Arrays.asList(id+".jpg"),220980);}
    public static void main(String[] args)throws Exception{
        File root=new File(args[0]);root.mkdirs();
        String scope=ChapterMetadata.scope("123456","","catalog");
        ChapterMetadata.Cache cache=new ChapterMetadata.Cache(new File(root,"metadata"),scope);
        List<String> ids=new ArrayList<>();for(int i=1;i<=24;i++)ids.add(Integer.toString(800000+i));
        AtomicInteger active=new AtomicInteger(),peak=new AtomicInteger(),calls=new AtomicInteger();
        CountDownLatch concurrent=new CountDownLatch(4);
        List<Integer> progress=new ArrayList<>();
        ChapterMetadata.Fetch fetch=id->{
            calls.incrementAndGet();int n=active.incrementAndGet();peak.accumulateAndGet(n,Math::max);
            try{
                concurrent.countDown();if(!concurrent.await(3,TimeUnit.SECONDS))throw new IOException("not concurrent");
                Thread.sleep(Integer.parseInt(id)%2==0?5:15);return detail(id);
            }finally{active.decrementAndGet();}
        };
        List<ChapterMetadata.Detail> result=ChapterMetadata.load(ids,cache,fetch,()->{},()->{},(done,total,cached)->progress.add(done),5);
        check(calls.get()==24);check(peak.get()==4);check(active.get()==0);check(progress.size()==25);
        for(int i=0;i<ids.size();i++)check(result.get(i).images.get(0).equals(ids.get(i)+".jpg"));
        ChapterMetadata.Fetch forbidden=id->{throw new AssertionError("cached metadata requested");};
        ChapterMetadata.load(ids,new ChapterMetadata.Cache(new File(root,"metadata"),scope),forbidden,()->{},()->{},(d,t,c)->{},5);
        check(calls.get()==24);
        long now=System.currentTimeMillis();
        cache.write("800001",detail("800001"),now-ChapterMetadata.TTL-1);
        Files.write(cache.path("800002").toPath(),new byte[]{1,2});
        Files.delete(cache.path("800003").toPath());
        Files.write(new File(root,"metadata/800003.part").toPath(),new byte[]{1,2});
        AtomicInteger reread=new AtomicInteger();
        ChapterMetadata.load(ids,cache,id->{reread.incrementAndGet();return detail(id);},()->{},()->{},(d,t,c)->{},5);
        check(reread.get()==3);
        check(new ChapterMetadata.Cache(new File(root,"metadata"),"changed").read("800001",now+1000)==null);
        check(!scope.equals(ChapterMetadata.scope("123456","auth=new","catalog")));
        check(!scope.equals(ChapterMetadata.scope("123456","","changed")));
        cache.write("800001",detail("800001"),now+60000);check(cache.read("800001",now)==null);
        cache.write("800001",detail("800001"),now);check(cache.read("800001",now+ChapterMetadata.TTL-1)!=null);
        check(cache.read("800001",now+ChapterMetadata.TTL)==null);
        try{cache.path("../escape");throw new AssertionError();}catch(IOException expected){check(true);}
        try{new ChapterMetadata.Detail(Arrays.asList("../escape.jpg"),220980);throw new AssertionError();}catch(IOException expected){check(true);}
        try{new ChapterMetadata.Detail(Collections.emptyList(),220980);throw new AssertionError();}catch(IOException expected){check(true);}
        Files.write(cache.path("800001").toPath(),new byte[ChapterMetadata.MAX_BYTES+1]);check(cache.read("800001",now)==null);
        // Cancellation occurs after the coordinator durably commits the first result.
        ChapterMetadata.Cache partial=new ChapterMetadata.Cache(new File(root,"partial"),scope);
        AtomicBoolean stop=new AtomicBoolean(),aborted=new AtomicBoolean();AtomicInteger stoppedWorkers=new AtomicInteger();
        try{
            ChapterMetadata.load(ids,partial,id->{
                stoppedWorkers.incrementAndGet();
                try{Thread.sleep(id.equals("800001")?5:2000);return detail(id);}finally{stoppedWorkers.decrementAndGet();}
            },()->{if(stop.get())throw new IOException("PAUSE");},()->aborted.set(true),(d,t,c)->{if(d==1)stop.set(true);},5);
            throw new AssertionError("pause expected");
        }catch(IOException expected){check(expected.getMessage().equals("PAUSE"));}
        check(aborted.get());check(stoppedWorkers.get()==0);check(partial.read("800001",System.currentTimeMillis())!=null);
        AtomicInteger resumed=new AtomicInteger();
        ChapterMetadata.load(ids,partial,id->{resumed.incrementAndGet();return detail(id);},()->{},()->{},(d,t,c)->{},5);
        check(resumed.get()==23);
        // A failed request must close all workers and retain already committed records.
        partial.invalidate("800024");aborted.set(false);
        try{
            ChapterMetadata.load(ids,partial,id->{throw new IOException("HTTP 429");},()->{},()->aborted.set(true),(d,t,c)->{},5);
            throw new AssertionError();
        }catch(IOException expected){check(expected.getMessage().equals("HTTP 429"));}
        check(aborted.get());check(partial.read("800001",System.currentTimeMillis())!=null);
        check(partial.read("800024",System.currentTimeMillis())==null);
        check(new String(Files.readAllBytes(partial.path("800001").toPath()),java.nio.charset.StandardCharsets.ISO_8859_1).indexOf("auth=")<0);
        ChapterMetadata.Cache limit=new ChapterMetadata.Cache(new File(root,"limit"),scope);
        limit.write("1",new ChapterMetadata.Detail(Collections.nCopies(20000,"1.jpg"),220980),System.currentTimeMillis());
        for(boolean cached:new boolean[]{false,true}){
            if(cached)limit.write("2",detail("2"),System.currentTimeMillis());
            try{ChapterMetadata.load(Arrays.asList("1","2"),limit,ChapterMetadataTest::detail,()->{},()->{},(d,t,c)->{},5);throw new AssertionError();}
            catch(IOException expected){check(expected.getMessage().contains("20000"));}
        }
        System.out.println("ChapterMetadataTest: "+checks+" checks passed");
    }
}
