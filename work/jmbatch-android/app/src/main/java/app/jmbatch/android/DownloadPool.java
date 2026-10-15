package app.jmbatch.android;

import java.util.*;

/** Keeps a task's slot until its thread has actually exited, including cancellation. */
public final class DownloadPool<K, J extends DownloadPool.Job> {
    public interface Job extends Runnable { void cancel(String reason); }
    private final Map<K, Entry<J>> entries = new LinkedHashMap<>();
    private static final class Entry<J extends Job> {
        final J job;
        final Thread thread;
        Entry(J job) { this.job=job; thread=new Thread(job, "jm-download"); }
    }
    public synchronized boolean start(K key, J job, int limit) {
        if (limit < 1 || limit > 4) throw new IllegalArgumentException("同时下载任务数应为 1–4");
        if (entries.containsKey(key) || entries.size() >= limit) return false;
        Entry<J> entry=new Entry<>(job);
        entries.put(key,entry);
        try { entry.thread.start(); }
        catch (RuntimeException | Error error) { entries.remove(key); throw error; }
        return true;
    }
    public synchronized List<K> reap() {
        List<K> finished=new ArrayList<>();
        Iterator<Map.Entry<K,Entry<J>>> iterator=entries.entrySet().iterator();
        while(iterator.hasNext()) {
            Map.Entry<K,Entry<J>> entry=iterator.next();
            if(!entry.getValue().thread.isAlive()) { finished.add(entry.getKey()); iterator.remove(); }
        }
        return finished;
    }
    public synchronized int size() { return entries.size(); }
    public synchronized J get(K key) { Entry<J> entry=entries.get(key); return entry==null?null:entry.job; }
    public synchronized List<J> snapshot() {
        List<J> jobs=new ArrayList<>();
        for(Entry<J> entry:entries.values())jobs.add(entry.job);
        return jobs;
    }
    public void cancelAll(String reason) { for(J job:snapshot())job.cancel(reason); }
}
