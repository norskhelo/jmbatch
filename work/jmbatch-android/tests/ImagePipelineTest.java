import app.jmbatch.android.ImagePipeline;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public class ImagePipelineTest {
    static int checks;
    static void check(boolean v){checks++;if(!v)throw new AssertionError("pipeline check "+checks);}
    public static void main(String[] args)throws Exception {
        Path root=Path.of(args[0]);Files.createDirectories(root);
        List<Integer> pages=new ArrayList<>();for(int i=0;i<100;i++)pages.add(i);
        AtomicInteger staged=new AtomicInteger(),peak=new AtomicInteger(),processing=new AtomicInteger(),processPeak=new AtomicInteger();
        CountDownLatch firstPair=new CountDownLatch(2);
        Set<Integer> done=ConcurrentHashMap.newKeySet();AtomicInteger cleaned=new AtomicInteger();
        List<ImagePipeline.Failure<Integer>> failures=ImagePipeline.run(pages,8,2,p->{
            peak.accumulateAndGet(staged.incrementAndGet(),Math::max);Files.write(root.resolve(p+".raw"),new byte[]{p.byteValue()});
        },p->{
            processPeak.accumulateAndGet(processing.incrementAndGet(),Math::max);
            try{
                firstPair.countDown();if(!firstPair.await(2,TimeUnit.SECONDS))throw new IOException("processing serialized");
                if(p==13)throw new IOException("synthetic corrupt input");
                Files.move(root.resolve(p+".raw"),root.resolve(p+".jpg"));done.add(p);
            }finally{processing.decrementAndGet();}
        },p->{Files.deleteIfExists(root.resolve(p+".raw"));staged.decrementAndGet();cleaned.incrementAndGet();},()->{},()->{},5);
        check(failures.size()==1&&failures.get(0).page==13);check(done.size()==99);check(peak.get()<=10);check(staged.get()==0&&cleaned.get()==100);check(processPeak.get()==2);
        for(int p:done)check(Files.readAllBytes(root.resolve(p+".jpg"))[0]==(byte)p);
        // A new run only schedules missing pages; valid committed files are retained after a failed page.
        List<Integer> missing=new ArrayList<>();for(int p:pages)if(!Files.exists(root.resolve(p+".jpg")))missing.add(p);
        AtomicInteger requests=new AtomicInteger();
        check(ImagePipeline.run(missing,16,4,p->{requests.incrementAndGet();Files.write(root.resolve(p+".raw"),new byte[]{p.byteValue()});},
            p->Files.move(root.resolve(p+".raw"),root.resolve(p+".jpg")),p->Files.deleteIfExists(root.resolve(p+".raw")),()->{},()->{},5).isEmpty());
        check(requests.get()==1);
        // Cancel while both fetching and processing own files; wait for all owners before cleanup/return.
        AtomicBoolean cancel=new AtomicBoolean();AtomicReference<Throwable> result=new AtomicReference<>();
        CountDownLatch processingStarted=new CountDownLatch(1);AtomicInteger live=new AtomicInteger();Set<Integer> raw=ConcurrentHashMap.newKeySet();
        Thread runner=new Thread(()->{try{
            ImagePipeline.run(pages,4,2,p->{live.incrementAndGet();try{raw.add(p);Thread.sleep(10);}finally{live.decrementAndGet();}},
                p->{live.incrementAndGet();try{processingStarted.countDown();Thread.sleep(10000);}finally{live.decrementAndGet();}},
                raw::remove,()->{if(cancel.get())throw new IOException("cancel");},()->cancel.set(true),1);
            result.set(new AssertionError("not cancelled"));
        }catch(IOException expected){}catch(Throwable e){result.set(e);}});
        runner.start();check(processingStarted.await(2,TimeUnit.SECONDS));cancel.set(true);runner.join(3000);
        check(!runner.isAlive()&&result.get()==null);check(live.get()==0&&raw.isEmpty());
        // Local fetch errors do not generate processed pages; each failed input is reported once.
        AtomicInteger output=new AtomicInteger();
        failures=ImagePipeline.run(pages,16,4,p->{throw new FileNotFoundException("disk");},p->output.incrementAndGet(),p->{},()->{},()->{},1);
        check(failures.size()==100&&output.get()==0);
        check(ImagePipeline.run(Collections.emptyList(),16,4,p->{throw new AssertionError();},p->{},p->{},()->{},()->{},1).isEmpty());
        System.out.println("ImagePipelineTest: "+checks+" checks passed");
    }
}
