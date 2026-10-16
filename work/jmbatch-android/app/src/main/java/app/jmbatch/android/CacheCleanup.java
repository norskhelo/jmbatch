package app.jmbatch.android;

import java.io.*;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;

/** Only known task artifacts. Callers must keep workers out until cleanup finishes. */
public final class CacheCleanup {
    public interface Progress { void update(Result result); }
    public static final class Result {
        public long files, bytes;
        public int errors;
        public void add(Result other){files+=other.files;bytes+=other.bytes;errors+=other.errors;}
        public String message(boolean automatic){
            return (automatic?"自动清理":"缓存清理")+"：已删除 "+files+" 个文件，释放 "+DownloadDisplay.size(bytes)
                +(errors>0?"；"+errors+" 项未能清理，可稍后重试":"");
        }
    }
    private static void safe(File file,File owner)throws IOException{
        Path root=owner.getAbsoluteFile().toPath().normalize(),path=file.getAbsoluteFile().toPath().normalize();
        if(!path.startsWith(root))throw new IOException("缓存路径越界");
        for(Path p=path;p!=null&&p.startsWith(root);p=p.getParent()){
            if(!Files.exists(p,LinkOption.NOFOLLOW_LINKS))continue;
            BasicFileAttributes attributes=Files.readAttributes(p,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS);
            Path expected=p.getParent().toRealPath().resolve(p.getFileName());
            if(attributes.isSymbolicLink()||attributes.isOther()||!p.toRealPath().equals(expected))throw new IOException("拒绝清理链接路径");
        }
        if(!file.getCanonicalPath().startsWith(owner.getCanonicalPath()+File.separator))throw new IOException("缓存路径越界");
    }
    private static void remove(File file,File owner,Result result,Progress progress){
        try{
            safe(file,owner);
            if(!file.exists())return;
            if(file.isDirectory()){
                File[] children=file.listFiles();if(children==null)throw new IOException("无法读取缓存目录");
                for(File child:children)remove(child,owner,result,progress);
                if(!file.delete())throw new IOException("无法清理缓存目录");
            }else if(file.isFile()){
                long bytes=file.length();if(!file.delete())throw new IOException("无法清理缓存文件");
                result.files++;result.bytes+=bytes;if(result.files%100==0)progress.update(result);
            }
        }catch(IOException|SecurityException error){result.errors++;}
    }
    private static void partials(File file,File owner,Result result,Progress progress){
        try{
            safe(file,owner);
            if(file.isDirectory()){
                File[] children=file.listFiles();if(children==null)throw new IOException("无法读取缓存目录");
                for(File child:children)partials(child,owner,result,progress);
            }else if(file.getName().endsWith(".jpg.download")||file.getName().endsWith(".jpg.partial"))remove(file,owner,result,progress);
        }catch(IOException|SecurityException error){result.errors++;}
    }
    public static Result clean(File cache,File owner,boolean completed,boolean keepImages,Progress progress){
        Result result=new Result();
        try{
            safe(cache,owner);
            if(!cache.exists())return result;
            File[] children=cache.listFiles();if(children==null)throw new IOException("无法读取缓存目录");
            for(File file:children){
                String name=file.getName();
                if(name.equals("images")){
                    if(completed&&!keepImages)remove(file,owner,result,progress);else partials(file,owner,result,progress);
                }else if(name.equals("export.partial.pdf")||name.equals("export.partial.zip")||name.equals("album-stage")
                    ||name.equals("completed.json.tmp")||(completed&&name.equals("chapters")))remove(file,owner,result,progress);
            }
        }catch(IOException|SecurityException error){result.errors++;}
        progress.update(result);return result;
    }
    private CacheCleanup(){}
}
