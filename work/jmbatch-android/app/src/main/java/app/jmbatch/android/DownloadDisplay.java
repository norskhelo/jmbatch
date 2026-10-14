package app.jmbatch.android;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** Pure presentation rules; validated images are distinct from retry traffic. */
public final class DownloadDisplay {
    public static String size(double value) {
        value = Math.max(0, value);
        String[] units = {"B", "KB", "MB", "GB", "TB"};
        int unit = 0;
        while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
        return String.format(Locale.ROOT, unit == 0 ? "%.0f %s" : "%.1f %s", value, units[unit]);
    }
    public static String speed(long value) { return size(value) + "/s"; }
    public static double percent(int done, int total, String status) {
        return status.equals("done") ? 100 : total > 0 ? Math.min(99.9, Math.max(0, done) * 100.0 / total) : 0;
    }
    public static String progress(int done, int total, String status) {
        return String.format(Locale.ROOT, "%.1f%% · %d/%s 张", percent(done, total, status), done, total > 0 ? String.valueOf(total) : "?");
    }
    public static String sizeText(int done, int total, long images, long result, String status) {
        if (status.equals("done")) return "漫画大小 " + (result > 0 ? size(result) : "未知（旧记录）");
        if (done <= 0 || images <= 0) return "已下载图片 0 B · 预计大小 计算中";
        return total > done ? "已下载图片 " + size(images) + " / 预计大小 " + size(images * (double)total / done) : "图片大小 " + size(images);
    }
    public static String eta(String status, String stage, int done, int total, int cached, double elapsed, long speed, long now) {
        if (!status.equals("running")) {
            switch (status) {
                case "done": return "下载完成";
                case "paused": return "已暂停";
                case "resetting": return "重连后重新估算";
                case "failed": return "下载失败";
                case "cancelled": return "已取消";
                default: return "等待下载";
            }
        }
        if (total > 0 && done >= total || stage.equals("verify") || stage.equals("export")) return "正在校验 / 导出，预计完成时间待定";
        if (stage.equals("page_retry")) return "正在重试失败页，预计完成时间待定";
        if (!stage.equals("download") || done <= cached || total <= 0 || elapsed <= 0 || speed <= 0) return "预计完成时间：计算中";
        long remaining = Math.max(1, (long)Math.ceil((total - done) * elapsed / (done - cached)));
        if (remaining > 365 * 86400L) return "预计完成时间：计算中";
        String clock = new SimpleDateFormat("MM-dd HH:mm:ss", Locale.ROOT).format(new Date(now + remaining * 1000));
        String duration = remaining < 60 ? remaining + " 秒" : remaining < 3600 ? (long)Math.ceil(remaining / 60.0) + " 分钟" : String.format(Locale.ROOT, "%.1f 小时", remaining / 3600.0);
        return "预计完成 " + clock + "（约剩 " + duration + "，导出另计）";
    }
}
