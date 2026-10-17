package app.jmbatch.android;

import java.io.*;
import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Synthetic blocked HTTPS requests exercise the real transport, pipeline and task slot. */
public final class JmApiCancellationTest {
    static int checks;
    static volatile Scenario scenario;
    static void check(boolean value, String message) {
        checks++; if (!value) throw new AssertionError(message);
    }
    static void await(CountDownLatch latch) throws IOException {
        // Model a platform socket operation that does not respond to thread interruption.
        boolean interrupted = false;
        long end = System.nanoTime() + TimeUnit.SECONDS.toNanos(8);
        try {
            while (true) {
                try {
                    if (!latch.await(Math.max(1, end-System.nanoTime()), TimeUnit.NANOSECONDS))
                        throw new IOException("fixture timed out");
                    return;
                } catch (InterruptedException error) { interrupted = true; }
            }
        } finally { if (interrupted) Thread.currentThread().interrupt(); }
    }
    static final class Scenario {
        final boolean body;
        final CountDownLatch entered = new CountDownLatch(16), closing = new CountDownLatch(16);
        final CountDownLatch release = new CountDownLatch(1);
        final AtomicInteger requests = new AtomicInteger(), disconnects = new AtomicInteger();
        Scenario(boolean body) { this.body = body; }
    }
    static final class Connection extends HttpURLConnection {
        final Scenario state = scenario;
        final CountDownLatch closed = new CountDownLatch(1);
        Connection(URL url) { super(url); }
        public void connect() {}
        public boolean usingProxy() { return false; }
        public void disconnect() {
            state.disconnects.incrementAndGet(); state.closing.countDown();
            try { await(state.release); } catch (IOException error) { throw new IllegalStateException(error); }
            finally { closed.countDown(); }
        }
        void block() throws IOException {
            state.entered.countDown(); await(closed); throw new IOException("connection cancelled");
        }
        public int getResponseCode() throws IOException {
            state.requests.incrementAndGet(); if (!state.body) block(); return 200;
        }
        public Map<String,List<String>> getHeaderFields() { return Collections.emptyMap(); }
        public String getContentEncoding() { return null; }
        public InputStream getInputStream() {
            return new InputStream() {
                public int read() throws IOException { block(); return -1; }
                public int read(byte[] bytes, int offset, int length) throws IOException { return read(); }
            };
        }
    }
    static void cancellation(Path root, boolean body) throws Exception {
        Files.createDirectories(root);
        Path saved = root.resolve("complete.jpg"); byte[] original = {1,2,3,4}; Files.write(saved, original);
        Scenario state = scenario = new Scenario(body);
        JmApi.Control control = new JmApi.Control();
        JmApi api = new JmApi(new Store.Settings(), "", control);
        List<Integer> pages = new ArrayList<>(); for (int i=0;i<7000;i++) pages.add(i);
        AtomicReference<Throwable> failure = new AtomicReference<>();
        AtomicInteger processed = new AtomicInteger();
        Set<Integer> raw = ConcurrentHashMap.newKeySet();
        DownloadPool<String, DownloadPool.Job> pool = new DownloadPool<>();
        DownloadPool.Job job = new DownloadPool.Job() {
            public void cancel(String reason) { control.cancel(reason); }
            public void run() {
                try {
                    ImagePipeline.run(pages,16,4,p->{
                        raw.add(p); api.image("123456",p+".jpg",root.resolve(p+".raw").toFile(),0);
                    },p->processed.incrementAndGet(),p->{Files.deleteIfExists(root.resolve(p+".raw"));raw.remove(p);},
                        control::check,()->{if(control.stop.isEmpty())control.cancel("ABORT");},1);
                    failure.set(new AssertionError("cancelled pipeline returned success"));
                } catch (IOException expected) {
                    if (!"CANCEL".equals(expected.getMessage())) failure.set(expected);
                } catch (Throwable error) { failure.set(error); }
            }
        };
        Thread caller = new Thread(()->job.cancel("CANCEL"),"simulated-main");
        long begin = 0;
        try {
            check(pool.start("task",job,1),"task start");
            check(state.entered.await(4,TimeUnit.SECONDS),"16 requests must be in flight");
            begin=System.nanoTime(); caller.start(); caller.join(1000);
            check(!caller.isAlive(),"cancel blocked its caller on a slow disconnect");
            check(state.closing.await(1,TimeUnit.SECONDS),"one slow disconnect delayed the other requests");
            for (int i=0;i<10;i++) job.cancel("CANCEL");
            check(state.disconnects.get()==16,"repeated cancellation duplicated disconnects");
            check(pool.reap().isEmpty()&&pool.size()==1,"slot released before old file owners stopped");
            check(!pool.start("task",job,1),"same task restarted while stopping");
            check(processed.get()==0&&state.requests.get()==16,"pending pages were processed or requested");
        } finally {
            state.release.countDown(); caller.join(3000);
            long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);
            while(pool.size()>0&&System.nanoTime()<end){pool.reap();Thread.sleep(10);}
        }
        check(pool.size()==0&&failure.get()==null,"pipeline did not stop cleanly: "+failure.get());
        check(raw.isEmpty(),"temporary inputs remain owned");
        check(state.disconnects.get()==16&&state.requests.get()==16,"transport retried or disconnected twice");
        check(Arrays.equals(Files.readAllBytes(saved),original),"complete cache was modified");
        try(java.util.stream.Stream<Path> files=Files.list(root)) { check(files.count()==1,"partial files not removed"); }
        System.out.printf(Locale.ROOT,"7000 pages / 16 blocked %s requests: stopped in %.3f s%n",body?"body":"header",(System.nanoTime()-begin)/1e9);
        // A cancellation preceding registration must never start another network request.
        try { api.image("123456","late.jpg",root.resolve("late.raw").toFile(),0); throw new AssertionError("late request"); }
        catch(IOException expected) { check(state.requests.get()==16,"request started after cancellation"); }
    }
    public static void main(String[] args) throws Exception {
        URL.setURLStreamHandlerFactory(protocol->new URLStreamHandler(){
            protected URLConnection openConnection(URL url){return new Connection(url);}
        });
        Path root=Path.of(args[0]);
        cancellation(root.resolve("headers"),false); cancellation(root.resolve("body"),true);
        System.out.println("JmApiCancellationTest: "+checks+" checks passed");
    }
}
