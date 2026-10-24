package app.jmbatch.android;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.regex.*;
import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;

/** Pure Java protocol primitives, input validation and streaming PDF writer. */
public final class Core {
    public static final String VERSION = "0.6.17";
    public static final int ZIP_LAYOUT_VERSION = 3;
    public static final String APP_VERSION = "2.1.7";
    public static final String API_SECRET = "185Hcomic3PAPP7R";
    public static final String CONTENT_SECRET = "18comicAPPContent";
    public static final String DOMAIN_SECRET = "diosfjckwpqpdfjkvnqQjsik";
    private Core() {}

    public static List<String> parseIds(String input) {
        String normalized = input.trim().replaceAll("\\s*[-~～—–至]\\s*", "-");
        LinkedHashSet<String> ids = new LinkedHashSet<>();
        Pattern pattern = Pattern.compile("(?:JM)?([0-9]{3,10})(?:-(?:JM)?([0-9]{3,10}))?", Pattern.CASE_INSENSITIVE);
        for (String token : normalized.split("[\\s,，;；、]+")) {
            if (token.isEmpty()) continue;
            Matcher m = pattern.matcher(token);
            if (!m.matches()) throw new IllegalArgumentException("无法识别编号：" + token + "。示例：123456 或 123460-123465");
            long first = Long.parseLong(m.group(1)), last = m.group(2) == null ? first : Long.parseLong(m.group(2));
            if (first <= 0 || last < first) throw new IllegalArgumentException("编号区间无效：" + token);
            if (last - first >= 2000) throw new IllegalArgumentException("单次最多添加 2000 个编号");
            for (long n = first; n <= last; n++) {
                ids.add(Long.toString(n));
                if (ids.size() > 2000) throw new IllegalArgumentException("单次最多添加 2000 个编号");
            }
        }
        if (ids.isEmpty()) throw new IllegalArgumentException("请先输入编号");
        return new ArrayList<>(ids);
    }

    public static String md5(String text) throws Exception {
        byte[] digest = MessageDigest.getInstance("MD5").digest(text.getBytes(StandardCharsets.UTF_8));
        StringBuilder hex = new StringBuilder();
        for (byte b : digest) hex.append(String.format(Locale.ROOT, "%02x", b & 255));
        return hex.toString();
    }

    public static String decrypt(String encoded, String timestamp, String secret) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/ECB/PKCS5Padding");
        cipher.init(Cipher.DECRYPT_MODE, new SecretKeySpec(md5(timestamp + secret).getBytes(StandardCharsets.UTF_8), "AES"));
        return new String(cipher.doFinal(Base64.getMimeDecoder().decode(encoded.trim())), StandardCharsets.UTF_8);
    }

    public static int segments(long scrambleId, long photoId, String filename) throws Exception {
        if (photoId < scrambleId) return 0;
        if (photoId < 268850) return 10;
        int base = photoId < 421926 ? 10 : 8;
        String hash = md5(Long.toString(photoId) + filename);
        return (hash.charAt(hash.length() - 1) % base) * 2 + 2;
    }

    public static int[] strip(int height, int count, int i) {
        int move = height / count, over = height % count;
        int source = height - move * (i + 1) - over, target = move * i;
        if (i == 0) move += over; else target += over;
        return new int[] {source, target, move};
    }

    public static String outputName(String id, String title, String format, boolean numeric) {
        if (!id.matches("[0-9]{1,10}") || !(format.equals("images") || format.equals("pdf") || format.equals("zip"))) throw new IllegalArgumentException("编号或格式无效");
        return (numeric ? id : "JM" + id + "-" + safeName(title) + "-" + UUID.randomUUID().toString().substring(0,8)) + "." + format;
    }

    public static String zipImageName(boolean flat, int chapterCount, int sequence, int chapter, int page) {
        return chapterCount == 1 ? String.format(Locale.ROOT, "%05d.jpg", sequence) : String.format(Locale.ROOT, "%04d/%05d.jpg", chapter, page);
    }

    public static String safeName(String name) {
        String clean = name.replaceAll("[<>:\"/\\\\|?*\\p{Cntrl}]", "_").trim();
        if (clean.isEmpty()) clean = "未命名";
        return clean.substring(0, Math.min(48, clean.length()));
    }

    public static String error(Throwable error, String cookie) {
        while (error instanceof java.util.concurrent.ExecutionException && error.getCause() != null) error = error.getCause();
        String message = error.getClass().getSimpleName() + ": " + String.valueOf(error.getMessage());
        for (String part : cookie.split(";")) {
            int index = part.indexOf('=');
            if (index >= 0 && part.substring(index + 1).trim().length() >= 3)
                message = message.replace(part.substring(index + 1).trim(), "[已隐藏]");
        }
        message = message.replaceAll("https?://[^\\s\\]<>\"']+", "[请求地址已隐藏]");
        if (message.length() > 1500) message = message.substring(0, 1500);
        return message;
    }

    public interface Progress { void step(int done, int total) throws Exception; }

    public static final class Page {
        public final File jpeg;
        public final int width, height;
        public Page(File jpeg, int width, int height) { this.jpeg = jpeg; this.width = width; this.height = height; }
    }

    /** JPEG embedding keeps PDF memory bounded to a small copy buffer per page. */
    public static void writePdf(File output, List<Page> pages, Progress progress) throws Exception {
        if (pages.isEmpty()) throw new IOException("没有图片，拒绝生成空 PDF");
        int count = 2 + pages.size() * 3;
        long[] offsets = new long[count + 1];
        try (CountingOutput out = new CountingOutput(new BufferedOutputStream(new FileOutputStream(output)))) {
            ascii(out, "%PDF-1.4\n%\u00e2\u00e3\u00cf\u00d3\n");
            object(out, offsets, 1, "<< /Type /Catalog /Pages 2 0 R >>");
            StringBuilder kids = new StringBuilder();
            for (int i = 0; i < pages.size(); i++) kids.append(3 + i * 3).append(" 0 R ");
            object(out, offsets, 2, "<< /Type /Pages /Count " + pages.size() + " /Kids [" + kids + "] >>");
            for (int i = 0; i < pages.size(); i++) {
                Page page = pages.get(i);
                if (page.width <= 0 || page.height <= 0 || !page.jpeg.isFile()) throw new IOException("PDF 图片无效");
                int pageId = 3 + i * 3, imageId = pageId + 1, contentId = pageId + 2;
                // Limit page dimensions in points while retaining original JPEG pixels.
                double scale = Math.min(1.0, 14000.0 / Math.max(page.width, page.height));
                String w = String.format(Locale.ROOT, "%.3f", page.width * scale);
                String h = String.format(Locale.ROOT, "%.3f", page.height * scale);
                object(out, offsets, pageId, "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 " + w + " " + h + "] /Resources << /XObject << /Im0 " + imageId + " 0 R >> >> /Contents " + contentId + " 0 R >>");
                offsets[imageId] = out.count;
                ascii(out, imageId + " 0 obj\n<< /Type /XObject /Subtype /Image /Width " + page.width + " /Height " + page.height + " /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length " + page.jpeg.length() + " >>\nstream\n");
                try (InputStream in = new FileInputStream(page.jpeg)) { copy(in, out); }
                ascii(out, "\nendstream\nendobj\n");
                String content = "q " + w + " 0 0 " + h + " 0 0 cm /Im0 Do Q\n";
                object(out, offsets, contentId, "<< /Length " + content.length() + " >>\nstream\n" + content + "endstream");
                progress.step(i + 1, pages.size());
            }
            long xref = out.count;
            ascii(out, "xref\n0 " + (count + 1) + "\n0000000000 65535 f \n");
            for (int id = 1; id <= count; id++) ascii(out, String.format(Locale.ROOT, "%010d 00000 n \n", offsets[id]));
            ascii(out, "trailer\n<< /Size " + (count + 1) + " /Root 1 0 R >>\nstartxref\n" + xref + "\n%%EOF\n");
        }
    }

    public static void copy(InputStream input, OutputStream output) throws IOException {
        byte[] buffer = new byte[65536]; int n;
        while ((n = input.read(buffer)) != -1) output.write(buffer, 0, n);
    }
    private static void ascii(OutputStream out, String text) throws IOException { out.write(text.getBytes(StandardCharsets.ISO_8859_1)); }
    private static void object(CountingOutput out, long[] offsets, int id, String body) throws IOException {
        offsets[id] = out.count; ascii(out, id + " 0 obj\n" + body + "\nendobj\n");
    }
    private static class CountingOutput extends FilterOutputStream {
        long count;
        CountingOutput(OutputStream out) { super(out); }
        public void write(int value) throws IOException { out.write(value); count++; }
        public void write(byte[] data, int offset, int size) throws IOException { out.write(data, offset, size); count += size; }
    }
}
