import app.jmbatch.android.ResumeCache;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;

public class ResumeCacheTest {
    static int checks;
    static void check(boolean value, String message) { checks++; if (!value) throw new AssertionError(message); }
    static long validSize(File file) throws IOException {
        if (!file.isFile()) return -1;
        try { return ImageIO.read(file) == null ? -1 : file.length(); }
        catch (IOException broken) { return -1; }
    }
    public static void main(String[] args) throws Exception {
        Path parent = Paths.get(args[0]); Files.createDirectories(parent);
        Path root = Files.createTempDirectory(parent, "scan-");
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        ImageIO.write(new BufferedImage(8, 8, BufferedImage.TYPE_INT_RGB), "jpg", bytes);
        byte[] jpeg = bytes.toByteArray();
        List<File> jobs = new ArrayList<>();
        for (int i = 1; i <= 7227; i++) {
            File file = root.resolve(String.format(Locale.ROOT, "%05d.jpg", i)).toFile();
            jobs.add(file);
            if (i <= 4321 || i == 6100) Files.write(file.toPath(), jpeg);
        }
        Files.write(jobs.get(1).toPath(), new byte[]{1, 2, 3});
        Files.write(root.resolve("04322.jpg.partial"), jpeg);
        int[] scanned = {0};
        ResumeCache.Result<File> result = ResumeCache.scan(jobs, () -> {}, ResumeCacheTest::validSize,
            (done, total, cached) -> { scanned[0] = done; if (total != 7227) throw new AssertionError("total"); });
        check(scanned[0] == 7227, "scan includes every chapter/page");
        check(result.cached == 4321, "valid pages restored including out-of-order page");
        check(result.imageBytes == (long)4321 * jpeg.length, "restored image bytes");
        check(result.pending.size() == 7227 - 4321, "only missing/broken pages scheduled");
        check(result.pending.get(0).equals(jobs.get(1)), "repair corrupt early page");
        check(!result.pending.contains(jobs.get(6099)), "keep later cached page");
        check(result.pending.contains(jobs.get(4321)), "partial image does not count as complete");
        int[] requestCount = {0};
        for (File job : result.pending) { Files.write(job.toPath(), jpeg); requestCount[0]++; }
        check(requestCount[0] == 2906, "only 2906 image requests after resume");
        ResumeCache.Result<File> complete = ResumeCache.scan(jobs, () -> {}, ResumeCacheTest::validSize, (d,t,c) -> {});
        check(complete.pending.isEmpty() && complete.cached == 7227, "second resume requires no image requests");
        check(complete.imageBytes == (long)7227 * jpeg.length, "no duplicate byte accounting");
        int[] validated = {0};
        try {
            ResumeCache.scan(jobs, () -> { if (validated[0] == 4) throw new IOException("PAUSE"); },
                file -> { validated[0]++; return validSize(file); }, (d,t,c) -> {});
            throw new AssertionError("pause ignored");
        } catch (IOException stopped) { check(stopped.getMessage().equals("PAUSE"), "pause propagated during scan"); }
        check(validated[0] == 4 && Files.size(jobs.get(0).toPath()) == jpeg.length, "pause leaves cache intact");
        System.out.println("ResumeCacheTest: " + checks + " checks passed (7227 pages)");
    }
}
