package app.jmbatch.android;

import android.content.Context;
import android.util.AtomicFile;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public final class Store {
    private static Store instance;
    public static synchronized Store get(Context context) { if (instance == null) instance = new Store(context.getApplicationContext()); return instance; }
    public final Context context;
    public final List<Task> tasks = new ArrayList<>();
    public volatile String cookie = "";
    public volatile Settings settings = new Settings();
    public final Set<String> activeKeys = java.util.concurrent.ConcurrentHashMap.newKeySet();
    public volatile boolean running;
    public volatile boolean libraryBusy;
    public volatile String note = "";
    public volatile String cleanupNotice = "";
    private final AtomicFile file;

    public static final class Settings {
        public String outputUri = "", outputLabel = "应用下载目录", format = "images";
        public int concurrentTasks = 2, threads = 8, timeout = 25, retries = 2, slowKB = 30, window = 90, stall = 180, maxResets = 3;
        public int chapterWorkers = ChapterMetadata.DEFAULT_WORKERS;
        public boolean autoReset = true, keepImages = false, numericFilename = false, flatZip = false;
        public boolean downloadAllChapters = false;
        public Settings() {}
        public Settings(JSONObject json) {
            concurrentTasks = json.optInt("concurrentTasks", 2);
            chapterWorkers = json.optInt("chapterWorkers", ChapterMetadata.DEFAULT_WORKERS);
            downloadAllChapters = json.optBoolean("downloadAllChapters", false);
            outputUri = json.optString("outputUri", ""); outputLabel = json.optString("outputLabel", "应用下载目录");
            format = json.optString("format", "images"); threads = json.optInt("threads", 8); timeout = json.optInt("timeout", 25);
            retries = json.optInt("retries", 2); slowKB = json.optInt("slowKB", 30); window = json.optInt("window", 90);
            stall = json.optInt("stall", 180); maxResets = json.optInt("maxResets", 3);
            autoReset = json.optBoolean("autoReset", true); keepImages = json.optBoolean("keepImages", false);
            numericFilename = json.optBoolean("numericFilename", false); flatZip = json.optBoolean("flatZip", false);
            validate();
        }
        public void validate() {
            check(concurrentTasks, 1, 4, "同时下载任务数");
            check(chapterWorkers, 1, ChapterMetadata.MAX_WORKERS, "章节读取并行数");
            if (!format.equals("images") && !format.equals("pdf") && !format.equals("zip")) throw new IllegalArgumentException("输出格式无效");
            check(threads, 1, 16, "图片线程"); check(timeout, 5, 120, "请求超时"); check(retries, 0, 5, "请求重试");
            check(slowKB, 0, 10240, "慢速阈值"); check(window, 15, 600, "观察窗口"); check(stall, 30, 1800, "无进度超时"); check(maxResets, 0, 10, "重置次数");
        }
        private static void check(int n, int min, int max, String label) { if (n < min || n > max) throw new IllegalArgumentException(label + "应为 " + min + "–" + max); }
        public JSONObject json() {
            JSONObject json = new JSONObject();
            try { json.put("chapterWorkers", chapterWorkers).put("downloadAllChapters", downloadAllChapters).put("outputUri", outputUri).put("outputLabel", outputLabel).put("format", format).put("threads", threads).put("timeout", timeout).put("retries", retries)
                .put("concurrentTasks", concurrentTasks).put("slowKB", slowKB).put("window", window).put("stall", stall).put("maxResets", maxResets).put("autoReset", autoReset).put("keepImages", keepImages).put("numericFilename", numericFilename).put("flatZip", flatZip); }
            catch (JSONException impossible) { throw new IllegalStateException(impossible); }
            return json;
        }
    }

    public static final class Task {
        public final String id, key;
        public Settings settings;
        public volatile String title = "等待获取标题", status = "queued", phase = "排队中", error = "", resultUri = "";
        public volatile int done, total, cached, resets;
        public volatile long bytes, speed, elapsed;
        public volatile long imageBytes, resultBytes, downloadStarted;
        public volatile String stage = "metadata";
        public volatile String cleanupNote = "";
        public volatile List<ChapterRules.Chapter> chapterOptions = Collections.emptyList(), selectedChapters = Collections.emptyList();
        public String progressText() { return DownloadDisplay.progress(done, total, status); }
        public String sizeText() { return DownloadDisplay.sizeText(done, total, imageBytes, resultBytes, status); }
        public String etaText() { String text=DownloadDisplay.eta(status, stage, done, total, cached,
            downloadStarted > 0 ? (android.os.SystemClock.elapsedRealtime() - downloadStarted) / 1000.0 : 0, speed, System.currentTimeMillis());
            return settings.format.equals("images")?text.replace("校验 / 导出","校验 / 保存").replace("导出另计","保存另计"):text; }
        public Task(String id, Settings settings) { this.id = id; this.settings = new Settings(settings.json()); key = UUID.randomUUID().toString(); }
        public Task(JSONObject json) throws JSONException {
            id = json.getString("id"); key = json.getString("key");
            if (!id.matches("[0-9]{1,10}") || !key.matches("[0-9a-f-]{36}")) throw new JSONException("任务数据无效");
            settings = new Settings(json.getJSONObject("settings")); title = json.optString("title"); status = json.optString("status", "paused");
            phase = json.optString("phase"); error = json.optString("error"); resultUri = json.optString("resultUri");
            cleanupNote = json.optString("cleanupNote");
            done = json.optInt("done"); total = json.optInt("total"); cached = json.optInt("cached"); resets = json.optInt("resets"); elapsed = json.optLong("elapsed");
            imageBytes = json.optLong("imageBytes"); resultBytes = json.optLong("resultBytes");
            chapterOptions = ChapterSelection.read(json.optJSONArray("chapterOptions"));
            selectedChapters = ChapterSelection.read(json.optJSONArray("selectedChapters"));
            if (status.equals("running") || status.equals("queued") || status.equals("resetting")) { status = "paused"; phase = "已恢复，点击开始继续"; }
        }
        public JSONObject json() {
            JSONObject json = new JSONObject();
            try { json.put("chapterOptions", ChapterSelection.json(chapterOptions)).put("selectedChapters", ChapterSelection.json(selectedChapters)).put("id", id).put("key", key).put("settings", settings.json()).put("title", title).put("status", status).put("phase", phase).put("error", error)
                .put("resultUri", resultUri).put("done", done).put("total", total).put("cached", cached).put("resets", resets).put("elapsed", elapsed)
                .put("imageBytes", imageBytes).put("resultBytes", resultBytes).put("cleanupNote",cleanupNote); }
            catch (JSONException impossible) { throw new IllegalStateException(impossible); }
            return json;
        }
    }

    private Store(Context context) {
        this.context = context; file = new AtomicFile(new File(context.getFilesDir(), "queue.json"));
        if (!file.getBaseFile().exists()) return;
        try (InputStream input = file.openRead()) {
            ByteArrayOutputStream buffer = new ByteArrayOutputStream(); Core.copy(input, buffer);
            JSONObject root = new JSONObject(buffer.toString("UTF-8")); settings = new Settings(root.getJSONObject("settings"));
            cleanupNotice = root.optString("cleanupNotice");
            JSONArray list = root.getJSONArray("tasks"); for (int i = 0; i < list.length(); i++) tasks.add(new Task(list.getJSONObject(i)));
        } catch (Exception error) {
            tasks.clear(); settings = new Settings();
            File backup = new File(context.getFilesDir(), "queue-unreadable-" + System.currentTimeMillis() + ".json");
            if (file.getBaseFile().renameTo(backup)) note = "旧队列损坏，已保存备份。"; else note = "旧队列无法读取。";
        }
    }

    public synchronized void save() throws IOException {
        FileOutputStream stream = null;
        try {
            JSONObject root = new JSONObject(); JSONArray list = new JSONArray();
            for (Task task : tasks) list.put(task.json()); root.put("settings", settings.json()).put("tasks", list).put("cleanupNotice",cleanupNotice);
            stream = file.startWrite(); stream.write(root.toString(2).getBytes(StandardCharsets.UTF_8)); file.finishWrite(stream);
        } catch (Exception error) { if (stream != null) file.failWrite(stream); throw new IOException("保存队列失败：" + error.getMessage(), error); }
    }
    public synchronized List<Task> snapshot() { return new ArrayList<>(tasks); }
    public synchronized int add(List<String> ids, Settings options) throws IOException {
        if (tasks.size() + ids.size() > 5000) throw new IllegalArgumentException("最多保留 5000 条记录，请先清理已完成记录");
        Set<String> exists = new HashSet<>(); for (Task t : tasks) if (!t.status.equals("cancelled")) exists.add(t.id + "|" + t.settings.format + "|" + t.settings.outputUri);
        int count = 0;
        for (String id : ids) if (exists.add(id + "|" + options.format + "|" + options.outputUri)) { tasks.add(new Task(id, options)); count++; }
        settings = new Settings(options.json()); save(); return count;
    }
    public synchronized Task next() { for (Task t : tasks) if (t.status.equals("queued") && !activeKeys.contains(t.key)) return t; return null; }
    public synchronized void resume() throws IOException { for (Task t : tasks) if (t.status.equals("paused")) { t.status = !t.chapterOptions.isEmpty() && t.selectedChapters.isEmpty() ? "selecting" : "queued"; t.phase = t.status.equals("selecting") ? "请选择下载章节" : "排队中"; } save(); }
    public synchronized void pauseQueued() throws IOException { for (Task t : tasks) if (t.status.equals("queued") || t.status.equals("selecting")) { t.status = "paused"; t.phase = "已暂停"; } save(); }
    public synchronized void pauseQueuedOnly() throws IOException { for(Task t:tasks)if(t.status.equals("queued")){t.status="paused";t.phase="已暂停";}save(); }
    public File cache(Task task) throws IOException {
        File parent = new File(context.getFilesDir(), "work"); File target = new File(parent, task.key);
        if (!target.getCanonicalFile().getParentFile().equals(parent.getCanonicalFile())) throw new IOException("缓存路径异常");
        if (!target.exists() && !target.mkdirs()) throw new IOException("无法创建图片缓存目录");
        return target;
    }
    public static String status(String status) {
        switch (status) { case "selecting": return "待选章节"; case "running": return "下载中"; case "done": return "下载完成"; case "failed": return "失败"; case "paused": return "已暂停"; case "cancelled": return "已取消"; case "resetting": return "正在恢复"; default: return "排队中"; }
    }
}
