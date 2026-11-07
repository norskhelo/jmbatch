package app.jmbatch.android;

import android.content.Context;
import android.util.AtomicFile;
import java.io.*;
import android.net.Uri;
import java.util.*;
import org.json.*;

/** Album-only checks. Only successful downloads advance the known catalogue. */
public final class ChapterUpdates {
    interface Session { List<ChapterRules.Chapter> get(String id)throws Exception; }
    interface Open { Session open(Store.Settings settings,String cookie,JmApi.Control control)throws Exception; }
    static Session open(Store.Settings settings,String cookie,JmApi.Control control)throws Exception {
        control.check();
        JmApi api=new JmApi(settings,cookie,control);
        api.initialize();
        return id->{
            control.check();
            if(!id.matches("[0-9]{1,10}"))throw new IOException("漫画编号无效");
            return ChapterSelection.catalog(api.detail("album",id),id);
        };
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
    static final class History {
        static final History EMPTY=new History(Collections.emptySet(),Collections.emptySet());
        final Set<String> known,anchors;
        History(Set<String> known,Set<String> anchors){
            this.known=Collections.unmodifiableSet(known);this.anchors=Collections.unmodifiableSet(anchors);
        }
        private static Set<String> ids(JSONArray array)throws JSONException {
            Set<String> ids=new TreeSet<>();
            if(array!=null)for(int i=0;i<array.length();i++)ids.add(array.getString(i));
            return ids;
        }
        static History from(JSONObject item)throws JSONException {
            return item==null?EMPTY:new History(ids(item.optJSONArray("known")),ids(item.optJSONArray("anchors")));
        }
        JSONObject json()throws JSONException {
            return new JSONObject().put("known",new JSONArray(known)).put("anchors",new JSONArray(anchors));
        }
        boolean empty(){return known.isEmpty()&&anchors.isEmpty();}
        boolean single(){return known.size()==1&&known.containsAll(anchors);}
        History record(Store.Task task){
            boolean hasCatalog=!task.chapterOptions.isEmpty();
            Set<String> previous=hasCatalog?known:anchors,added=null;
            for(ChapterRules.Chapter chapter:hasCatalog?task.chapterOptions:task.selectedChapters){
                if(previous.contains(chapter.id))continue;
                if(added==null)added=new TreeSet<>(previous);
                added.add(chapter.id);
            }
            if(added==null)return this;
            return hasCatalog?new History(added,anchors):new History(known,added);
        }
    }

    // Legacy exports stored chapter numbers in folder names and one catalogue per JM ID.
    // Read only the first directory level. A flat, single-chapter folder has no ordinal.
    private static int lastFolderChapter(Context context,LibraryStore.Entry book)throws IOException {
        int last=0;
        for(AlbumStorage.Node node:AlbumStorage.children(context,Uri.parse(book.uri))){
            if(node.directory&&node.name.matches("[0-9]{4,8}"))last=Math.max(last,Integer.parseInt(node.name));
        }
        return last;
    }

    private static History resolve(Context context,LibraryStore.Entry book,History legacy,List<ChapterRules.Chapter> catalog)throws Exception {
        Set<String> anchors=book.history.anchors;
        int last=-1;
        if(anchors.isEmpty()&&!legacy.known.isEmpty()){
            if(book.format.equals("images")&&legacy.known.size()>1&&book.chapterCount<legacy.known.size()){
                int number=lastFolderChapter(context,book);
                if(number>0){
                    // Ignore genuinely new insertions when mapping the saved chapter numbers.
                    List<String> oldOrder=new ArrayList<>();
                    for(ChapterRules.Chapter c:catalog)if(legacy.known.contains(c.id))oldOrder.add(c.id);
                    if(oldOrder.size()!=legacy.known.size()||number>oldOrder.size())
                        throw new IOException("旧章节目录已变化，无法核对原图片文件夹的章节位置");
                    return new History(new TreeSet<>(oldOrder.subList(0,number)),Collections.emptySet());
                }
            }
            return legacy;
        }
        if(anchors.isEmpty())anchors=legacy.anchors;
        for(int i=0;i<catalog.size();i++)if(anchors.contains(catalog.get(i).id))last=i;
        if(last<0)last=catalog.size()-1;
        Set<String> known=new TreeSet<>();
        for(int i=0;i<=last;i++)known.add(catalog.get(i).id);
        return new History(known,anchors);
    }

    static Result compare(Context context,String id,List<ChapterRules.Chapter> catalog)throws Exception {
        ChapterRules.resolve(catalog,Collections.emptyList(),true);
        LibraryStore library=LibraryStore.get(context);
        List<LibraryStore.Entry> copies=library.albumEntries(id);
        if(copies.isEmpty())throw new IOException("原漫画已移除，请刷新漫画库");
        Set<String> known=new HashSet<>();History legacy=null;
        boolean initialized=true;
        boolean hasHistory=false;
        for(LibraryStore.Entry copy:copies)if(!copy.history.empty()){hasHistory=true;break;}
        for(LibraryStore.Entry book:copies){
            History history=book.history;
            if(history.known.isEmpty()){
                if(legacy==null)legacy=History.from(read(context).optJSONObject(id));
                // An untracked import must not mask updates confirmed by a tracked sibling.
                if(history.empty()&&hasHistory&&legacy.empty())continue;
                if(!history.empty()||!legacy.empty())initialized=false;
                history=resolve(context,book,legacy,catalog);
                library.rememberChapters(book,history);
            }else initialized=false;
            known.addAll(history.known);
        }
        List<ChapterRules.Chapter> fresh=new ArrayList<>();
        for(ChapterRules.Chapter c:catalog)if(!known.contains(c.id))fresh.add(c);
        return new Result(new ArrayList<>(catalog),fresh,initialized);
    }
}
