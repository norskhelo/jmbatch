package app.jmbatch.android;

import android.content.Context;
import android.net.Uri;
import java.io.InterruptedIOException;
import java.util.*;
import java.util.function.BooleanSupplier;
import java.util.function.Consumer;

/** Export each comic atomically; keep completed outputs when a later comic fails or is cancelled. */
public final class BatchExporter {
    private BatchExporter() {}
    public static final class Result {
        public int succeeded,failed,unprocessed;
        public boolean stopped;
        public final List<LibraryStore.Entry> files=new ArrayList<>();
        public final List<String> errors=new ArrayList<>(),warnings=new ArrayList<>();
        public String summary(){return (stopped?"已停止导出":"导出结束")+"：成功 "+succeeded+" 本，失败 "+failed+" 本，未处理 "+unprocessed+" 本；已保存 "+files.size()+" 项。";}
    }
    public static Result export(Context context,List<LibraryStore.Entry> selection,String tree,String label,String format,
                                boolean numeric,boolean split,BooleanSupplier cancelled,Consumer<String> progress){
        Map<String,LibraryStore.Entry> unique=new LinkedHashMap<>();
        for(LibraryStore.Entry entry:selection)unique.putIfAbsent(entry.uri,entry);
        List<LibraryStore.Entry> entries=new ArrayList<>(unique.values());Result result=new Result();
        for(int index=0;index<entries.size();index++){
            if(cancelled.getAsBoolean()){result.stopped=true;break;}
            LibraryStore.Entry entry=entries.get(index);
            String title=(entry.id.isEmpty()?"":"JM"+entry.id+" · ")+entry.title;
            String prefix="第 "+(index+1)+"/"+entries.size()+" 本 · "+title+"\n";
            try{
                progress.accept(prefix+"正在读取…");
                List<LibraryStore.Entry> files=AlbumExporter.export(context,Uri.parse(entry.uri),entry.format,entry.id,entry.title,
                    tree,label,format,numeric&&!format.equals("images"),true,split&&format.equals("pdf")&&!entry.format.equals("pdf"),
                    ()->{if(cancelled.getAsBoolean())throw new InterruptedIOException("导出已取消，源文件保留");},
                    message->progress.accept(prefix+message));
                result.files.addAll(files);result.succeeded++;
            }catch(Exception error){
                if(error instanceof InterruptedIOException&&cancelled.getAsBoolean()){result.stopped=true;break;}
                result.failed++;result.errors.add(title+"："+(error.getMessage()==null?error.getClass().getSimpleName():error.getMessage()));
            }
            progress.accept("已处理 "+(result.succeeded+result.failed)+"/"+entries.size()+" 本 · 成功 "+result.succeeded+" 本，失败 "+result.failed+" 本");
        }
        result.unprocessed=entries.size()-result.succeeded-result.failed;
        if(!result.files.isEmpty())try{
            progress.accept("正在将已导出的漫画加入漫画库…");LibraryStore.get(context).importFound(result.files);
        }catch(Exception error){result.warnings.add("文件已保存，但漫画库更新失败："+error.getMessage()+"。可稍后扫描导出目录重新导入。");}
        return result;
    }
}
