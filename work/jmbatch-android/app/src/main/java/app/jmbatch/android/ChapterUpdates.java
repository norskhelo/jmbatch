package app.jmbatch.android;

import android.content.Context;
import android.util.AtomicFile;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;

/** Album-only checks. Only successful downloads advance the known catalogue. */
public final class ChapterUpdates {
    interface Fetch { List<ChapterRules.Chapter> get(String id,Store.Settings settings,String cookie,JmApi.Control control)throws Exception; }
    static List<ChapterRules.Chapter> fetch(String id,Store.Settings settings,String cookie,JmApi.Control control)throws Exception {
        if(!id.matches("[0-9]{1,10}"))throw new IOException("这条漫画记录没有有效的 JM 编号，无法检查更新。");
        JmApi api=new JmApi(settings,cookie,control);
        try{api.initialize();control.check();return ChapterSelection.catalog(api.detail("album",id),id);}
        finally{control.cancel("检查结束");}
    }
    static final class Result {
        final List<ChapterRules.Chapter> catalog,fresh;final boolean initialized;
        Result(List<ChapterRules.Chapter> catalog,List<ChapterRules.Chapter> fresh,boolean initialized){this.catalog=catalog;this.fresh=fresh;this.initialized=initialized;}
    }
    private static AtomicFile file(Context context){return new AtomicFile(new File(context.getFilesDir(),"chapter-updates.json"));}
    private static JSONObject read(Context context)throws Exception {
        AtomicFile file=file(context);if(!file.getBaseFile().exists())return new JSONObject();
        try(InputStream in=file.openRead()){ByteArrayOutputStream out=new ByteArrayOutputStream();Core.copy(in,out);return new JSONObject(out.toString("UTF-8"));}
    }
    private static void write(Context context,JSONObject data)throws Exception {
        AtomicFile file=file(context);FileOutputStream out=null;
        try{out=file.startWrite();out.write(data.toString().getBytes(StandardCharsets.UTF_8));file.finishWrite(out);}
        catch(Exception error){if(out!=null)file.failWrite(out);throw error;}
    }
    private static Set<String> ids(JSONObject item,String key)throws Exception {
        Set<String> ids=new TreeSet<>();JSONArray array=item.optJSONArray(key);
        if(array!=null)for(int i=0;i<array.length();i++)ids.add(array.getString(i));return ids;
    }
    static synchronized void record(Context context,List<Store.Task> tasks)throws IOException {
        try{
            JSONObject data=read(context);boolean changed=false;
            for(Store.Task task:tasks){
                if(!task.status.equals("done")||task.resultUri.isEmpty())continue;
                JSONObject item=data.optJSONObject(task.id);if(item==null)item=new JSONObject();
                String key=task.chapterOptions.isEmpty()?"anchors":"known";Set<String> ids=ids(item,key);int before=ids.size();
                for(ChapterRules.Chapter c:task.chapterOptions.isEmpty()?task.selectedChapters:task.chapterOptions)ids.add(c.id);
                if(ids.size()!=before){item.put(key,new JSONArray(ids));data.put(task.id,item);changed=true;}
            }
            if(changed)write(context,data);
        }catch(Exception error){throw new IOException("章节更新记录保存失败："+error.getMessage(),error);}
    }
    static synchronized Result compare(Context context,String id,List<ChapterRules.Chapter> catalog)throws Exception {
        ChapterRules.resolve(catalog,Collections.emptyList(),true); // validate unique IDs and nonempty catalogue
        JSONObject data=read(context),item=data.optJSONObject(id);if(item==null)item=new JSONObject();
        Set<String> known=ids(item,"known");boolean initialized=false;
        if(known.isEmpty()){
            Set<String> anchors=ids(item,"anchors");int last=-1;
            for(int i=0;i<catalog.size();i++)if(anchors.contains(catalog.get(i).id))last=i;
            initialized=last<0;if(initialized)last=catalog.size()-1;
            for(int i=0;i<=last;i++)known.add(catalog.get(i).id);
            item.put("known",new JSONArray(known));data.put(id,item);write(context,data);
        }
        List<ChapterRules.Chapter> fresh=new ArrayList<>();for(ChapterRules.Chapter c:catalog)if(!known.contains(c.id))fresh.add(c);
        return new Result(new ArrayList<>(catalog),fresh,initialized);
    }
}
