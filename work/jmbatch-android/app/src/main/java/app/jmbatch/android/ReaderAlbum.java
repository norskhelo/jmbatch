package app.jmbatch.android;

import android.content.Context;
import android.net.Uri;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Reader-only lazy validation. Export and delete retain AlbumStorage's full validation. */
public final class ReaderAlbum {
    public interface Progress { void update(String text); }
    private final Context context;
    private final Uri folder;
    private final File local;
    private final AlbumStorage.Check cancelled;
    private final List<Record> pages=new ArrayList<>();
    private Map<String,AlbumStorage.Node> roots;
    // At most three directory listings; large books do not retain every provider cursor's data.
    private final LinkedHashMap<Integer,Map<String,AlbumStorage.Node>> directories=new LinkedHashMap<>(4,.75f,true);
    private final BitSet remaining=new BitSet();
    private final Map<Integer,String> failures=new HashMap<>();
    public int[] chapters,pageNumbers;
    private boolean flat;
    private static final class Record {
        final int chapter,page;final String name;final long size;
        Uri uri;
        Record(int c,int p,String n,long s){chapter=c;page=p;name=n;size=s;}
    }
    public ReaderAlbum(Context context,Uri folder,AlbumStorage.Check cancelled,Progress progress)throws Exception {
        this.context=context;this.folder=folder;this.cancelled=cancelled;
        local=AlbumStorage.local(context,folder);cancelled.run();progress.update("正在读取页面索引…");
        File stored=AlbumStorage.index(context,folder);
        // App-owned albums can read the manifest directly without stat-ing every image.
        Uri marker=null;
        if(local!=null){
            if(!local.isDirectory())throw new IOException("图片目录不可用");
            File file=new File(local,AlbumRules.MANIFEST);
            if(file.exists())marker=ExportProvider.uri(context,file);
        }else{
            roots=nodes(folder);
            AlbumStorage.Node node=roots.get(AlbumRules.MANIFEST);
            if(node!=null&&!node.directory)marker=node.uri;
        }
        boolean loaded=false;Exception problem=null;
        if(marker!=null)try(InputStream stream=AlbumStorage.open(context,marker)){parse(read(stream));loaded=true;}catch(Exception error){cancelled.run();problem=error;}
        if(!loaded&&stored.isFile())try(InputStream stream=new FileInputStream(stored)){parse(read(stream));loaded=true;}catch(Exception error){cancelled.run();problem=error;}
        if(!loaded){
            progress.update("正在首次建立页面索引…");
            try{
                JSONObject metadata=AlbumStorage.scan(context,folder,cancelled,count->progress.update("正在建立页面索引：已发现 "+count+" 页"));
                parse(metadata);
                // Reuse recovered/scanned metadata on the next open, including old albums.
                try{AlbumStorage.remember(context,folder,metadata);}catch(Exception ignored){}
            }catch(Exception error){if(problem!=null)error.addSuppressed(problem);throw error;}
        }
        chapters=new int[pages.size()];pageNumbers=new int[pages.size()];
        for(int i=0;i<pages.size();i++){chapters[i]=pages.get(i).chapter;pageNumbers[i]=pages.get(i).page;}
        remaining.set(0,pages.size());cancelled.run();
    }
    private JSONObject read(InputStream stream)throws Exception {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int count;
        while((count=stream.read(buffer))!=-1){cancelled.run();if(bytes.size()+count>8*1024*1024)throw new IOException("图片索引过大");bytes.write(buffer,0,count);}
        return new JSONObject(new String(bytes.toByteArray(),StandardCharsets.UTF_8));
    }
    private void parse(JSONObject metadata)throws Exception {
        pages.clear();int version=metadata.getInt("version");
        if((version!=1&&version!=AlbumRules.LAYOUT_VERSION)||!metadata.getString("id").matches("[0-9]{1,10}"))throw new IOException("图片索引版本无效");
        JSONArray entries=metadata.getJSONArray("entries");
        if(entries.length()<1||entries.length()>ArchivePages.MAX_PAGES)throw new IOException("图片数量无效");
        Set<Integer> ids=new HashSet<>();for(int i=0;i<entries.length();i++){cancelled.run();ids.add(entries.getJSONObject(i).getInt("chapter"));}
        flat=version==AlbumRules.LAYOUT_VERSION&&ids.size()==1;
        Set<String> seen=new HashSet<>();
        for(int i=0;i<entries.length();i++){
            cancelled.run();JSONObject item=entries.getJSONObject(i);int c=item.getInt("chapter"),p=item.getInt("page");
            String name=version==1?AlbumRules.imageName(c,p):AlbumRules.imageName(c,p,ids.size());long size=item.getLong("size");
            if(!name.equals(item.getString("file"))||!seen.add(name)||size<=0||size>ArchivePages.MAX_IMAGE_BYTES)throw new IOException("图片索引路径、顺序或大小无效");
            pages.add(new Record(c,p,name,size));
        }
        pages.sort(Comparator.comparingInt((Record p)->p.chapter).thenComparingInt(p->p.page));
    }
    private Map<String,AlbumStorage.Node> nodes(Uri directory)throws Exception {
        cancelled.run();Map<String,AlbumStorage.Node> result=new HashMap<>();
        for(AlbumStorage.Node node:AlbumStorage.children(context,directory)){
            cancelled.run();if(result.put(node.name,node)!=null)throw new IOException("目录含同名文件");
        }
        return result;
    }
    public AlbumStorage.Image image(int index)throws Exception {
        cancelled.run();Record record=pages.get(index);
        if(remaining.get(index)||failures.containsKey(index))verify(index);
        String failure=failures.get(index);if(failure!=null)throw new IOException(failure);
        return new AlbumStorage.Image(record.chapter,record.page,record.uri,record.size,record.name);
    }
    private void verify(int index)throws Exception {
        cancelled.run();Record record=pages.get(index);
        try{
            if(local!=null){
                Uri uri=ExportProvider.uri(context,new File(local,record.name));File file=AlbumStorage.local(context,uri);
                if(file==null||!file.isFile()||file.length()!=record.size)throw new IOException("图片缺失或大小变化："+record.name);
                record.uri=uri;
            }else{
                Map<String,AlbumStorage.Node> children=directories.get(record.chapter);
                if(children==null){
                    if(roots==null)roots=nodes(folder);
                    if(flat)children=roots;
                    else{
                        AlbumStorage.Node chapter=roots.get(record.name.split("/")[0]);
                        if(chapter==null||!chapter.directory)throw new IOException("章节目录缺失："+record.chapter);
                        children=nodes(chapter.uri);
                    }
                    directories.put(record.chapter,children);
                    while(directories.size()>3)directories.remove(directories.keySet().iterator().next());
                }
                AlbumStorage.Node node=children.get(flat?record.name:record.name.split("/")[1]);
                if(node==null||node.directory||node.size>=0&&node.size!=record.size)throw new IOException("图片缺失或大小变化："+record.name);
                record.uri=node.uri;
            }
            failures.remove(index);
        }catch(Exception error){cancelled.run();failures.put(index,error.getMessage()==null?"图片无法读取":error.getMessage());}
        remaining.clear(index);
    }
    public void retry(int index){
        Record record=pages.get(index);remaining.set(index);failures.remove(index);record.uri=null;
        directories.remove(record.chapter);if(local==null)roots=null;
    }
    public boolean pending(){return !remaining.isEmpty();}
    public int checked(){return pages.size()-remaining.cardinality();}
    public int failed(){return failures.size();}
    public int next(int anchor){
        anchor=Math.max(0,Math.min(pages.size()-1,anchor));
        for(int i=anchor;i<Math.min(pages.size(),anchor+5);i++)if(remaining.get(i))return i;
        if(anchor>0&&remaining.get(anchor-1))return anchor-1;
        int index=remaining.nextSetBit(anchor+5);return index>=0?index:remaining.nextSetBit(0);
    }
    /** One bounded slice, with navigation priority recomputed before the next slice. */
    public Map<Integer,String> check(int anchor)throws Exception {
        Map<Integer,String> errors=new HashMap<>();long end=System.nanoTime()+12_000_000L;
        for(int count=0;count<16;count++){
            cancelled.run();int index=next(anchor);if(index<0)break;
            verify(index);if(failures.containsKey(index))errors.put(index,failures.get(index));
            if(System.nanoTime()>=end)break;
        }
        return errors;
    }
}
