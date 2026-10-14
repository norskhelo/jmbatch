package app.jmbatch.android;

import java.io.IOException;
import java.util.*;

/** Shared ordering and naming rules, independent of Android storage APIs. */
public final class AlbumRules {
    public static final String MANIFEST = ".jmbatch-album.json";
    public static String imageName(int chapter, int page) throws IOException {
        if (chapter < 1 || page < 1) throw new IOException("章节或页码无效");
        return String.format(Locale.ROOT, "%04d/%05d.jpg", chapter, page);
    }
    public static String exportName(String id, String title, String token, String format, boolean numeric, int chapter) throws IOException {
        if (!id.matches("[0-9]{1,10}") || !Arrays.asList("pdf", "zip").contains(format)) throw new IOException("导出参数无效");
        String clean = title.replaceAll("[<>:\"/\\\\|?*\\p{Cntrl}]", "_").trim();
        if (clean.length() > 60) clean = clean.substring(0,60);
        return (numeric ? id : "JM" + id + "-" + clean + "-" + token)
            + (chapter > 0 ? String.format(Locale.ROOT, "-%04d", chapter) : "") + "." + format;
    }
    public static int group(String format, boolean split, int chapter) { return format.equals("pdf") && split ? chapter : 0; }
}
