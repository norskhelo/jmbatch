package app.jmbatch.android;

import android.app.AlertDialog;
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
public class BookmarkRuntimeTest {
    Context context;LibraryStore.Entry entry;ActivityController<ReaderActivity> controller;CountDownLatch unblock;
    static Object get(Object target,String name)throws Exception {Field f=target.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(target);}
    static Object call(Object target,String name,Object...args)throws Exception {
        Method m=args.length==0?target.getClass().getDeclaredMethod(name):target.getClass().getDeclaredMethod(name,int.class);
        m.setAccessible(true);return m.invoke(target,args);
    }
    @Before public void setup()throws Exception {
        context=RuntimeEnvironment.getApplication();new android.app.Instrumentation().setInTouchMode(true);
        for(Class<?> type:new Class<?>[]{Store.class,LibraryStore.class}){Field f=type.getDeclaredField("instance");f.setAccessible(true);f.set(null,null);}
        for(String name:new String[]{"queue.json","library.json"})Files.deleteIfExists(new File(context.getFilesDir(),name).toPath());
        File root=new File(AlbumStorage.root(context),"JM123-bookmarks-"+UUID.randomUUID().toString().substring(0,8));assertTrue(root.mkdirs());
        byte[][] images=new byte[3][];int[] heights={100,700,1400};
        for(int i=0;i<3;i++){ByteArrayOutputStream out=new ByteArrayOutputStream();Bitmap b=Bitmap.createBitmap(400,heights[i],Bitmap.Config.ARGB_8888);b.eraseColor(0xff884400+i*60);b.compress(Bitmap.CompressFormat.JPEG,80,out);b.recycle();images[i]=out.toByteArray();}
        JSONArray entries=new JSONArray();
        for(int i=0;i<61;i++){
            int chapter=i/20+1,p=i%20+1;String name=String.format("%04d/%05d.jpg",chapter,p);File image=new File(root,name);image.getParentFile().mkdirs();Files.write(image.toPath(),images[i%3]);
            entries.put(new JSONObject().put("chapter",chapter).put("page",p).put("file",name).put("size",images[i%3].length));
        }
        Files.write(new File(root,AlbumRules.MANIFEST).toPath(),new JSONObject().put("version",2).put("id","123").put("title","Synthetic bookmarks").put("entries",entries).toString().getBytes("UTF-8"));
        entry=new LibraryStore.Entry("123","Synthetic bookmarks",ExportProvider.uri(context,root).toString(),"","","images",false);
    }
    void frame()throws Exception {((ExecutorService)get(controller.get(),"worker")).submit(()->{}).get(10,TimeUnit.SECONDS);shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(20));}
    void settle()throws Exception {for(int i=0;i<45;i++)frame();}
    ReaderActivity open(int mode,String layout)throws Exception {
        Store.get(context).settings.chapterViewMode=mode;
        context.getSharedPreferences("reader-history",0).edit().putString(entry.uri,new JSONObject().put("page",0).put("mode",layout).put("bookmarks",new JSONArray(Arrays.asList(3,40,58,60))).toString()).commit();
        controller=Robolectric.buildActivity(ReaderActivity.class,new Intent(context,ReaderActivity.class).putExtra("entry",entry.json().toString()));
        controller.get().setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup().visible();settle();return controller.get();
    }
    void bookmark(int index)throws Exception {
        call(controller.get(),"bookmarks");shadowOf(Looper.getMainLooper()).idle();
        AlertDialog menu=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();
        shadowOf(menu).clickOnItem(index);shadowOf(Looper.getMainLooper()).idle();
        AlertDialog confirm=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();
        confirm.getButton(AlertDialog.BUTTON_POSITIVE).performClick();
        // AlertDialog dispatches its button callback through a Handler.
        shadowOf(Looper.getMainLooper()).idle();
    }
    void at(int target)throws Exception {
        ReaderActivity a=controller.get();ListView list=(ListView)get(a,"list");
        assertEquals("saved/displayed page",target,get(a,"page"));
        assertEquals("first row",target-(int)get(a,"scopeStart"),list.getFirstVisiblePosition());
        assertEquals("page top",list.getPaddingTop(),list.getChildAt(0).getTop());
    }
    @After public void close()throws Exception {
        if(unblock!=null)unblock.countDown();
        if(controller!=null){ReaderActivity a=controller.get();controller.pause().stop().destroy();controller=null;((ExecutorService)get(a,"worker")).awaitTermination(10,TimeUnit.SECONDS);shadowOf(Looper.getMainLooper()).idle();}
    }
    @Test public void coldBookmarkUsesOneClickAcrossMixedHeightPages()throws Exception {
        open(1,"scroll");bookmark(1);settle();at(40);bookmark(0);settle();at(3);
    }
    @Test public void bookmarkWhileFlingingStopsAtTarget()throws Exception {
        ReaderActivity a=open(1,"scroll");ListView list=(ListView)get(a,"list");list.fling(9000);frame();bookmark(1);settle();at(40);
    }
    @Test public void lastShortPageBookmarkAndChapterEndKeepTarget()throws Exception {
        open(1,"scroll");bookmark(3);settle();at(60);
    }
    @Test public void splitChapterBookmarkUsesOneClick()throws Exception {
        open(2,"scroll");bookmark(2);settle();at(58);bookmark(0);settle();at(3);
    }
    @Test public void latestJumpWinsBeforeLayoutAndDecodeFinish()throws Exception {
        ReaderActivity a=open(1,"scroll");call(a,"go",40);call(a,"go",3);call(a,"go",58);settle();at(58);
    }
    @Test public void pagedBookmarkAndModeSwitchKeepTarget()throws Exception {
        ReaderActivity a=open(2,"paged");bookmark(1);settle();assertEquals(40,((ReaderPager)get(a,"pager")).displayed());
        call(a,"toggleMode");settle();at(40);bookmark(0);settle();at(3);
    }
    void holdDecoder()throws Exception {
        unblock=new CountDownLatch(1);CountDownLatch started=new CountDownLatch(1);
        ((ExecutorService)get(controller.get(),"worker")).submit(()->{started.countDown();try{unblock.await(10,TimeUnit.SECONDS);}catch(InterruptedException error){Thread.currentThread().interrupt();}});
        assertTrue(started.await(5,TimeUnit.SECONDS));
    }
    @Test public void coldPagedBookmarkSurvivesChromeResize()throws Exception {
        ReaderActivity a=open(1,"paged");holdDecoder();bookmark(1);
        ((ReaderChrome)get(a,"chrome")).show(false);shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(350));
        assertEquals("pending bookmark survives resize",40,((ReaderPager)get(a,"pager")).target());
        unblock.countDown();settle();assertEquals(40,((ReaderPager)get(a,"pager")).displayed());
    }
    @Test public void coldScrollBookmarkSurvivesChromeResize()throws Exception {
        ReaderActivity a=open(1,"scroll");holdDecoder();bookmark(1);
        ((ReaderChrome)get(a,"chrome")).show(false);shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(350));
        unblock.countDown();settle();at(40);
    }
    @Test public void scrollBookmarkSurvivesLayoutBeforeSelectionIsApplied()throws Exception {
        ReaderActivity a=open(1,"scroll");holdDecoder();bookmark(1);
        ListView list=(ListView)get(a,"list");
        list.layout(list.getLeft(),list.getTop(),list.getRight(),list.getBottom()+120);
        unblock.countDown();settle();at(40);
    }
    @Test public void coldPagedBookmarkSurvivesTapAndModeSwitch()throws Exception {
        ReaderActivity a=open(1,"paged");holdDecoder();bookmark(1);ReaderPager pager=(ReaderPager)get(a,"pager");
        long now=android.os.SystemClock.uptimeMillis();
        for(int action:new int[]{MotionEvent.ACTION_DOWN,MotionEvent.ACTION_UP}){
            MotionEvent event=MotionEvent.obtain(now,now+action*30,action,100,100,0);pager.onTouchEvent(event);event.recycle();
        }
        assertEquals("tap must not cancel bookmark",40,pager.target());
        call(a,"toggleMode");unblock.countDown();settle();at(40);
    }
}
