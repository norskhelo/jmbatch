package app.jmbatch.android;

import java.io.File;
import java.io.IOException;

/** Resolve only chapter one's committed first page, never a partial or later page. */
public final class DownloadCoverRules {
    public static final class Source {
        public final String path,format,stamp;
        Source(String path,String format,long modified,long size){
            this.path=path;this.format=format;stamp=format+"|"+path+"|"+modified+"|"+size;
        }
    }
    public static Source resolve(File work,String key,String status,String result,String format)throws IOException {
        return resolve(work,key,status,result,format,1);
    }
    public static Source resolve(File work,String key,String status,String result,String format,int firstChapter)throws IOException {
        if(!key.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"))throw new IOException("任务缓存标识无效");
        File cache=new File(work,key);
        if(!cache.getCanonicalFile().getParentFile().equals(work.getCanonicalFile()))throw new IOException("任务缓存路径无效");
        if(firstChapter<1)throw new IOException("章节序号无效");
        File first=new File(cache,String.format(java.util.Locale.ROOT,"images/%04d/00001.jpg",firstChapter));
        if(first.isFile())return new Source(first.getPath(),"image",first.lastModified(),first.length());
        if("done".equals(status)&&result!=null&&!result.isEmpty())return new Source(result,format,0,0);
        return null;
    }
}
