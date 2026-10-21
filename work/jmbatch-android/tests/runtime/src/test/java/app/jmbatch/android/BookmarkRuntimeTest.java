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
        controller.get().setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup().visible().windowFocusChanged(true);settle();return controller.get();
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
    static Button button(View view,String text){
        if(view instanceof Button&&text.contentEquals(((Button)view).getText()))return (Button)view;
        if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;for(int i=0;i<group.getChildCount();i++){Button found=button(group.getChildAt(i),text);if(found!=null)return found;}}
        return null;
    }
    void touch(Window window,View target){
        assertNotNull(target);assertTrue("target laid out",target.getWidth()>0&&target.getHeight()>0);
        int[] screen=new int[2],origin=new int[2];target.getLocationOnScreen(screen);window.getDecorView().getLocationOnScreen(origin);
        float x=screen[0]-origin[0]+target.getWidth()/2f,y=screen[1]-origin[1]+target.getHeight()/2f;
        long now=android.os.SystemClock.uptimeMillis();
        MotionEvent down=MotionEvent.obtain(now,now,MotionEvent.ACTION_DOWN,x,y,0);
        MotionEvent up=MotionEvent.obtain(now,now+40,MotionEvent.ACTION_UP,x,y,0);
        window.getDecorView().dispatchTouchEvent(down);window.getDecorView().dispatchTouchEvent(up);down.recycle();up.recycle();
        // AbsListView delivers the click after its pressed-state duration.
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(150));
    }
    void touchBookmark(String mode,int chapters)throws Exception {
        ReaderActivity a=open(chapters,mode);call(a,"go",17);settle();
        controller.windowFocusChanged(true);
        touch(a.getWindow(),button(a.getWindow().getDecorView(),"书签列表"));
        AlertDialog menu=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();assertTrue(menu.isShowing());
        controller.windowFocusChanged(false);
        menu.getWindow().getDecorView().dispatchWindowFocusChanged(true);
        touch(menu.getWindow(),menu.getListView().getChildAt(1));
        AlertDialog confirm=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();assertNotSame(menu,confirm);
        confirm.getWindow().getDecorView().dispatchWindowFocusChanged(true);
        touch(confirm.getWindow(),confirm.getButton(AlertDialog.BUTTON_POSITIVE));
        assertFalse("first tap closes bookmark dialog",confirm.isShowing());
        controller.windowFocusChanged(true);
        settle();
        if(mode.equals("scroll"))at(40);else assertEquals(40,((ReaderPager)get(a,"pager")).displayed());
    }
    @Test public void firstRealTouchWithWindowFocusScroll()throws Exception {touchBookmark("scroll",1);}
    @Test public void firstRealTouchWithWindowFocusPaged()throws Exception {touchBookmark("paged",1);}
    @Test public void firstRealTouchCrossChapterScroll()throws Exception {touchBookmark("scroll",2);}
    @Test public void firstRealTouchCrossChapterPaged()throws Exception {touchBookmark("paged",2);}
    @Test public void scrollJumpBeforeWindowRelayout()throws Exception {
        ReaderActivity a=open(1,"scroll");call(a,"go",17);settle();
        ListView list=(ListView)get(a,"list");
        call(a,"go",3);
        list.layout(list.getLeft(),list.getTop(),list.getRight(),list.getBottom()+120);
        settle();at(3);
    }
    @Test public void pagedJumpBeforeWindowRelayout()throws Exception {
        ReaderActivity a=open(1,"paged");call(a,"go",17);settle();
        ReaderPager pager=(ReaderPager)get(a,"pager");
        call(a,"go",3);
        pager.layout(pager.getLeft(),pager.getTop(),pager.getRight(),pager.getBottom()+120);
        settle();assertEquals(3,pager.displayed());
    }
    void deferredJump(String mode)throws Exception {
        ReaderActivity a=open(1,mode);call(a,"go",17);settle();
        controller.windowFocusChanged(false);bookmark(0);
        assertEquals("wait for reader window instead of navigating under dialog",17,get(a,"page"));
        if(mode.equals("paged"))assertEquals(17,((ReaderPager)get(a,"pager")).target());
        controller.windowFocusChanged(true);settle();
        if(mode.equals("scroll"))at(3);else assertEquals(3,((ReaderPager)get(a,"pager")).displayed());
    }
    @Test public void scrollBookmarkWaitsForDialogFocusReturn()throws Exception {deferredJump("scroll");}
    @Test public void pagedBookmarkWaitsForDialogFocusReturn()throws Exception {deferredJump("paged");}
    @Test public void latestDeferredBookmarkWins()throws Exception {
        ReaderActivity a=open(1,"paged");controller.windowFocusChanged(false);
        bookmark(0);bookmark(1);controller.windowFocusChanged(true);settle();
        assertEquals(40,((ReaderPager)get(a,"pager")).displayed());
    }
    static EditText input(View view){
        if(view instanceof EditText)return (EditText)view;
        if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;for(int i=0;i<group.getChildCount();i++){EditText found=input(group.getChildAt(i));if(found!=null)return found;}}
        return null;
    }
    @Test public void pageNumberAndChapterDialogsKeepTheirTargets()throws Exception {
        for(String mode:new String[]{"scroll","paged"}){
            ReaderActivity a=open(2,mode);call(a,"jumpPage");shadowOf(Looper.getMainLooper()).idle();
            AlertDialog dialog=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();
            input(dialog.getWindow().getDecorView()).setText("18");controller.windowFocusChanged(false);
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).performClick();shadowOf(Looper.getMainLooper()).idle();
            assertFalse(dialog.isShowing());controller.windowFocusChanged(true);settle();
            assertEquals(17,get(a,"page"));
            call(a,"chooseChapter");shadowOf(Looper.getMainLooper()).idle();
            dialog=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();controller.windowFocusChanged(false);
            shadowOf(dialog).clickOnItem(2);shadowOf(Looper.getMainLooper()).idle();
            controller.windowFocusChanged(true);settle();assertEquals(40,get(a,"page"));close();
        }
    }
    @Test public void cancelAndDeleteDoNotJump()throws Exception {
        ReaderActivity a=open(1,"scroll");call(a,"go",17);settle();
        for(int which:new int[]{AlertDialog.BUTTON_NEGATIVE,AlertDialog.BUTTON_NEUTRAL}){
            call(a,"bookmarks");shadowOf(Looper.getMainLooper()).idle();
            shadowOf(org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog()).clickOnItem(0);shadowOf(Looper.getMainLooper()).idle();
            AlertDialog dialog=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();
            dialog.getButton(which).performClick();settle();at(17);
        }
        assertFalse(((Set<?>)get(a,"marks")).contains(3));
    }
    @Test public void scrollAnchorReleasesForUserGesture()throws Exception {
        ReaderActivity a=open(1,"scroll");call(a,"go",3);settle();at(3);
        ListView list=(ListView)get(a,"list");long now=android.os.SystemClock.uptimeMillis();
        for(int i=0;i<4;i++){
            int action=i==0?MotionEvent.ACTION_DOWN:i==3?MotionEvent.ACTION_UP:MotionEvent.ACTION_MOVE;
            MotionEvent event=MotionEvent.obtain(now,now+i*100,action,100,list.getHeight()*.85f-i*100,0);
            list.dispatchTouchEvent(event);event.recycle();shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(20));
        }
        settle();assertTrue("a completed jump must not pin subsequent scrolling",list.getFirstVisiblePosition()>3||list.getChildAt(0).getTop()<0);
    }
}
