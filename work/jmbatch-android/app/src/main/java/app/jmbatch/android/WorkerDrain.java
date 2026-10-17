package app.jmbatch.android;
import java.util.concurrent.*;

/** Retain task ownership while a timed-out child still has access to its files. */
public final class WorkerDrain {
    public static void await(ExecutorService pool){
        boolean interrupted=Thread.interrupted();
        try{
            while(!pool.isTerminated()){
                try{pool.awaitTermination(1,TimeUnit.SECONDS);}catch(InterruptedException e){interrupted=true;}
            }
        }finally{if(interrupted)Thread.currentThread().interrupt();}
    }
    private WorkerDrain(){}
}
