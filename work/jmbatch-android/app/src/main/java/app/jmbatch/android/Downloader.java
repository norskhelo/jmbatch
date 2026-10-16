package app.jmbatch.android;

import android.content.Context;
import android.database.Cursor;
import android.graphics.*;
import android.net.Uri;
import android.os.*;
import android.provider.DocumentsContract;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.zip.*;

public final class Downloader {
    private final Context context;
    private final Store store;
    private final Store.Task task;
    private final JmApi.Control control;
    private final String cookie;
    private final Semaphore decodeGate = new Semaphore(1);
    private final File cache;

    private static final class ImageJob {
        String chapterId, filename; int chapter, page; long scramble; File target;
    }

    public Downloader(Context context, Store store, Store.Task task, JmApi.Control control, String cookie) throws IOException {
        this.context = context; this.store = store; this.task = task; this.control = control; this.cookie = cookie; cache = store.cache(task);
    }

    public String run() throws Exception {
        File marker = new File(cache, "completed.json");
        if (marker.isFile()) {
            try {
                JSONObject finished = new JSONObject(readText(marker)); Uri uri = Uri.parse(finished.getString("uri"));
                if(task.settings.format.equals("images")) {
                    if(!finished.optString("format").equals("images")||finished.optInt("albumLayoutVersion")!=AlbumRules.LAYOUT_VERSION)throw new IOException("旧版成品需重新保存图片");
                    AlbumStorage.Album album=AlbumStorage.load(context,uri);task.total=task.done=album.images.size();task.resultBytes=0;
                    for(AlbumStorage.Image image:album.images)task.resultBytes+=image.size;
                    return uri.toString();
                }
                if (finished.optBoolean("numericFilename", false) != task.settings.numericFilename ||
                    (task.settings.format.equals("zip") && finished.optInt("zipLayoutVersion", 0) != Core.ZIP_LAYOUT_VERSION)) throw new IOException("导出设置已变化");
                try (InputStream input = context.getContentResolver().openInputStream(uri)) {
                    if (input != null && input.read() >= 0) {
                        task.total = task.done = finished.getInt("images");
                        task.resultBytes = finished.optLong("resultBytes");
                        if (task.resultBytes <= 0) {
                            try (android.os.ParcelFileDescriptor descriptor = context.getContentResolver().openFileDescriptor(uri, "r")) {
                                if (descriptor != null) task.resultBytes = Math.max(0, descriptor.getStatSize());
                            } catch (IOException ignored) { /* Older providers may not report a size. */ }
                        }
                        return uri.toString();
                    }
                }
            } catch (Exception ignored) { /* Missing external file: rebuild from cache/network. */ }
        }
        checkSpace(256L * 1024 * 1024);
        JmApi api = new JmApi(task.settings, cookie, control);
        task.phase = "正在连接并获取会话"; api.initialize(); control.check();
        task.phase = "读取漫画与章节信息";
        JSONObject album = api.detail("album", task.id); task.title = album.getString("name");
        JSONArray series = album.optJSONArray("series"); List<JSONObject> chapters = new ArrayList<>();
        if (series != null) for (int i = 0; i < series.length(); i++) chapters.add(series.getJSONObject(i));
        if (chapters.isEmpty()) chapters.add(new JSONObject().put("id", task.id).put("sort", 1));
        chapters.sort(Comparator.comparingInt(item -> item.optInt("sort", 1)));
        List<ChapterRules.Chapter> catalog = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for(JSONObject chapter:chapters){
            String id=chapter.getString("id");
            if(seen.add(id))catalog.add(new ChapterRules.Chapter(id,catalog.size()+1,chapter.optString("name","第 "+(catalog.size()+1)+" 章")));
        }
        List<ChapterRules.Chapter> chosen=ChapterRules.resolve(catalog,task.selectedChapters,task.settings.downloadAllChapters);
        task.selectedChapters=Collections.unmodifiableList(new ArrayList<>(chosen));store.save();control.check();
        List<ImageJob> jobs = new ArrayList<>(); Set<String> chapterIds = new HashSet<>(); long scramble = -1;
        for (ChapterRules.Chapter chapter : chosen) {
            control.check(); String id = chapter.id;
            if (!id.matches("[0-9]{1,10}")) throw new IOException("服务端章节编号无效");
            if (!chapterIds.add(id)) continue;
            int index = chapter.number; task.phase = "读取所选章节 " + chapterIds.size() + "/" + chosen.size();
            JSONObject detail = api.detail("chapter", id); JSONArray files = detail.optJSONArray("images");
            if (files == null || files.length() == 0) throw new IOException("第 " + index + " 章没有图片，可能需要登录");
            if (scramble < 0) scramble = api.scramble(id);
            File directory = new File(new File(cache, "images"), String.format(Locale.ROOT, "%04d", index));
            if (!directory.exists() && !directory.mkdirs()) throw new IOException("无法创建图片目录");
            for (int p = 0; p < files.length(); p++) {
                ImageJob job = new ImageJob(); job.chapterId = id; job.filename = files.getString(p); job.chapter = index; job.page = p + 1; job.scramble = scramble;
                job.target = new File(directory, String.format(Locale.ROOT, "%05d.jpg", p + 1)); jobs.add(job);
                if (jobs.size() > 20000) throw new IOException("单本超过 20000 张图片，请拆分任务");
            }
        }
        task.stage = control.stage = "cache"; task.speed = 0;
        task.phase = "正在校验已有图片，保留原进度";
        ResumeCache.Result<ImageJob> restored = ResumeCache.scan(jobs, control::check,
            job -> job.target.isFile() && validImage(job.target) ? job.target.length() : -1,
            (checked, total, cached) -> {
                control.lastData = SystemClock.elapsedRealtime();
                task.phase = "校验已有图片 " + checked + "/" + total + "，已确认 " + cached + " 张可复用";
            });
        synchronized (task) {
            task.total = jobs.size(); task.done = task.cached = restored.cached;
            task.bytes = 0; task.imageBytes = restored.imageBytes;
        }
        task.stage = control.stage = "download"; task.downloadStarted = control.lastData = SystemClock.elapsedRealtime();
        task.phase = "已恢复 " + task.done + "/" + task.total + " 张图片，继续下载剩余 " + restored.pending.size() + " 张";
        ExecutorService pool = Executors.newFixedThreadPool(task.settings.threads);
        CompletionService<SinglePageRecovery.Failure<ImageJob>> completion = new ExecutorCompletionService<>(pool);
        List<SinglePageRecovery.Failure<ImageJob>> failed = new ArrayList<>();
        boolean collected = false;
        try {
            for (ImageJob job : restored.pending) completion.submit(() -> {
                try { downloadImage(api, job, 0); return null; }
                catch (Exception error) { control.check(); return new SinglePageRecovery.Failure<>(job,error,"第 "+job.chapter+" 章第 "+job.page+" 页"); }
            });
            for (int i = 0; i < restored.pending.size(); i++) { control.check(); SinglePageRecovery.Failure<ImageJob> failure=completion.take().get(); if(failure!=null)failed.add(failure); }
            collected = true;
        } finally {
            pool.shutdownNow();
            if (!collected && control.stop.isEmpty()) control.cancel("ABORT");
            // A reset must not start until old workers have stopped using their files.
            if (!pool.awaitTermination(task.settings.timeout + 10L, TimeUnit.SECONDS)) {
                control.cancel("FATAL");
                throw new IOException("旧下载线程未能及时退出；已停止该任务以避免重复写入。请重启应用后重试。");
            }
        }
        control.check();
        SinglePageRecovery.recover(failed,(job,round)->downloadImage(api,job,round),control::check,
            message->{task.stage=control.stage="page_retry";control.lastData=SystemClock.elapsedRealtime();task.phase=message;},
            error->!(error instanceof NetworkRoutes.HttpFailure && ((NetworkRoutes.HttpFailure)error).code<500)
                && !String.valueOf(error.getMessage()).contains("存储空间不足") && !String.valueOf(error.getMessage()).contains("解码内存"));
        if (task.done != task.total) throw new IOException("图片不完整：" + task.done + "/" + task.total + "，未生成成品");
        task.stage = control.stage = "verify"; task.phase = "核对图片和章节完整性";
        List<Core.Page> pages = new ArrayList<>(); long totalSize = 0;
        for (ImageJob job : jobs) {
            control.check(); BitmapFactory.Options bounds = dimensions(job.target);
            if (bounds.outWidth <= 0 || bounds.outHeight <= 0) throw new IOException("图片损坏：第 " + job.chapter + " 章第 " + job.page + " 张");
            pages.add(new Core.Page(job.target, bounds.outWidth, bounds.outHeight)); totalSize += job.target.length();
        }
        checkSpace(totalSize + 64L*1024*1024);
        if(task.settings.format.equals("images")) {
            task.stage=control.stage="export";task.phase="保存排序图片";
            File staging=new File(cache,"album-stage-"+UUID.randomUUID());if(!staging.mkdir())throw new IOException("无法创建图片暂存目录");
            try {
                JSONArray entries=new JSONArray();
                for(ImageJob job:jobs){
                    control.check();String relative=AlbumRules.imageName(job.chapter,job.page,chapterIds.size());File target=new File(staging,relative);
                    if(!target.getParentFile().exists()&&!target.getParentFile().mkdirs())throw new IOException("无法创建章节目录");
                    Files.copy(job.target.toPath(),target.toPath());
                    entries.put(new JSONObject().put("chapter",job.chapter).put("page",job.page).put("file",relative).put("size",target.length()));
                }
                String filename=Core.outputName(task.id,task.title,"images",false);String folderName=filename.substring(0,filename.length()-7);
                String uri=AlbumStorage.publish(context,staging,task.settings.outputUri,folderName,control::check).toString();
                AlbumStorage.remember(context,Uri.parse(uri),new JSONObject().put("version",AlbumRules.LAYOUT_VERSION).put("id",task.id).put("title",task.title).put("entries",entries));
                AlbumStorage.load(context,Uri.parse(uri));
                task.resultBytes=totalSize;
                writeTextAtomic(marker,new JSONObject().put("uri",uri).put("images",jobs.size()).put("format","images").put("resultBytes",totalSize).put("albumLayoutVersion",AlbumRules.LAYOUT_VERSION).toString());
                if(!task.settings.keepImages)try{deleteOwned(new File(cache,"images"),cache);}catch(IOException ignored){}
                return uri;
            } finally { if(staging.exists())deleteOwned(staging,cache); }
        }
        task.stage = control.stage = "export";
        File partial = new File(cache, "export.partial." + task.settings.format);
        if (task.settings.format.equals("pdf")) {
            Core.writePdf(partial, pages, (n, total) -> { control.check(); task.phase = "生成 PDF " + n + "/" + total; });
            verifyPdf(partial);
        } else {
            try (ZipOutputStream zip = new ZipOutputStream(new BufferedOutputStream(new FileOutputStream(partial)))) {
                zip.setLevel(1);
                for (int i = 0; i < jobs.size(); i++) {
                    control.check(); ImageJob job = jobs.get(i);
                    task.phase = "打包图片 " + (i+1) + "/" + jobs.size();
                    zip.putNextEntry(new ZipEntry(Core.zipImageName(task.settings.flatZip, chapterIds.size(), i+1, job.chapter, job.page)));
                    try (InputStream input = new FileInputStream(job.target)) { copyChecked(input, zip); }
                    zip.closeEntry();
                }
            }
            try (ZipFile zip = new ZipFile(partial)) {
                if (zip.size() != jobs.size()) throw new IOException("ZIP 文件数量不一致");
                Enumeration<? extends ZipEntry> entries = zip.entries();
                while (entries.hasMoreElements()) {
                    control.check(); ZipEntry entry = entries.nextElement(); CRC32 crc = new CRC32();
                    try (InputStream input = zip.getInputStream(entry)) { byte[] buffer = new byte[32768]; int n; while ((n=input.read(buffer)) != -1) crc.update(buffer,0,n); }
                    if (crc.getValue() != entry.getCrc()) throw new IOException("ZIP 校验失败");
                }
            }
        }
        control.check(); task.phase = "保存并验证输出文件";
        long resultSize = partial.length();
        String uri = publish(partial);
        task.resultBytes = resultSize;
        writeTextAtomic(marker, new JSONObject().put("uri", uri).put("images", jobs.size()).put("resultBytes", resultSize).put("numericFilename", task.settings.numericFilename).put("flatZip", task.settings.flatZip).put("zipLayoutVersion", Core.ZIP_LAYOUT_VERSION).toString());
        if (!task.settings.keepImages) {
            try { deleteOwned(new File(cache, "images"), cache); } catch (IOException ignored) { /* A valid output is still a success. */ }
        }
        return uri;
    }

    private void downloadImage(JmApi api, ImageJob job, int retryRound) throws Exception {
        control.check(); boolean cached = false;
        if (job.target.isFile()) {
            decodeGate.acquire();
            try { cached = validImage(job.target); } finally { decodeGate.release(); }
        }
        if (!cached) {
            checkSpace(32L*1024*1024);
            File raw = new File(job.target.getParentFile(), job.target.getName() + ".download");
            File decoded = new File(job.target.getParentFile(), job.target.getName() + ".partial");
            try {
            api.image(job.chapterId, job.filename, raw, retryRound); control.check();
            decodeGate.acquire();
            try {
                control.check();
                String name = job.filename.contains(".") ? job.filename.substring(0, job.filename.lastIndexOf('.')) : job.filename;
                decode(raw, decoded, Core.segments(job.scramble, Long.parseLong(job.chapterId), name));
                control.check(); Files.move(decoded.toPath(), job.target.toPath(), StandardCopyOption.REPLACE_EXISTING);
            } finally { decodeGate.release(); }
            } finally { raw.delete(); decoded.delete(); }
        }
        control.check();
        synchronized (task) { task.imageBytes += job.target.length(); task.done++; if (cached) task.cached++; task.phase = "第 " + job.chapter + " 章 · 图片 " + job.page + "（已完成 " + task.done + "/" + task.total + "）"; }
        control.lastData = SystemClock.elapsedRealtime();
    }

    static BitmapFactory.Options dimensions(File file) {
        BitmapFactory.Options options = new BitmapFactory.Options(); options.inJustDecodeBounds = true; BitmapFactory.decodeFile(file.getAbsolutePath(), options); return options;
    }
    private boolean validImage(File file) {
        try {
            BitmapFactory.Options bounds = dimensions(file); if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return false;
            checkBitmapMemory(bounds.outWidth, bounds.outHeight);
            Bitmap image = BitmapFactory.decodeFile(file.getAbsolutePath()); if (image == null) return false; image.recycle(); return true;
        } catch (Exception ignored) { return false; }
    }
    static void checkBitmapMemory(int width, int height) throws IOException {
        if (width <= 0 || height <= 0 || (long)width * height * 8 > Runtime.getRuntime().maxMemory() * .60)
            throw new IOException("单张图片尺寸过大，超出当前手机安全解码内存；未缩小图片或生成不完整文件");
    }
    static void decode(File raw, File output, int count) throws Exception {
        BitmapFactory.Options bounds = dimensions(raw); checkBitmapMemory(bounds.outWidth, bounds.outHeight);
        Bitmap source = BitmapFactory.decodeFile(raw.getAbsolutePath()); if (source == null) throw new IOException("图片解码失败，响应可能不是图片");
        Bitmap result = null;
        try {
            // Produce RGB JPEGs so PDF /DeviceRGB is always correct.
            result = Bitmap.createBitmap(source.getWidth(), source.getHeight(), Bitmap.Config.ARGB_8888);
            Canvas canvas = new Canvas(result); canvas.drawColor(Color.WHITE); Paint paint = new Paint();
            if (count == 0) canvas.drawBitmap(source, 0, 0, paint);
            else for (int i = 0; i < count; i++) {
                int[] strip = Core.strip(source.getHeight(), count, i);
                canvas.drawBitmap(source, new Rect(0,strip[0],source.getWidth(),strip[0]+strip[2]), new Rect(0,strip[1],source.getWidth(),strip[1]+strip[2]), paint);
            }
            try (FileOutputStream stream = new FileOutputStream(output)) {
                if (!result.compress(Bitmap.CompressFormat.JPEG, 92, stream)) throw new IOException("无法保存解码图片");
                stream.getFD().sync();
            }
        } finally { source.recycle(); if (result != null) result.recycle(); }
    }

    private void checkSpace(long bytes) throws IOException { if (new StatFs(cache.getAbsolutePath()).getAvailableBytes() < bytes) throw new IOException("手机存储空间不足，需要至少约 " + bytes/1024/1024 + " MB 可用空间"); }

    private String publish(File source) throws Exception {
        String name = Core.outputName(task.id, task.title, task.settings.format, task.settings.numericFilename);
        if (task.settings.outputUri.isEmpty()) {
            File directory = new File(context.getExternalFilesDir(null) == null ? context.getFilesDir() : context.getExternalFilesDir(null), "exports");
            if (!directory.exists() && !directory.mkdirs()) throw new IOException("无法创建输出目录");
            File partial = new File(directory, name + "." + task.key + ".partial"), result = new File(directory,name);
            if (result.exists()) throw duplicate(name);
            try (InputStream input = new FileInputStream(source); FileOutputStream output = new FileOutputStream(partial)) { copyChecked(input,output); output.getFD().sync(); }
            if (partial.length() != source.length() || crc(partial) != crc(source)) throw new IOException("输出文件校验失败");
            control.check(); Files.move(partial.toPath(),result.toPath()); source.delete();
            return ExportProvider.uri(context, result).toString();
        }
        Uri tree = Uri.parse(task.settings.outputUri);
        Uri parent = DocumentsContract.buildDocumentUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree));
        if (task.settings.numericFilename) ensureAbsent(tree, name);
        Uri partial = DocumentsContract.createDocument(context.getContentResolver(), parent, task.settings.format.equals("pdf") ? "application/pdf" : "application/zip", name + "." + task.key + ".partial");
        if (partial == null) throw new IOException("无法在所选目录创建文件，请重新选择输出目录");
        boolean committed = false;
        try {
            CRC32 expected = new CRC32(); long count = 0;
            try (InputStream input = new FileInputStream(source); OutputStream output = context.getContentResolver().openOutputStream(partial,"w")) {
                if (output == null) throw new IOException("所选目录不可写"); byte[] buffer = new byte[65536]; int n;
                while ((n=input.read(buffer))!=-1) { control.check(); output.write(buffer,0,n); expected.update(buffer,0,n); count+=n; } output.flush();
            }
            CRC32 actual = new CRC32(); long size = 0;
            try (InputStream input = context.getContentResolver().openInputStream(partial)) {
                if (input == null) throw new IOException("无法验证输出文件"); byte[] buffer = new byte[65536]; int n;
                while ((n=input.read(buffer))!=-1) { control.check(); actual.update(buffer,0,n); size+=n; }
            }
            if (size!=count || expected.getValue()!=actual.getValue()) throw new IOException("输出文件校验失败");
            control.check(); if (task.settings.numericFilename) ensureAbsent(tree, name);
            Uri result = DocumentsContract.renameDocument(context.getContentResolver(),partial,name);
            if (result == null) throw new IOException("所选目录不支持安全重命名，请选择手机本地目录");
            partial = result;
            if (task.settings.numericFilename) {
                try (Cursor cursor = context.getContentResolver().query(result, new String[]{DocumentsContract.Document.COLUMN_DISPLAY_NAME}, null, null, null)) {
                    if (cursor == null || !cursor.moveToFirst() || !name.equals(cursor.getString(0))) throw new IOException("存储提供方更改了文件名，无法保留纯编号；请选择其他本机目录");
                }
            }
            committed = true; source.delete(); return result.toString();
        } finally { if (!committed) try { DocumentsContract.deleteDocument(context.getContentResolver(),partial); } catch (Exception ignored) {} }
    }
    private IOException duplicate(String name) { return new IOException("同名成品已存在：" + name + "，未覆盖。请移动已有文件、更换目录或关闭纯编号命名后重试。"); }
    private void ensureAbsent(Uri tree, String name) throws IOException {
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree));
        try (Cursor cursor = context.getContentResolver().query(children, new String[]{DocumentsContract.Document.COLUMN_DISPLAY_NAME}, null, null, null)) {
            if (cursor == null) throw new IOException("无法检查所选目录中的同名文件");
            while (cursor.moveToNext()) if (name.equalsIgnoreCase(cursor.getString(0))) throw duplicate(name);
        }
    }
    private void copyChecked(InputStream input, OutputStream output) throws Exception { byte[] buffer = new byte[65536]; int n; while ((n=input.read(buffer))!=-1) { control.check(); output.write(buffer,0,n); } }
    private static long crc(File file) throws IOException { CRC32 crc = new CRC32(); try(InputStream in=new FileInputStream(file)){ byte[] b=new byte[65536]; int n; while((n=in.read(b))!=-1)crc.update(b,0,n); } return crc.getValue(); }
    static String readText(File file) throws IOException { try(InputStream input=new FileInputStream(file)){ ByteArrayOutputStream out=new ByteArrayOutputStream(); Core.copy(input,out); return out.toString("UTF-8"); } }
    static void writeTextAtomic(File file,String text) throws IOException { File tmp=new File(file.getParentFile(),file.getName()+".tmp"); try(FileOutputStream out=new FileOutputStream(tmp)){out.write(text.getBytes(StandardCharsets.UTF_8));out.getFD().sync();} Files.move(tmp.toPath(),file.toPath(),StandardCopyOption.REPLACE_EXISTING); }
    static void verifyPdf(File file) throws IOException {
        try(RandomAccessFile in=new RandomAccessFile(file,"r")){ if(in.length()<32)throw new IOException("PDF 为空"); in.seek(in.length()-6); byte[] tail=new byte[6];in.readFully(tail);if(!new String(tail,StandardCharsets.US_ASCII).equals("%%EOF\n"))throw new IOException("PDF 写入未完成"); }
    }
    static void deleteOwned(File target, File owner) throws IOException {
        String root=owner.getCanonicalPath()+File.separator;
        if(!target.getCanonicalPath().startsWith(root)||Files.isSymbolicLink(target.toPath()))throw new IOException("拒绝清理异常缓存路径");
        File[] children=target.listFiles();if(children!=null)for(File child:children)deleteOwned(child,owner);
        if(target.exists()&&!target.delete())throw new IOException("无法清理任务缓存");
    }
}
