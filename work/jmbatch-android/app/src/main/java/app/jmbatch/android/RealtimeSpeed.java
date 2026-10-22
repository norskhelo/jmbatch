package app.jmbatch.android;

/** Completed useful bytes in the latest refresh interval; never sums pipeline stages. */
final class RealtimeSpeed {
    private long time, bytes, speed;
    void reset(long now, long completed) { time = now; bytes = completed; speed = 0; }
    long sample(long now, long completed) {
        long elapsed = now - time;
        if (elapsed >= 1000) {
            speed = Math.max(0, completed - bytes) * 1000 / elapsed;
            time = now; bytes = completed;
        }
        return speed;
    }
}
