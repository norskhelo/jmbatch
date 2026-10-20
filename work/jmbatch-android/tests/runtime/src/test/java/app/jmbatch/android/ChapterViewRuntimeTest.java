package app.jmbatch.android;

import android.content.*;
import android.graphics.Bitmap;
import android.os.Looper;
import android.view.*;
import android.widget.*;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.*;
import org.robolectric.android.controller.ActivityController;
import java.io.*;
import java.nio.file.*;
import java.lang.reflect.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},qualifiers="w360dp-h800dp-mdpi",shadows={CollectionRuntimeTest.WindowsAtomicRename.class})
@LooperMode(LooperMode.Mode.PAUSED)
public class ChapterViewRuntimeTest {
    Context context;LibraryStore.Entry entry;ActivityController<ReaderActivity> controller;
    static Object get(Object target,String name)throws Exception {Field f=target.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(target);}
    static Object call(Object target,String name,Object...args)throws Exception {
        Method m=args.length==0?target.getClass().getDeclaredMethod(name):target.getClass().getDeclaredMethod(name,int.class);
        m.setAccessible(true);return m.invoke(target,args);
    }
    @Before public void setup()throws Exception {
        context=RuntimeEnvironment.getApplication();new android.app.Instrumentation().setInTouchMode(true);
        for(Class<?> type:new Class<?>[]{Store.class,LibraryStore.class}){Field f=type.getDeclaredField("instance");f.setAccessible(true);f.set(null,null);}
        for(String name:new String[]{"queue.json","library.json"})Files.deleteIfExists(new File(context.getFilesDir(),name).toPath());
        File root=new File(AlbumStorage.root(context),"JM123-chapters-1234abcd");root.mkdirs();
        ByteArrayOutputStream out=new ByteArrayOutputStream();Bitmap b=Bitmap.createBitmap(400,700,Bitmap.Config.ARGB_8888);b.eraseColor(-1);b.compress(Bitmap.CompressFormat.JPEG,80,out);b.recycle();byte[] bytes=out.toByteArray();
        JSONArray entries=new JSONArray();int[] numbers={2,5,9},counts={3,2,1};
        for(int c=0;c<3;c++)for(int p=1;p<=counts[c];p++){
            String name=String.format("%04d/%05d.jpg",numbers[c],p);File image=new File(root,name);image.getParentFile().mkdirs();Files.write(image.toPath(),bytes);
            entries.put(new JSONObject().put("chapter",numbers[c]).put("page",p).put("file",name).put("size",bytes.length));
        }
        Files.write(new File(root,AlbumRules.MANIFEST).toPath(),new JSONObject().put("version",2).put("id","123").put("title","Synthetic chapters").put("entries",entries).toString().getBytes("UTF-8"));
        entry=new LibraryStore.Entry("123","Synthetic chapters",ExportProvider.uri(context,root).toString(),"","","images",false);
    }
    void frame()throws Exception {((ExecutorService)get(controller.get(),"worker")).submit(()->{}).get(10,TimeUnit.SECONDS);shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(20));}
    void settle()throws Exception {for(int i=0;i<35;i++)frame();}
    ReaderActivity open(int mode,String layout)throws Exception {
        Store.get(context).settings.chapterViewMode=mode;
        context.getSharedPreferences("reader-history",0).edit().putString(entry.uri,new JSONObject().put("page",4).put("mode",layout).put("bookmarks",new JSONArray(Arrays.asList(0,4,5))).toString()).commit();
        controller=Robolectric.buildActivity(ReaderActivity.class,new Intent(context,ReaderActivity.class).putExtra("entry",entry.json().toString()));
        controller.get().setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup().visible();settle();return controller.get();
    }
    @After public void close()throws Exception {
        if(controller!=null){ReaderActivity a=controller.get();controller.pause().stop().destroy();controller=null;((ExecutorService)get(a,"worker")).awaitTermination(10,TimeUnit.SECONDS);shadowOf(Looper.getMainLooper()).idle();}
    }
    @Test public void settingsDefaultRoundTripAndDiskRestore()throws Exception {
        assertEquals(1,new Store.Settings(new JSONObject()).chapterViewMode);
        Store store=Store.get(context);store.settings.chapterViewMode=2;store.save();
        Field f=Store.class.getDeclaredField("instance");f.setAccessible(true);f.set(null,null);
        assertEquals(2,Store.get(context).settings.chapterViewMode);
        for(int invalid:new int[]{0,3}){try{new Store.Settings(new JSONObject().put("chapterViewMode",invalid));fail();}catch(IllegalArgumentException expected){}}
    }
    @Test public void scrollingOnlyContainsCurrentChapterAndSwitchesExplicitly()throws Exception {
        ReaderActivity a=open(2,"scroll");ListView list=(ListView)get(a,"list");
        assertEquals(2,list.getCount());assertEquals(1,list.getFirstVisiblePosition());assertEquals(4,get(a,"page"));
        call(a,"step",1);settle();assertEquals(4,get(a,"page"));
        call(a,"go",3);settle();call(a,"step",-1);settle();assertEquals(3,get(a,"page"));
        call(a,"chapterStep",1);settle();assertEquals(5,get(a,"page"));assertEquals(1,((ListView)get(a,"list")).getCount());
        call(a,"step",1);settle();assertEquals(5,get(a,"page"));
        call(a,"go",0);settle();assertEquals(3,((ListView)get(a,"list")).getCount());
        call(a,"go",4);settle();assertEquals(4,get(a,"page"));assertEquals(new TreeSet<>(Arrays.asList(0,4,5)),get(a,"marks"));
        call(a,"toggleMode");settle();assertEquals(4,((ReaderPager)get(a,"pager")).displayed());
        call(a,"toggleMode");settle();assertEquals(1,((ListView)get(a,"list")).getFirstVisiblePosition());
        close();Store.get(context).settings.chapterViewMode=1;
        controller=Robolectric.buildActivity(ReaderActivity.class,new Intent(context,ReaderActivity.class).putExtra("entry",entry.json().toString()));
        controller.get().setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup().visible();settle();
        assertEquals(6,((ListView)get(controller.get(),"list")).getCount());assertEquals(4,get(controller.get(),"page"));
    }
    @Test public void pagedGesturesRespectBothChapterBoundaries()throws Exception {
        ReaderActivity a=open(2,"paged");ReaderPager pager=(ReaderPager)get(a,"pager");assertEquals(4,pager.displayed());
        pager.go(100);settle();assertEquals(4,pager.displayed());
        swipe(pager,600,10);settle();assertEquals(4,pager.displayed());
        pager.go(-1);settle();assertEquals(3,pager.displayed());
        swipe(pager,10,600);settle();assertEquals(3,pager.displayed());
        call(a,"go",5);settle();assertEquals(5,((ReaderPager)get(a,"pager")).displayed());
        call(a,"go",0);settle();assertEquals(0,((ReaderPager)get(a,"pager")).displayed());
        assertEquals(new TreeSet<>(Arrays.asList(0,4,5)),get(a,"marks"));
    }
    @Test public void mergedModeContinuesAcrossChapterBoundary()throws Exception {
        ReaderActivity a=open(1,"paged");call(a,"step",1);settle();assertEquals(5,get(a,"page"));assertEquals(0,get(a,"scopeStart"));assertEquals(6,get(a,"scopeEnd"));
    }
    void swipe(ReaderPager pager,int from,int to) {
        long now=android.os.SystemClock.uptimeMillis();
        for(int action:new int[]{MotionEvent.ACTION_DOWN,MotionEvent.ACTION_MOVE,MotionEvent.ACTION_UP}){
            MotionEvent e=MotionEvent.obtain(now,now+(action==0?0:100),action,action==0?from:to,200,0);pager.onTouchEvent(e);e.recycle();
        }
    }
}
