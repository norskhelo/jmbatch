import app.jmbatch.android.ImageMemory;
import java.io.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public class ImageMemoryTest {
    static int checks;
    static void check(boolean v){checks++;if(!v)throw new AssertionError("memory check "+checks);}
    public static void main(String[] args)throws Exception {
        check(ImageMemory.estimate(100,200,2)==160000+4L*1024*1024);
        try{ImageMemory.estimate(Integer.MAX_VALUE,Integer.MAX_VALUE,2);throw new AssertionError();}catch(IOException expected){checks++;}
        ImageMemory budget=new ImageMemory(100,4);
        try{budget.acquire(101,()->{});throw new AssertionError();}catch(IOException expected){checks++;}
        AtomicInteger entered=new AtomicInteger();CountDownLatch started=new CountDownLatch(1),enteredSecond=new CountDownLatch(1);
        AtomicReference<Throwable> error=new AtomicReference<>();
        ImageMemory.Lease first=budget.acquire(60,()->{});
        Thread second=new Thread(()->{started.countDown();try(ImageMemory.Lease lease=budget.acquire(60,()->{})){entered.incrementAndGet();enteredSecond.countDown();}catch(Throwable e){error.set(e);}});
        second.start();check(started.await(1,TimeUnit.SECONDS));check(!enteredSecond.await(100,TimeUnit.MILLISECONDS));
        first.close();first.close();check(enteredSecond.await(2,TimeUnit.SECONDS));second.join(2000);check(error.get()==null&&entered.get()==1);
        ImageMemory limited=new ImageMemory(1000,2);
        AtomicInteger active=new AtomicInteger(),peak=new AtomicInteger();ExecutorService pool=Executors.newFixedThreadPool(8);
        CountDownLatch pair=new CountDownLatch(2),release=new CountDownLatch(1);
        java.util.List<Future<?>> futures=new java.util.ArrayList<>();
        for(int i=0;i<8;i++)futures.add(pool.submit(()->{try(ImageMemory.Lease lease=limited.acquire(1,()->{})){
            peak.accumulateAndGet(active.incrementAndGet(),Math::max);pair.countDown();release.await();active.decrementAndGet();
        }catch(Exception e){throw new RuntimeException(e);}}));
        check(pair.await(2,TimeUnit.SECONDS));release.countDown();for(Future<?> f:futures)f.get();pool.shutdown();check(peak.get()==2);
        ImageMemory blocked=new ImageMemory(100,1);AtomicBoolean cancelled=new AtomicBoolean();
        try(ImageMemory.Lease held=blocked.acquire(100,()->{})){
            Thread waiter=new Thread(()->{try{blocked.acquire(1,()->{if(cancelled.get())throw new IOException("cancel");});error.set(new AssertionError("not cancelled"));}catch(IOException expected){}catch(Exception e){error.set(e);}});
            waiter.start();cancelled.set(true);waiter.join(2000);check(!waiter.isAlive()&&error.get()==null);
        }
        try(ImageMemory.Lease lease=blocked.acquire(100,()->{})){checks++;}
        System.out.println("ImageMemoryTest: "+checks+" checks passed");
    }
}
