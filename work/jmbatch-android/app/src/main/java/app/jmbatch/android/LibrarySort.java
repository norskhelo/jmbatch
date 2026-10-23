package app.jmbatch.android;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import java.io.File;
import java.util.*;

/** Metadata is read off the UI thread; stable sort keeps favorite order. */
final class LibrarySort {
    static List<LibraryStore.Entry> sorted(Context c,List<LibraryStore.Entry> source,String mode,boolean reverse){
        List<LibraryStore.Entry> favorites=new ArrayList<>(),rest=new ArrayList<>();Map<String,Long> facts=new HashMap<>();
        for(LibraryStore.Entry e:source){if(e.favorite){favorites.add(e);continue;}rest.add(e);if(mode.equals("name")||e.isCollection())continue;
            long value=0;try{if(mode.equals("chapters")){value=ChapterDeletion.inspect(c,e,()->false).counts.size();}
                else{File local=AlbumStorage.local(c,Uri.parse(e.uri));if(local!=null)value=mode.equals("time")?local.lastModified():size(local);else if(e.format.equals("images")&&mode.equals("size")){for(AlbumStorage.Image image:AlbumStorage.load(c,Uri.parse(e.uri)).images)value+=Math.max(0,image.size);}else try(Cursor cur=c.getContentResolver().query(Uri.parse(e.uri),new String[]{mode.equals("time")?"last_modified":"_size"},null,null,null)){if(cur!=null&&cur.moveToFirst()&&!cur.isNull(0))value=cur.getLong(0);}}
            }catch(Exception ignored){value=-1;}facts.put(e.uri,value);
        }
        Comparator<LibraryStore.Entry> comparator=mode.equals("name")?Comparator.comparing(e->e.title.toLowerCase(Locale.ROOT)):Comparator.comparingLong(e->facts.getOrDefault(e.uri,0L));if(reverse)comparator=comparator.reversed();rest.sort(comparator);favorites.addAll(rest);return favorites;
    }
    private static long size(File file){if(!file.isDirectory())return file.length();long sum=0;File[] children=file.listFiles();if(children!=null)for(File child:children)if(!java.nio.file.Files.isSymbolicLink(child.toPath()))sum+=size(child);return sum;}
}
