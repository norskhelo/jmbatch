package app.jmbatch.android;

import java.util.*;

/** UI-owned priority queue. A running job stays reserved until its UI delivery. */
public final class ReaderRequests {
    public static final class Job {
        public final int generation,index,width,height;
        public final String key;
        public Job(int generation,int index,int width,int height){
            this.generation=generation;this.index=index;this.width=width;this.height=height;
            key=generation+":"+index+":"+width+":"+height;
        }
    }
    private final LinkedHashMap<String,Job> queued=new LinkedHashMap<>();
    private Job active;
    public void replace(List<Job> jobs){queued.clear();for(Job job:jobs)offer(job);}
    public void offer(Job job){if((active==null||!active.key.equals(job.key))&&queued.size()<8)queued.put(job.key,job);}
    public Job take(){
        if(active!=null||queued.isEmpty())return null;
        Iterator<Job> iterator=queued.values().iterator();active=iterator.next();iterator.remove();return active;
    }
    public void complete(Job job){if(active==job)active=null;}
    public void clear(){queued.clear();}
    public int waiting(){return queued.size();}
}
