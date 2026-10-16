package app.jmbatch.android;

import java.io.IOException;

/** Process-wide reservations for full-resolution bitmaps, shared by all tasks. */
public final class ImageMemory {
    public interface Check { void run() throws Exception; }
    public static final ImageMemory SHARED = new ImageMemory(Runtime.getRuntime().maxMemory() * 3 / 5,
        Math.max(1, Math.min(4, Runtime.getRuntime().availableProcessors() / 2)));
    private final long budget;
    private final int parallelism;
    private long used;
    private int active;

    public ImageMemory(long budget, int parallelism) {
        if (budget < 1 || parallelism < 1) throw new IllegalArgumentException();
        this.budget = budget; this.parallelism = parallelism;
    }
    public int workers() { return parallelism; }
    public static long estimate(int width, int height, int copies) throws IOException {
        if (width <= 0 || height <= 0 || copies < 1 || copies > 2) throw new IOException("图片尺寸无效");
        long pixels = (long) width * height;
        // Include decoder/encoder scratch memory in addition to ARGB pixels.
        if (pixels > (Long.MAX_VALUE - 4L * 1024 * 1024) / (4L * copies)) throw new IOException("图片尺寸过大");
        return pixels * 4 * copies + 4L * 1024 * 1024;
    }
    public synchronized Lease acquire(long bytes, Check check) throws Exception {
        if (bytes <= 0 || bytes > budget) throw new IOException("单张图片尺寸过大，超出当前手机安全解码内存；未缩小图片或生成不完整文件");
        while (active >= parallelism || bytes > budget - used) { check.run(); wait(100); }
        check.run(); used += bytes; active++;
        return new Lease(bytes);
    }
    public final class Lease implements AutoCloseable {
        private long bytes;
        private Lease(long bytes) { this.bytes = bytes; }
        public void close() {
            synchronized (ImageMemory.this) {
                if (bytes == 0) return;
                used -= bytes; active--; bytes = 0; ImageMemory.this.notifyAll();
            }
        }
    }
}
