package app.jmbatch.android;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import android.util.AtomicFile;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** A durable export index; removing queue history does not discard favorites. */
public final class LibraryStore {
    private static LibraryStore instance;
    public static synchronized LibraryStore get(Context context) {
        if(instance==null)instance=new LibraryStore(context.getApplicationContext());
        return instance;
    }
    public static final class Entry {
        public final String id,title,uri,tree,label,format;
        public final boolean favorite;
        Entry(String id,String title,String uri,String tree,String label,String format,boolean favorite) {
            this.id=id;this.title=title;this.uri=uri;this.tree=tree;this.label=label;this.format=format;this.favorite=favorite;
        }
        Entry(JSONObject j)throws JSONException {
            this(j.getString("id"),j.getString("title"),j.getString("uri"),j.getString("tree"),j.getString("label"),j.getString("format"),j.getBoolean("favorite"));
            if(uri.isEmpty()||(!format.equals("images")&&!format.equals("pdf")&&!format.equals("zip")))throw new JSONException("漫画记录无效");
        }
        JSONObject json()throws JSONException {
            return new JSONObject().put("id",id).put("title",title).put("uri",uri).put("tree",tree).put("label",label).put("format",format).put("favorite",favorite);
        }
    }
    private final Context context;
    private final AtomicFile file;
    private LinkedHashMap<String,Entry> entries=new LinkedHashMap<>();
    private String loadError="";

    private LibraryStore(Context context) {
        this.context=context;file=new AtomicFile(new File(context.getFilesDir(),"library.json"));
        if(!file.getBaseFile().exists())return;
        try(InputStream input=file.openRead()) {
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();Core.copy(input,bytes);
            JSONObject root=new JSONObject(bytes.toString("UTF-8"));
            if(root.getInt("version")!=1)throw new IOException("不支持的列表格式");
            JSONArray array=root.getJSONArray("entries");
            for(int i=0;i<array.length();i++){Entry entry=new Entry(array.getJSONObject(i));entries.put(entry.uri,entry);}
        } catch(Exception error) {
            entries.clear();loadError="无法读取漫画库，原记录已保留。为保护数据，本次无法修改记录："+error.getMessage();
        }
    }
    private void writable()throws IOException {if(!loadError.isEmpty())throw new IOException(loadError);}
    private void persist(LinkedHashMap<String,Entry> next)throws IOException {
        writable();FileOutputStream output=null;
        try {
            JSONArray list=new JSONArray();for(Entry item:next.values())list.put(item.json());
            byte[] bytes=new JSONObject().put("version",1).put("entries",list).toString(2).getBytes(StandardCharsets.UTF_8);
            output=file.startWrite();output.write(bytes);file.finishWrite(output);entries=next;
        }catch(Exception error){if(output!=null)file.failWrite(output);throw new IOException("保存漫画列表失败："+error.getMessage(),error);}
    }
    public synchronized void sync(List<Store.Task> tasks)throws IOException {
        writable();LinkedHashMap<String,Entry> next=new LinkedHashMap<>(entries);boolean changed=false;
        for(Store.Task task:tasks) {
            if(!task.status.equals("done")||task.resultUri.isEmpty())continue;
            Entry old=next.get(task.resultUri);
            if(old!=null&&old.title.equals(task.title)&&old.id.equals(task.id))continue;
            next.put(task.resultUri,new Entry(task.id,task.title,task.resultUri,task.settings.outputUri,task.settings.outputLabel,task.settings.format,old!=null&&old.favorite));changed=true;
        }
        if(changed)persist(next);
    }
    public synchronized List<Entry> list(String query,boolean favorites)throws IOException {
        writable();ArrayList<Entry> result=new ArrayList<>();
        for(Entry item:entries.values())if(LibraryRules.matches(item.id,item.title,item.uri,item.favorite,query,favorites))result.add(item);
        Collections.reverse(result);return result;
    }
    public synchronized void favorite(Entry item)throws IOException {
        writable();Entry current=entries.get(item.uri);if(current==null)throw new IOException("记录已移除，请刷新");
        LinkedHashMap<String,Entry> next=new LinkedHashMap<>(entries);
        next.put(current.uri,new Entry(current.id,current.title,current.uri,current.tree,current.label,current.format,!current.favorite));persist(next);
    }
    private File appFile(Entry item)throws IOException {
        Uri uri=Uri.parse(item.uri);
        if(!"content".equals(uri.getScheme())||!(context.getPackageName()+".exports").equals(uri.getAuthority())||uri.getPathSegments().size()!=1)
            throw new IOException("导出文件地址无效");
        File root=context.getExternalFilesDir(null);if(root==null)root=context.getFilesDir();
        if(item.format.equals("images")){
            File album=AlbumStorage.local(context,uri);
            if(album==null||!album.isDirectory()||!album.getCanonicalFile().getParentFile().equals(new File(root,"exports").getCanonicalFile()))throw new IOException("图片目录不在保存目录中");
            return album;
        }
        return LibraryRules.ownedFile(new File(root,"exports"),uri.getLastPathSegment());
    }
    public void check(Entry item)throws IOException {
        if(item.tree.isEmpty()){appFile(item);if(item.format.equals("images"))try{AlbumStorage.load(context,Uri.parse(item.uri));}catch(Exception e){throw new IOException("图片目录校验失败",e);}return;}
        Uri uri=Uri.parse(item.uri), tree=Uri.parse(item.tree);
        if(!"content".equals(uri.getScheme())||!Objects.equals(tree.getAuthority(),uri.getAuthority())||
            !DocumentsContract.isTreeUri(uri)||!DocumentsContract.getTreeDocumentId(tree).equals(DocumentsContract.getTreeDocumentId(uri)))
            throw new IOException("文件地址与保存目录不匹配");
        try(Cursor cursor=context.getContentResolver().query(uri,new String[]{DocumentsContract.Document.COLUMN_DISPLAY_NAME,DocumentsContract.Document.COLUMN_MIME_TYPE},null,null,null)) {
            if(cursor==null)throw new IOException("存储服务未返回文件信息，请确认目录权限和存储状态");
            if(!cursor.moveToFirst())throw new FileNotFoundException("文件不存在或已移动");
            String name=cursor.getString(0),mime=cursor.getString(1);
            if(item.format.equals("images")){
                if(!DocumentsContract.Document.MIME_TYPE_DIR.equals(mime))throw new IOException("图片目录已不存在");
                try{AlbumStorage.load(context,uri);}catch(Exception e){throw new IOException("图片目录校验失败",e);}return;
            }
            if(name==null||!LibraryRules.supported(name)||DocumentsContract.Document.MIME_TYPE_DIR.equals(mime))throw new IOException("只允许操作 PDF / ZIP 文件，不允许删除目录");
        }
    }
    private void beginRemoval(Store store)throws IOException {
        synchronized(store){
            if(store.libraryBusy||store.running)throw new IOException("请先暂停下载队列，再删除文件或移除记录");
            for(Store.Task task:store.tasks)if(task.status.equals("running")||task.status.equals("resetting"))throw new IOException("下载任务正在停止，请稍后再试");
            store.libraryBusy=true;
        }
    }
    public void remove(Store store,Entry item,boolean delete)throws IOException {
        beginRemoval(store);
        try{removeOne(store,item,delete);}finally{store.libraryBusy=false;}
    }
    public BatchOperations.Result removeMany(Store store,List<Entry> selected,boolean delete,java.util.function.BooleanSupplier cancelled,java.util.function.BiConsumer<Integer,Integer> progress)throws IOException {
        beginRemoval(store);
        try{
            LinkedHashMap<String,Entry> unique=new LinkedHashMap<>();for(Entry item:selected)unique.put(item.uri,item);
            return BatchOperations.run(new ArrayList<>(unique.values()),item->removeOne(store,item,delete),cancelled,item->item.title,progress);
        }finally{store.libraryBusy=false;}
    }
    private void removeOne(Store store,Entry item,boolean delete)throws IOException {
        synchronized(this){writable();if(!entries.containsKey(item.uri))throw new IOException("记录已移除，请刷新");}
        if(delete){
            check(item);
            if(item.format.equals("images")){
                try{AlbumStorage.validateForDeletion(context,Uri.parse(item.uri));AlbumStorage.remove(context,Uri.parse(item.uri));}catch(Exception e){throw new IOException(e.getMessage(),e);}
            }
            else if(item.tree.isEmpty()){if(!appFile(item).delete())throw new IOException("删除失败，文件可能被占用或存储不可写");}
            else if(!DocumentsContract.deleteDocument(context.getContentResolver(),Uri.parse(item.uri)))throw new IOException("存储服务拒绝删除文件，请确认目录有写入权限");
        }
        try{
            synchronized(store){
                for(Store.Task task:store.tasks)if(task.resultUri.equals(item.uri)){
                    task.resultUri="";
                    if(delete){task.status="cancelled";task.phase="文件已删除，可重新下载";}
                }
                store.save();
            }
            synchronized(this){LinkedHashMap<String,Entry> next=new LinkedHashMap<>(entries);next.remove(item.uri);persist(next);}
        }catch(IOException failure){throw new IOException((delete?"文件已删除，但记录保存失败：":"记录保存失败：")+failure.getMessage(),failure);}
    }
    public synchronized int setFavorites(List<Entry> selected,boolean favorite)throws IOException {
        writable();LinkedHashMap<String,Entry> next=new LinkedHashMap<>(entries);Set<String> changed=new HashSet<>();
        for(Entry item:selected){
            Entry current=next.get(item.uri);if(current==null)throw new IOException("部分记录已移除，请刷新后重试");
            next.put(current.uri,new Entry(current.id,current.title,current.uri,current.tree,current.label,current.format,favorite));changed.add(current.uri);
        }
        if(!changed.isEmpty())persist(next);return changed.size();
    }
    private static String identity(Entry entry){
        Uri uri=Uri.parse(entry.uri);
        if(!entry.tree.isEmpty())return uri.getAuthority()+"|"+DocumentsContract.getDocumentId(uri);
        return entry.uri;
    }
    public synchronized int importFound(List<Entry> found)throws IOException {
        writable();LinkedHashMap<String,Entry> next=new LinkedHashMap<>(entries);Set<String> known=new HashSet<>();
        for(Entry entry:entries.values())known.add(identity(entry));
        int added=0;
        for(Entry entry:found)if(known.add(identity(entry))){next.put(entry.uri,entry);added++;}
        if(added>0)persist(next);return added;
    }
}
