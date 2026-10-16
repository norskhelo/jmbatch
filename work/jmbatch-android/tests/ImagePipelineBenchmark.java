import app.jmbatch.android.ImagePipeline;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Synthetic scheduling comparison, NOT phone speed or a real image benchmark. */
public class ImagePipelineBenchmark {
    public static void main(String[] args)throws Exception {
        List<Integer> pages=new ArrayList<>();for(int i=0;i<48;i++)pages.add(i);
        Semaphore serial=new Semaphore(1);ExecutorService old=Executors.newFixedThreadPool(16);
        List<Future<?>> jobs=new ArrayList<>();long start=System.nanoTime();
        for(int page:pages)jobs.add(old.submit(()->{try{Thread.sleep(20);serial.acquire();try{Thread.sleep(100);}finally{serial.release();}}catch(Exception e){throw new RuntimeException(e);}}));
        for(Future<?> job:jobs)job.get();old.shutdown();double before=(System.nanoTime()-start)/1e9;
        AtomicInteger done=new AtomicInteger();start=System.nanoTime();
        if(!ImagePipeline.run(pages,16,4,p->Thread.sleep(20),p->{Thread.sleep(100);done.incrementAndGet();},p->{},()->{},()->{},5).isEmpty()||done.get()!=48)throw new AssertionError();
        double after=(System.nanoTime()-start)/1e9;
        System.out.printf(Locale.ROOT,"{\"synthetic\":true,\"pages\":48,\"network_ms\":20,\"processing_ms\":100,\"old_workers\":16,\"old_processing\":1,\"new_network_workers\":16,\"new_processing_workers\":4,\"old_seconds\":%.6f,\"new_seconds\":%.6f}%n",before,after);
    }
}
