package app.jmbatch.android;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import java.io.File;
import java.util.*;

/** Folders, favorites, then comics; IDs ascending, metadata largest/newest first. */
final class LibrarySort {
    static List<LibraryStore.Entry> sorted(Context c,List<LibraryStore.Entry> source,String mode)throws java.io.IOException {
        List<LibraryStore.Entry> result=new ArrayList<>(source);
        Map<String,Long> facts=new HashMap<>(),folders=new HashMap<>();
        if(!mode.equals("name")&&!mode.equals("number")) {
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
        Map<LibraryStore.Entry,String[]> names=new IdentityHashMap<>();
        for(LibraryStore.Entry e:source)names.put(e,NameSort.key(e.title));
        Comparator<LibraryStore.Entry> title=(a,b)->NameSort.compare(names.get(a),names.get(b));
        Comparator<LibraryStore.Entry> within=mode.equals("name")?title:Comparator.<LibraryStore.Entry>comparingLong(e->facts.getOrDefault(e.uri,0L)).reversed().thenComparing(title);
        if(mode.equals("number")) {
            Map<LibraryStore.Entry,String> numbers=new IdentityHashMap<>();
            for(LibraryStore.Entry e:source)numbers.put(e,e.isCollection()?null:number(e.id));
            within=((Comparator<LibraryStore.Entry>)(a,b)->compareNumbers(numbers.get(a),numbers.get(b))).thenComparing(title);
        }
        result.sort(Comparator.<LibraryStore.Entry>comparingInt(e->e.isCollection()?0:e.favorite?1:2).thenComparing(within));
        return result;
    }
    private static String number(String value) {
        if(value==null||value.isEmpty())return null;
        for(int i=0;i<value.length();i++)if(value.charAt(i)<'0'||value.charAt(i)>'9')return null;
        int start=0;while(start<value.length()-1&&value.charAt(start)=='0')start++;
        return value.substring(start);
    }
    private static int compareNumbers(String a,String b) {
        if(a==null)return b==null?0:1;
        if(b==null)return -1;
        int length=Integer.compare(a.length(),b.length());
        return length!=0?length:a.compareTo(b);
    }
    private static long fact(Context c,LibraryStore.Entry e,String mode) {
        try {
            if(mode.equals("chapters"))return e.chapterCount;
            if(mode.equals("size"))return e.sizeBytes;
            File local=AlbumStorage.local(c,Uri.parse(e.uri));
            if(local!=null)return local.lastModified();
            try(Cursor cur=c.getContentResolver().query(Uri.parse(e.uri),new String[]{"last_modified"},null,null,null)) {
                if(cur!=null&&cur.moveToFirst()&&!cur.isNull(0))return cur.getLong(0);
            }
            return 0;
        }catch(Exception ignored){return -1;}
    }
}
