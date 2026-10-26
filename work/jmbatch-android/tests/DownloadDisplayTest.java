import app.jmbatch.android.DownloadDisplay;

public class DownloadDisplayTest {
    static int checks;
    static void check(boolean value, String label) { if (!value) throw new AssertionError(label); checks++; }
    public static void main(String[] args) {
        check(DownloadDisplay.failureText("failed", "IOException: 网络超时\n请重试", "下载失败").equals("失败原因：网络超时 请重试"), "stored reason");
        check(DownloadDisplay.failureText("failed", "SocketTimeoutException: 网络请求超时", "").equals("失败原因：网络请求超时"), "message before technical class");
        check(DownloadDisplay.failureText("failed", "", "自动重连失败").equals("失败原因：自动重连失败"), "legacy phase fallback");
        check(DownloadDisplay.failureText("failed", null, "下载失败，点详情查看原因").contains("未记录具体原因"), "legacy generic fallback");
        for(String status:new String[]{"queued","running","paused","resetting","done","cancelled"})
            check(DownloadDisplay.failureText(status,"旧错误","").isEmpty(), "no stale reason " + status);
        long[] values = {0, 1023, 1024, 1048576, 1073741824, -1};
        String[] expected = {"0 B/s", "1023 B/s", "1.0 KB/s", "1.0 MB/s", "1.0 GB/s", "0 B/s"};
        for (int i = 0; i < values.length; i++) check(DownloadDisplay.speed(values[i]).equals(expected[i]), "speed boundary " + i);
        check(DownloadDisplay.percent(1, 4, "running") == 25, "quarter progress");
        check(DownloadDisplay.percent(4, 4, "running") == 99.9, "wait for export");
        check(DownloadDisplay.percent(4, 4, "failed") == 99.9, "failed export not 100");
        check(DownloadDisplay.percent(4, 4, "done") == 100, "verified completion");
        check(DownloadDisplay.progress(0, 0, "running").contains("0.0%"), "unknown total");
        check(DownloadDisplay.sizeText(2, 4, 2048, 0, "running").equals("已下载图片 2.0 KB / 预计大小 4.0 KB"), "estimated images");
        check(DownloadDisplay.sizeText(4, 4, 4096, 3000, "done").equals("漫画大小 2.9 KB"), "actual export");
        check(DownloadDisplay.sizeText(4, 4, 0, 0, "done").contains("未知"), "legacy queue");
        String eta = DownloadDisplay.eta("running", "download", 15, 20, 10, 10, 2048, 0);
        check(eta.contains("约剩 10 秒") && eta.contains("导出另计"), "exclude cache from rate");
        for (String status : new String[]{"paused", "resetting", "failed", "cancelled", "done"})
            check(!DownloadDisplay.eta(status, "download", 15, 20, 10, 10, 2048, 0).contains("约剩"), "inactive " + status);
        check(DownloadDisplay.eta("running", "download", 10, 20, 10, 1, 2048, 0).contains("计算中"), "all samples cached");
        check(DownloadDisplay.eta("running", "download", 15, 20, 10, 10, 0, 0).contains("计算中"), "stalled");
        check(DownloadDisplay.eta("running", "export", 20, 20, 10, 10, 2048, 0).contains("导出"), "export phase");
        check(DownloadDisplay.eta("running", "page_retry", 19, 20, 10, 10, 2048, 0).contains("重试"), "page recovery");
        String scanning = DownloadDisplay.eta("running", "cache", 15, 20, 10, 10, 2048, 0);
        check(scanning.contains("校验已有图片") && !scanning.contains("约剩"), "cache validation is not downloading");
        System.out.println("DownloadDisplayTest: " + checks + " checks passed");
    }
}
