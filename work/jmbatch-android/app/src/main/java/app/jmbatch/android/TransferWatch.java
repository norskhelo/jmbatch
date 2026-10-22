package app.jmbatch.android;

import java.net.SocketTimeoutException;

/** Request-local slow-read recovery; local writes and image processing do not count. */
final class TransferWatch {
    private final long minimumBytesPerSecond, windowMillis;
    private long readMillis, bytes;
    TransferWatch(long minimumBytesPerSecond, long windowMillis) {
        this.minimumBytesPerSecond = minimumBytesPerSecond;
        this.windowMillis = Math.max(15000, windowMillis);
    }
    void read(long elapsedMillis, int count) throws SocketTimeoutException {
        readMillis += Math.max(0, elapsedMillis); bytes += Math.max(0, count);
        if (minimumBytesPerSecond <= 0 || readMillis < windowMillis) return;
        if (bytes * 1000.0 / readMillis < minimumBytesPerSecond)
            throw new SocketTimeoutException("图片连接持续低速，尝试其他地址或线路");
        readMillis = bytes = 0;
    }
}
