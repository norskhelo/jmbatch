package app.jmbatch.android;

import java.util.*;

/** Reconcile all cached pages before scheduling any network work. */
public final class ResumeCache {
    public interface Check { void run() throws Exception; }
    public interface Size<T> { long validatedBytes(T job) throws Exception; }
    public interface Progress { void scanned(int checked, int total, int cached) throws Exception; }
    public static final class Result<T> {
        public final List<T> pending = new ArrayList<>();
        public int cached;
        public long imageBytes;
    }
    public static <T> Result<T> scan(List<T> jobs, Check check, Size<T> size, Progress progress) throws Exception {
        Result<T> result = new Result<>();
        int checked = 0;
        for (T job : jobs) {
            check.run();
            long bytes = size.validatedBytes(job);
            if (bytes >= 0) { result.cached++; result.imageBytes += bytes; }
            else result.pending.add(job);
            progress.scanned(++checked, jobs.size(), result.cached);
        }
        check.run();
        return result;
    }
}
