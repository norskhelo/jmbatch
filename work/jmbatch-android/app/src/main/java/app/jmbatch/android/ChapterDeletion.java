package app.jmbatch.android;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import org.json.*;
import java.io.*;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.*;
import java.util.function.*;
import java.util.zip.*;

/** A complete verified replacement is committed before old files are removed. */
public final class ChapterDeletion {
    public static final class Plan {
        public final LinkedHashMap<Integer,Integer> counts=new LinkedHashMap<>();
        final List<Integer> chapters=new ArrayList<>();
        final List<AlbumStorage.Image> images=new ArrayList<>();
        String stamp;
        void add(int chapter){chapters.add(chapter);counts.put(chapter,counts.getOrDefault(chapter,0)+1);}
    }
    private static void check(BooleanSupplier cancelled)throws IOException {
        if(cancelled.getAsBoolean())throw new IOException("已取消删除章节，原漫画保留");
    }
    private static File temporary(Context context)throws IOException {
        File root=new File(context.getCacheDir(),"chapter-delete");
        if(!root.isDirectory()&&!root.mkdirs())throw new IOException("无法建立临时目录");
        return Files.createTempDirectory(root.toPath(),"edit-").toFile();
    }
    private static String stamp(Context context,Uri uri)throws Exception {
        File local=AlbumStorage.local(context,uri);
        if(local!=null)return uri+":"+local.length()+":"+local.lastModified();
        try(Cursor c=context.getContentResolver().query(uri,new String[]{"_size","last_modified"},null,null,null)){
            if(c==null||!c.moveToFirst())throw new IOException("文件不存在或存储不可用");
            return uri+":"+(c.isNull(0)?-1:c.getLong(0))+":"+(c.isNull(1)?-1:c.getLong(1));
        }
    }
    private static final class Reporter {
        final Consumer<String> output;long last;String phase="";
        Reporter(Consumer<String> output){this.output=output;}
        void update(String phase,int done,int total,boolean force){
            long now=System.nanoTime();
            if(force||!phase.equals(this.phase)||now-last>=150_000_000L){
                this.phase=phase;last=now;output.accept(phase+(total>0?" "+done+"/"+total:done>0?" "+done:"…"));
            }
        }
    }
    public static Plan inspect(Context context,LibraryStore.Entry item,BooleanSupplier cancelled)throws Exception {
        return inspect(context,item,cancelled,text->{});
    }
    public static Plan inspect(Context context,LibraryStore.Entry item,BooleanSupplier cancelled,Consumer<String> progress)throws Exception {
        check(cancelled);Reporter report=new Reporter(progress);report.update("正在检查章节目录",0,0,true);
        LibraryStore.get(context).checkLocation(item);Plan plan=new Plan();StringBuilder signature=new StringBuilder();
        if(item.format.equals("images")){
            AlbumStorage.Album album=AlbumStorage.inspectForDeletion(context,Uri.parse(item.uri),()->check(cancelled),
                (phase,done,total,bytes,totalBytes)->report.update("正在读取章节页面",done,total,done==total));
            plan.images.addAll(album.images);
            for(AlbumStorage.Image image:album.images){check(cancelled);plan.add(image.chapter);signature.append(image.chapter).append('/').append(image.page).append(':').append(image.size).append(':').append(image.uri).append(':').append(image.modified).append('\n');}
        }else if(item.format.equals("zip")){
            File temp=temporary(context);
            try{
                File input=new File(temp,"source.zip");copy(context,Uri.parse(item.uri),input,cancelled);
                try(ZipFile zip=new ZipFile(input)){
                    for(ArchivePages.Page page:ArchivePages.read(zip)){plan.add(page.chapter);signature.append(page.entry.getName()).append(':').append(page.entry.getSize()).append(':').append(page.entry.getCrc()).append('\n');}
                }
                signature.append(stamp(context,Uri.parse(item.uri)));
            }finally{Downloader.deleteOwned(temp,temp.getParentFile());}
        }else{plan.add(1);signature.append("pdf");}
        report.update("章节检查完成",plan.chapters.size(),plan.chapters.size(),true);
        plan.stamp=signature.toString();return plan;
    }
    private static long transfer(InputStream input,OutputStream output,BooleanSupplier cancelled,long limit)throws Exception {
        byte[] buffer=new byte[65536];long total=0;int n;
        while((n=input.read(buffer))!=-1){check(cancelled);total+=n;if(total>limit)throw new IOException("文件大小超出支持范围");output.write(buffer,0,n);}return total;
    }
    private static void copy(Context context,Uri source,File target,BooleanSupplier cancelled)throws Exception {
        MessageDigest hash=MessageDigest.getInstance("SHA-256");
        try(InputStream input=new java.security.DigestInputStream(AlbumStorage.open(context,source),hash);FileOutputStream output=new FileOutputStream(target)){
            transfer(input,output,cancelled,ArchivePages.MAX_TOTAL_BYTES);output.getFD().sync();
        }
        byte[] expected=hash.digest();hash.reset();
        try(InputStream input=new java.security.DigestInputStream(new FileInputStream(target),hash)){
            byte[] bytes=new byte[65536];while(input.read(bytes)!=-1)check(cancelled);
        }
        if(!Arrays.equals(expected,hash.digest()))throw new IOException("保留内容保存校验失败，原漫画保留");
    }
    static JSONObject remap(JSONObject previous,List<Integer> chapters,Set<Integer> removed)throws Exception {
        Map<Integer,Integer> mapping=new LinkedHashMap<>();
        for(int i=0;i<chapters.size();i++)if(!removed.contains(chapters.get(i)))mapping.put(i,mapping.size());
        int old=previous.optInt("page",0),page=mapping.size()-1;
        for(int i:mapping.keySet())if(i>=old){page=mapping.get(i);break;}
        JSONArray marks=new JSONArray(),original=previous.optJSONArray("bookmarks");
        if(original!=null)for(int i=0;i<original.length();i++)if(mapping.containsKey(original.getInt(i)))marks.put(mapping.get(original.getInt(i)));
        return new JSONObject().put("page",page).put("mode",previous.optString("mode","scroll")).put("bookmarks",marks);
    }
    public static String delete(Context context,Store store,LibraryStore.Entry item,Plan expected,Set<Integer> removed,
                                BooleanSupplier cancelled,Consumer<String> progress)throws Exception {
        synchronized(store){
            if(store.running||store.libraryBusy)throw new IOException("请先暂停下载队列，再删除章节");
            for(Store.Task task:store.tasks)if(Arrays.asList("running","resetting","cancelling","cancel_failed").contains(task.status)||task.id.equals(item.id)&&task.status.equals("queued"))throw new IOException("下载任务尚未停止，请先暂停或取消");
            store.libraryBusy=true;
        }
        File temp=null;Uri replacement=null;final Uri[] owned={null};boolean committed=false;
        try{
            Plan current=inspect(context,item,cancelled,progress);
            if(!current.stamp.equals(expected.stamp))throw new IOException("漫画内容已变化，请重新打开章节列表");
            if(removed.isEmpty()||!current.counts.keySet().containsAll(removed))throw new IOException("请勾选有效章节");
            if(removed.size()==current.counts.size())throw new IOException("至少保留一章；删除整本请使用“删除文件”");
            SharedPreferences history=context.getSharedPreferences("reader-history",Context.MODE_PRIVATE);
            JSONObject mapped=remap(new JSONObject(history.getString(item.uri,"{}")),current.chapters,removed);
            String name=AlbumRules.exportName(item.id.matches("[0-9]{1,10}")?item.id:"0",item.title,UUID.randomUUID().toString().replace("-","").substring(0,8),item.format,false,0);
            JSONObject metadata=null;
            if(item.format.equals("images")){
                Map<Integer,Integer> numbers=new LinkedHashMap<>();for(int c:current.counts.keySet())if(!removed.contains(c))numbers.put(c,numbers.size()+1);
                JSONArray records=new JSONArray();List<FolderSave.Entry> retained=new ArrayList<>();
                for(AlbumStorage.Image image:current.images){
                    check(cancelled);if(removed.contains(image.chapter))continue;
                    int c=numbers.get(image.chapter);String relative=AlbumRules.imageName(c,image.page,numbers.size());
                    File local=AlbumStorage.local(context,image.uri);
                    retained.add(local==null?new FolderSave.Entry(()->AlbumStorage.open(context,image.uri),relative,image.size):new FolderSave.Entry(local,relative,image.size));
                    records.put(new JSONObject().put("chapter",c).put("page",image.page).put("file",relative).put("size",image.size));
                }
                metadata=new JSONObject().put("version",2).put("id",item.id.matches("[0-9]{1,10}")?item.id:"0").put("title",item.title).put("entries",records);
                Reporter report=new Reporter(progress);progress.accept("正在保存并校验保留章节…");
                replacement=AlbumStorage.publishImages(context,retained,item.tree,name,()->check(cancelled),
                    (phase,done,total,bytes,totalBytes)->report.update(phase.equals("cleanup")?"正在清理临时文件":"校验保留图片",done,total,done==total),uri->owned[0]=uri);
            }else{
                temp=temporary(context);File output=new File(temp,"remaining.zip");
                progress.accept("正在保存并校验保留章节…");
                File input=new File(temp,"source.zip");copy(context,Uri.parse(item.uri),input,cancelled);
                try(ZipFile zip=new ZipFile(input);ZipOutputStream out=new ZipOutputStream(new FileOutputStream(output))){
                    Set<String> discarded=new HashSet<>();for(ArchivePages.Page page:ArchivePages.read(zip))if(removed.contains(page.chapter))discarded.add(page.entry.getName());
                    Enumeration<? extends ZipEntry> all=zip.entries();long bytes=0;
                    while(all.hasMoreElements()){
                        check(cancelled);ZipEntry entry=all.nextElement();if(discarded.contains(entry.getName()))continue;
                        ZipEntry saved=new ZipEntry(entry.getName());saved.setTime(entry.getTime());out.putNextEntry(saved);CRC32 crc=new CRC32();long count;
                        try(InputStream in=new CheckedInputStream(zip.getInputStream(entry),crc)){count=transfer(in,out,cancelled,ArchivePages.MAX_TOTAL_BYTES-bytes);}
                        if(count!=entry.getSize()||crc.getValue()!=entry.getCrc())throw new IOException("ZIP 源文件校验失败");bytes+=count;out.closeEntry();
                    }
                }
                try(ZipFile zip=new ZipFile(output)){
                    Enumeration<? extends ZipEntry> all=zip.entries();byte[] buffer=new byte[65536];
                    while(all.hasMoreElements()){ZipEntry entry=all.nextElement();CRC32 crc=new CRC32();try(InputStream in=new CheckedInputStream(zip.getInputStream(entry),crc)){while(in.read(buffer)!=-1)check(cancelled);}if(crc.getValue()!=entry.getCrc())throw new IOException("ZIP 保存校验失败");}
                }
                replacement=AlbumStorage.publish(context,output,item.tree,name,()->check(cancelled));
            }
            check(cancelled);progress.accept("正在核对原漫画是否变化…");
            if(!inspect(context,item,cancelled,progress).stamp.equals(expected.stamp))throw new IOException("漫画内容已变化，原漫画保留；请重试");
            progress.accept("正在保存漫画库与阅读记录…");
            if(metadata!=null){AlbumStorage.remember(context,replacement,metadata);AlbumStorage.load(context,replacement);}
            check(cancelled);
            if(!history.edit().putString(replacement.toString(),mapped.toString()).commit())throw new IOException("无法保存阅读记录，原漫画保留");
            LibraryStore.Entry updated=new LibraryStore.Entry(item.id,item.title,replacement.toString(),item.tree,item.label,item.format,item.favorite);
            try{LibraryStore.get(context).replaceChapters(store,item,updated);}
            catch(LibraryStore.RecoveryFailure error){committed=true;throw error;}
            committed=true;String warning="";
            progress.accept("正在清理原漫画文件…");
            try{AlbumStorage.remove(context,Uri.parse(item.uri));if(item.format.equals("images"))AlbumStorage.forget(context,Uri.parse(item.uri));}
            catch(Exception error){warning="\n剩余章节已保存，但旧文件清理未完成，请手动处理："+item.uri+"\n"+error.getMessage();}
            LibraryCover.forget(context,item);
            return "已从漫画库删除 "+removed.size()+" 章，保留 "+(current.counts.size()-removed.size())+" 章。"+warning;
        }finally{
            store.libraryBusy=false;
            if(temp!=null)Downloader.deleteOwned(temp,temp.getParentFile());
            Uri abandoned=replacement!=null?replacement:owned[0];
            if(abandoned!=null&&!committed){AlbumStorage.remove(context,abandoned);if(item.format.equals("images"))AlbumStorage.forget(context,abandoned);}
        }
    }
}
