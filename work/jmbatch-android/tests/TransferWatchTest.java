package app.jmbatch.android;

import java.net.SocketTimeoutException;

public final class TransferWatchTest {
    public static void main(String[] args)throws Exception {
        TransferWatch slow=new TransferWatch(1024,15000);
        for(int i=0;i<14;i++)slow.read(1000,1);
        try{slow.read(1000,1);throw new AssertionError("continuous trickle must recover");}catch(SocketTimeoutException expected){}
        TransferWatch healthy=new TransferWatch(1024,15000);
        for(int i=0;i<90;i++)healthy.read(1000,4096);
        TransferWatch disabled=new TransferWatch(0,15000);disabled.read(1000000,1);
        // The caller supplies only time inside input.read(), excluding output.write().
        TransferWatch localWrites=new TransferWatch(1024,15000);for(int i=0;i<200;i++)localWrites.read(1,4096);
        RealtimeSpeed rate=new RealtimeSpeed();rate.reset(1000,100000);
        if(rate.sample(2000,104096)!=4096||rate.sample(3000,104096)!=0||rate.sample(5000,108192)!=2048)throw new AssertionError("latest interval only");
        rate.reset(6000,108192);if(rate.sample(7000,108192)!=0)throw new AssertionError("cached bytes must not spike");
        System.out.println("TransferWatchTest: slow trickle, healthy, disabled, local writes and realtime speed passed");
    }
}
