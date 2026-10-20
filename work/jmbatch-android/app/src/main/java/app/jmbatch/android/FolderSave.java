package app.jmbatch.android;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.CRC32;

/** One-copy image publication with write-time CRC and independent target readback. */
public final class FolderSave {
    public static final String NO_MEDIA = ".nomedia";
    /** Create before any image is visible; never replace an existing file or follow a link. */
    public static boolean ensureNoMedia(File directory) throws IOException {
        if(Files.isSymbolicLink(directory.toPath())||!directory.isDirectory())
            throw new IOException("无法设置相册隐藏：图片目录不可用");
        File marker=new File(directory,NO_MEDIA);
        if(Files.isSymbolicLink(marker.toPath()))throw new IOException("无法设置相册隐藏：标记为链接");
        boolean created=marker.createNewFile();
        if(!Files.isRegularFile(marker.toPath(),LinkOption.NOFOLLOW_LINKS))
            throw new IOException("无法设置相册隐藏：标记不是文件");
        return created;
    }
    public interface Check { void run() throws Exception; }
    public interface Ownership { void record(File file) throws Exception; }
    public interface Progress { void update(String phase,int done,int total,long bytes,long totalBytes) throws Exception; }
    public interface Input { InputStream open() throws Exception; }
    public interface Target {
        OutputStream write() throws Exception;
        void sync(OutputStream stream) throws Exception;
        InputStream read() throws Exception;
    }
    public static final class Entry {
        public final File source; public final String path; public final long size;
        private final Input input;
        public Entry(File source,String path,long size) throws IOException {
            this(source,()->new FileInputStream(source),path,size);
        }
        /** URI sources are fully inspected by the caller before and after publication. */
        public Entry(Input input,String path,long size)throws IOException {this(null,input,path,size);}
        private Entry(File source,Input input,String path,long size)throws IOException {
            if(path==null||!path.matches("(?:[0-9]{4,}/)?[0-9]{5,}\\.jpg")||size<=0)
                throw new IOException("图片路径或大小无效");
            this.source=source;this.input=Objects.requireNonNull(input);this.path=path;this.size=size;
        }
        private long checkSource()throws IOException {
            if(source==null)return 0;
            if(Files.isSymbolicLink(source.toPath())||!source.isFile()||source.length()!=size)throw new IOException("来源图片已变化："+path);
            return source.lastModified();
        }
    }
    public static long validate(List<Entry> entries) throws IOException {
        if(entries.isEmpty()||entries.size()>20000)throw new IOException("图片数量无效");
        Set<String> names=new HashSet<>();long bytes=0;
        for(Entry entry:entries){
            if(!names.add(entry.path))throw new IOException("图片重复："+entry.path);
            entry.checkSource();
            bytes=Math.addExact(bytes,entry.size);
        }
        return bytes;
    }
    public static void transfer(Entry entry,Target target,Check check,Progress progress,
                                int done,int total,long bytes,long totalBytes) throws Exception {
        check.run();long modified=entry.checkSource();
        byte[] buffer=new byte[65536];CRC32 sourceCrc=new CRC32();long copied=0;
        progress.update("save",done,total,bytes,totalBytes);
        try(InputStream input=entry.input.open();OutputStream output=target.write()){
            if(input==null)throw new IOException("来源图片不可读");
            if(output==null)throw new IOException("保存目录不可写");int n;
            while((n=input.read(buffer))!=-1){
                check.run();copied+=n;if(copied>entry.size)throw new IOException("来源图片大小变化");
                output.write(buffer,0,n);sourceCrc.update(buffer,0,n);
                progress.update("save",done,total,bytes+copied,totalBytes);
            }
            if(copied!=entry.size||entry.checkSource()!=modified)
                throw new IOException("来源图片在保存时发生变化");
            check.run();output.flush();target.sync(output);
        }
        CRC32 targetCrc=new CRC32();long verified=0;
        progress.update("saved_verify",done,total,bytes,totalBytes);
        try(InputStream input=target.read()){
            if(input==null)throw new IOException("无法读回已保存图片");int n;
            while((n=input.read(buffer))!=-1){
                check.run();verified+=n;if(verified>entry.size)throw new IOException("图片保存大小校验失败");
                targetCrc.update(buffer,0,n);progress.update("saved_verify",done,total,bytes+verified,totalBytes);
            }
        }
        if(verified!=entry.size||sourceCrc.getValue()!=targetCrc.getValue())throw new IOException("图片保存校验失败");
        check.run();progress.update("saved_verify",done+1,total,bytes+entry.size,totalBytes);
    }
    public static File publish(File root,List<Entry> entries,String name,Check check,Progress progress) throws Exception {
        return publish(root,entries,name,check,progress,file->{});
    }
    public static File publish(File root,List<Entry> entries,String name,Check check,Progress progress,Ownership ownership) throws Exception {
        if(name.isEmpty()||name.equals(".")||name.equals("..")||name.contains("/")||name.contains("\\"))
            throw new IOException("输出名称无效");
        long totalBytes=validate(entries);check.run();
        if(!root.isDirectory()&&!root.mkdirs()&&!root.isDirectory())throw new IOException("无法创建保存目录");
        File result=new File(root,name),temporary=new File(root,name+"."+UUID.randomUUID()+".partial");
        if(Files.exists(result.toPath(),LinkOption.NOFOLLOW_LINKS))throw new IOException("同名文件已存在，未覆盖："+name);
        Files.createDirectory(temporary.toPath());
        try{
            ownership.record(temporary);
            ensureNoMedia(temporary);
            int done=0;long bytes=0;
            for(Entry entry:entries){
                check.run();File target=new File(temporary,entry.path);
                if(!target.getParentFile().isDirectory()&&!target.getParentFile().mkdirs())throw new IOException("无法创建章节目录");
                if(!target.createNewFile())throw new IOException("图片文件已存在");
                transfer(entry,new Target(){
                    public OutputStream write()throws Exception{return new FileOutputStream(target);}
                    public void sync(OutputStream out)throws Exception{((FileOutputStream)out).getFD().sync();}
                    public InputStream read()throws Exception{return new FileInputStream(target);}
                },check,progress,done,entries.size(),bytes,totalBytes);
                done++;bytes+=entry.size;
            }
            check.run();Files.move(temporary.toPath(),result.toPath());ownership.record(result);return result;
        }finally{
            if(temporary.exists()){clean(temporary,root,()->{},progress);ownership.record(null);}
        }
    }
    private static void collect(File file,String owner,List<File> ordered,Check check) throws Exception {
        check.run();
        if(!file.getCanonicalPath().startsWith(owner)||Files.isSymbolicLink(file.toPath()))throw new IOException("拒绝清理异常缓存路径");
        if(file.isDirectory()){
            File[] children=file.listFiles();if(children==null)throw new IOException("无法读取待清理目录");
            for(File child:children)collect(child,owner,ordered,check);
        }
        ordered.add(file);
    }
    public static void clean(File directory,File owner,Check check,Progress progress) throws Exception {
        if(!directory.exists())return;
        progress.update("cleanup",0,0,0,0);
        List<File> ordered=new ArrayList<>();collect(directory,owner.getCanonicalPath()+File.separator,ordered,check);
        int total=0;for(File file:ordered)if(!file.isDirectory())total++;
        int done=0;progress.update("cleanup",0,total,0,0);
        for(File file:ordered){
            check.run();boolean image=!file.isDirectory();
            if(file.exists()&&!file.delete())throw new IOException("无法清理任务缓存");
            if(image)progress.update("cleanup",++done,total,0,0);
        }
    }
}
