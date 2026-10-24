package app.jmbatch.android;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import java.io.File;
import java.util.*;

/** Metadata is read off the UI thread; group priority and ascending order stay fixed. */
final class LibrarySort {
    static List<LibraryStore.Entry> sorted(Context c,List<LibraryStore.Entry> source,String mode)throws java.io.IOException {
        List<LibraryStore.Entry> result=new ArrayList<>(source);
        Map<String,Long> facts=new HashMap<>(),folders=new HashMap<>();
        if(!mode.equals("name")) {
            for(LibraryStore.Entry e:source) {
                if(e.isCollection())folders.put(e.uri,0L);
                else facts.put(e.uri,fact(c,e,mode));
            }
            // Include all members, not just the four-cover preview.
            if(!folders.isEmpty())for(LibraryStore.Entry e:LibraryStore.get(c).list("",false)) {
                if(!folders.containsKey(e.collection))continue;
                long value=Math.max(0,facts.computeIfAbsent(e.uri,key->fact(c,e,mode)));
                long previous=folders.get(e.collection);
                folders.put(e.collection,mode.equals("time")?Math.max(previous,value):previous+value);
            }
            facts.putAll(folders);
        }
        Comparator<LibraryStore.Entry> title=Comparator.comparing(e->e.title.toLowerCase(Locale.ROOT));
        Comparator<LibraryStore.Entry> within=mode.equals("name")?title:Comparator.<LibraryStore.Entry>comparingLong(e->facts.getOrDefault(e.uri,0L)).thenComparing(title);
        result.sort(Comparator.<LibraryStore.Entry>comparingInt(e->e.isCollection()?0:e.favorite?1:2).thenComparing(within));
        return result;
    }
    private static long fact(Context c,LibraryStore.Entry e,String mode) {
        try {
            if(mode.equals("chapters"))return e.chapterCount;
            File local=AlbumStorage.local(c,Uri.parse(e.uri));
            if(local!=null)return mode.equals("time")?local.lastModified():size(local);
            if(e.format.equals("images")&&mode.equals("size")) {
                long value=0;
                for(AlbumStorage.Image image:AlbumStorage.load(c,Uri.parse(e.uri)).images)value+=Math.max(0,image.size);
                return value;
            }
            try(Cursor cur=c.getContentResolver().query(Uri.parse(e.uri),new String[]{mode.equals("time")?"last_modified":"_size"},null,null,null)) {
                if(cur!=null&&cur.moveToFirst()&&!cur.isNull(0))return cur.getLong(0);
            }
            return 0;
        }catch(Exception ignored){return -1;}
    }
    private static long size(File file){if(!file.isDirectory())return file.length();long sum=0;File[] children=file.listFiles();if(children!=null)for(File child:children)if(!java.nio.file.Files.isSymbolicLink(child.toPath()))sum+=size(child);return sum;}
}
