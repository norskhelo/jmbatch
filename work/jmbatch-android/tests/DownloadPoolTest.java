import app.jmbatch.android.DownloadPool;
import java.util.*;
import java.util.concurrent.*;

public final class DownloadPoolTest {
    static int checks;
    static void check(boolean value){checks++;if(!value)throw new AssertionError("check "+checks);}
    static final class Work implements DownloadPool.Job {
        final CountDownLatch entered=new CountDownLatch(1), release=new CountDownLatch(1);
        volatile String stop="";
        public void run(){entered.countDown();try{if(!release.await(10,TimeUnit.SECONDS))throw new AssertionError("release timeout");}catch(InterruptedException e){throw new AssertionError(e);}}
        public void cancel(String reason){stop=reason;} // Closing real requests may take time.
    }
    static void reap(DownloadPool<String,Work> pool,int expected)throws Exception{
        long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(3);
        do{pool.reap();if(pool.size()==expected)return;Thread.sleep(5);}while(System.nanoTime()<end);
        throw new AssertionError("workers did not exit");
    }
    public static void main(String[] args)throws Exception{
        DownloadPool<String,Work> pool=new DownloadPool<>();
        Work a=new Work(), b=new Work(), c=new Work(), d=new Work();
        try{
            check(pool.start("a",a,2));check(pool.start("b",b,2));
            check(a.entered.await(3,TimeUnit.SECONDS)&&b.entered.await(3,TimeUnit.SECONDS));
            check(!pool.start("c",c,2));check(!pool.start("a",c,4));
            check(pool.size()==2);check(pool.snapshot().size()==2);
            pool.get("a").cancel("CANCEL");check(a.stop.equals("CANCEL"));check(b.stop.isEmpty());
            check(pool.reap().isEmpty());check(!pool.start("c",c,2));
            a.release.countDown();reap(pool,1);check(pool.get("a")==null);
            check(!pool.start("c",c,1)); // Reducing the limit leaves b alone.
            check(b.stop.isEmpty());check(pool.start("c",c,3));check(pool.start("d",d,3));
            check(c.entered.await(3,TimeUnit.SECONDS)&&d.entered.await(3,TimeUnit.SECONDS));
            pool.cancelAll("PAUSE");check(b.stop.equals("PAUSE")&&c.stop.equals("PAUSE")&&d.stop.equals("PAUSE"));
            check(pool.size()==3);check(!pool.start("a",new Work(),2));
            b.release.countDown();c.release.countDown();d.release.countDown();reap(pool,0);
            Work resumed=new Work();check(pool.start("a",resumed,1));check(resumed.entered.await(3,TimeUnit.SECONDS));
            resumed.release.countDown();reap(pool,0);check(pool.size()==0);
            for(int bad:new int[]{0,5}){try{pool.start("bad",new Work(),bad);throw new AssertionError("invalid limit");}catch(IllegalArgumentException expected){checks++;}}
        }finally{a.release.countDown();b.release.countDown();c.release.countDown();d.release.countDown();}
        System.out.println("Download pool checks: "+checks);
    }
}
