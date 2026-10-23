package app.jmbatch.android;

import java.io.IOException;
import java.util.function.IntSupplier;

/** One token bucket shared by all image transfers in a service. */
final class DownloadRate {
    private final IntSupplier limit;
    private double tokens;private long previous=System.nanoTime();private int lastLimit;
    DownloadRate(IntSupplier limit){this.limit=limit;}
    void acquire(int bytes,JmApi.Control control)throws IOException{
        int remaining=bytes;
        while(remaining>0){control.check();long wait;
            synchronized(this){int kb=limit.getAsInt();long now=System.nanoTime();if(kb<=0){tokens=0;previous=now;lastLimit=0;return;}
                double rate=kb*1024.0,capacity=Math.max(1024,rate*.1);
                if(lastLimit!=kb){tokens=0;previous=now;lastLimit=kb;}
                tokens=Math.min(capacity,tokens+(now-previous)/1e9*rate);previous=now;
                int granted=(int)Math.min(remaining,tokens);remaining-=granted;tokens-=granted;
                if(remaining==0)return;wait=Math.max(1,Math.min(50,(long)Math.ceil(Math.min(remaining,capacity)/rate*1000)));
            }
            try{Thread.sleep(wait);}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("下载已中断",e);}
        }
    }
}
