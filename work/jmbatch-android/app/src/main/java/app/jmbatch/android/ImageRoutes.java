package app.jmbatch.android;

import java.util.*;

/** Session-local CDN health; a probe is a normal page request, never a duplicate. */
public final class ImageRoutes {
    public interface Clock { long now(); }
    private static final class Health {
        double rate; long until; int failures, samples;
    }
    private final List<String> hosts;
    private final Map<String, Health> health = new LinkedHashMap<>();
    private final Clock clock;
    private int requests, probeIndex;
    private boolean probing;
    private long nextProbe;
    public ImageRoutes(List<String> hosts, Clock clock) {
        this.hosts = new ArrayList<>(new LinkedHashSet<>(hosts)); this.clock = clock;
        if (this.hosts.isEmpty()) throw new IllegalArgumentException();
        for (String host : this.hosts) health.put(host, new Health());
    }
    public synchronized Plan plan(int recoveryRound) {
        long now = clock.now(); List<String> order = new ArrayList<>();
        for (String host : hosts) if (health.get(host).until <= now) order.add(host);
        if (order.isEmpty()) order.add(Collections.min(hosts, Comparator.comparingLong(h -> health.get(h).until)));
        order.sort((a,b) -> Double.compare(health.get(b).rate, health.get(a).rate));
        boolean probe = false; requests++;
        if (recoveryRound > 0) Collections.rotate(order, -recoveryRound);
        else if (!probing && requests % 8 == 0 && now >= nextProbe && order.size() > 1) {
            String primary = order.get(0);
            for (int i = 0; i < hosts.size(); i++) {
                String candidate = hosts.get(probeIndex); probeIndex = (probeIndex + 1) % hosts.size();
                if (!candidate.equals(primary) && order.contains(candidate)) {
                    order.remove(candidate); order.add(0, candidate); probe = probing = true; break;
                }
            }
        }
        return new Plan(order, probe);
    }
    public synchronized void success(String host, long bytes, long elapsedMillis) {
        Health h = health.get(host); if (h == null) return;
        double rate = Math.max(1, bytes) * 1000.0 / Math.max(1, elapsedMillis);
        h.rate = h.samples++ == 0 ? rate : h.rate * .5 + rate * .5;
        h.failures = 0; h.until = 0;
    }
    public synchronized void failure(String host, Exception error) {
        String kind = NetworkRoutes.kind(error);
        NetworkRoutes.HttpFailure http = NetworkRoutes.httpFailure(error);
        if (kind.equals("other") || http != null && http.code < 500) return;
        Health h = health.get(host); if (h == null) return;
        h.until = clock.now() + Math.min(120000L, 15000L << Math.min(3, h.failures++));
        h.rate = 0; h.samples = 0;
    }
    public final class Plan implements AutoCloseable {
        public final List<String> hosts;
        private boolean probe;
        private Plan(List<String> hosts, boolean probe) { this.hosts = Collections.unmodifiableList(hosts); this.probe = probe; }
        public void close() {
            synchronized (ImageRoutes.this) {
                if (probe) { probing = false; nextProbe = clock.now() + 15000; probe = false; }
            }
        }
    }
}
