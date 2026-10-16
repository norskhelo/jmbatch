package app.jmbatch.android;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

/** Bounded raw-file pipeline. A slot covers fetching, queued and processing pages. */
public final class ImagePipeline {
    public interface Action<T> { void run(T page) throws Exception; }
    public interface Check { void run() throws Exception; }
    public static final class Failure<T> {
        public final T page; public final Exception error;
        Failure(T page, Exception error) { this.page = page; this.error = error; }
    }
    public static final class UnstoppedWorkers extends IOException {
        UnstoppedWorkers() { super("旧图片线程未能及时退出；已停止该任务以避免重复写入。请重启应用后重试。"); }
    }
    public static <T> List<Failure<T>> run(List<T> pages, int networkWorkers, int imageWorkers,
            Action<T> fetch, Action<T> process, Action<T> cleanup, Check check, Runnable abort, int timeout) throws Exception {
        if (networkWorkers < 1 || networkWorkers > 16 || imageWorkers < 1 || imageWorkers > 4) throw new IllegalArgumentException();
        if (pages.isEmpty()) return Collections.emptyList();
        int networks = Math.min(networkWorkers, pages.size()), images = Math.min(imageWorkers, pages.size());
        Semaphore slots = new Semaphore(networks + images);
        BlockingQueue<T> ready = new ArrayBlockingQueue<>(networks + images);
        AtomicInteger next = new AtomicInteger(), producers = new AtomicInteger(networks);
        List<Failure<T>> failures = Collections.synchronizedList(new ArrayList<>());
        ExecutorService pool = Executors.newFixedThreadPool(networks + images);
        CompletionService<Void> completion = new ExecutorCompletionService<>(pool);
        boolean complete = false;
        try {
            for (int i = 0; i < networks; i++) completion.submit(() -> {
                try {
                    while (true) {
                        check.run(); slots.acquire();
                        int index = next.getAndIncrement();
                        if (index >= pages.size()) { slots.release(); return null; }
                        T page = pages.get(index); boolean handedOff = false;
                        try {
                            check.run(); fetch.run(page); check.run(); ready.put(page); handedOff = true;
                        } catch (Exception error) { check.run(); failures.add(new Failure<>(page, error)); }
                        finally { if (!handedOff) { try { cleanup.run(page); } finally { slots.release(); } } }
                    }
                } finally { producers.decrementAndGet(); }
            });
            for (int i = 0; i < images; i++) completion.submit(() -> {
                while (producers.get() > 0 || !ready.isEmpty()) {
                    check.run(); T page = ready.poll(100, TimeUnit.MILLISECONDS); if (page == null) continue;
                    try { check.run(); process.run(page); }
                    catch (Exception error) { check.run(); failures.add(new Failure<>(page, error)); }
                    finally { try { cleanup.run(page); } finally { slots.release(); } }
                }
                return null;
            });
            int finished = 0;
            while (finished < networks + images) {
                check.run(); Future<Void> done = completion.poll(100, TimeUnit.MILLISECONDS);
                if (done != null) { done.get(); finished++; }
            }
            complete = true;
        } catch (ExecutionException error) {
            Throwable cause = error.getCause();
            if (cause instanceof Exception) throw (Exception) cause;
            if (cause instanceof Error) throw (Error) cause;
            throw new IOException("图片流水线异常", cause);
        } finally {
            if (!complete) abort.run();
            pool.shutdownNow();
            // No cleanup/retry may touch a raw file still owned by an old worker.
            boolean interrupted = Thread.interrupted(), stopped = false;
            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(timeout + 10L);
            try {
                while (!stopped && System.nanoTime() < deadline) {
                    try { stopped = pool.awaitTermination(Math.max(1, deadline - System.nanoTime()), TimeUnit.NANOSECONDS); }
                    catch (InterruptedException again) { interrupted = true; }
                }
            }
            finally { if (interrupted) Thread.currentThread().interrupt(); }
            if (!stopped) throw new UnstoppedWorkers();
            for (T page : ready) cleanup.run(page);
        }
        check.run(); return new ArrayList<>(failures);
    }
    private ImagePipeline() {}
}
