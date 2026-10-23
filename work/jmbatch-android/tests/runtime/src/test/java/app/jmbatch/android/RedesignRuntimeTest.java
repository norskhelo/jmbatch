package app.jmbatch.android;

import android.app.AlertDialog;
import android.view.*;
import android.widget.*;
import android.os.Looper;
import org.json.*;
import org.junit.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

/** Focused production UI paths for the confirmed redesign. */
public class RedesignRuntimeTest extends BookmarkRuntimeTest {
    static <T extends View> T find(View root,Class<T> type,String text){
        if(type.isInstance(root)&&(text==null||root instanceof TextView&&((TextView)root).getText().toString().equals(text)))return type.cast(root);
        if(root instanceof ViewGroup)for(int i=0;i<((ViewGroup)root).getChildCount();i++){T found=find(((ViewGroup)root).getChildAt(i),type,text);if(found!=null)return found;}
        return null;
    }
    @Test public void newJumpDialogNavigatesInAllThreeModes()throws Exception {
        for(String mode:new String[]{"scroll","paged","vertical"}){
            ReaderActivity activity=open(1,mode);ViewGroup decor=(ViewGroup)activity.getWindow().getDecorView();int children=decor.getChildCount();call(activity,"jumpPage");shadowOf(Looper.getMainLooper()).idle();
            AlertDialog dialog=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();
            find(dialog.getWindow().getDecorView(),EditText.class,null).setText("41");
            find(dialog.getWindow().getDecorView(),Button.class,"跳转").performClick();settle();
            assertEquals(40,get(activity,"page"));
            assertEquals("Dismiss must remove the blur layer even with a navigation listener",children,decor.getChildCount());
            if(!mode.equals("scroll"))assertEquals(40,((ReaderPager)get(activity,"pager")).displayed());
            close();
        }
    }
    @Test public void newBookmarkListUsesSingleClick()throws Exception {
        ReaderActivity activity=open(1,"scroll");call(activity,"jumpPage");shadowOf(Looper.getMainLooper()).idle();
        AlertDialog dialog=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();
        find(dialog.getWindow().getDecorView(),Button.class,"第 41 页").performClick();settle();at(40);
    }
    @Test public void namedBookmarkAnchorsAndSurvivesChapterRemapping()throws Exception {
        ReaderActivity activity=open(1,"scroll");call(activity,"showBookmarkInput");shadowOf(Looper.getMainLooper()).idle();
        PopupWindow popup=(PopupWindow)get(activity,"bookmarkPanel");assertTrue(popup.isShowing());
        find(popup.getContentView(),EditText.class,null).setText("测试书签");find(popup.getContentView(),Button.class,"添加").performClick();
        assertFalse(popup.isShowing());assertEquals("测试书签",((Map<?,?>)get(activity,"bookmarkNames")).get(0));
        JSONObject mapped=ChapterDeletion.remap(new JSONObject().put("page",3).put("mode","vertical").put("bookmarks",new JSONArray(Arrays.asList(0,3))).put("bookmarkNames",new JSONObject().put("0","旧").put("3","保留")),Arrays.asList(1,1,2,2),Collections.singleton(1));
        assertEquals("保留",mapped.getJSONObject("bookmarkNames").getString("1"));assertEquals("vertical",mapped.getString("mode"));
    }
    @Test public void aggregateBudgetAndZeroLimit()throws Exception {
        AtomicInteger limit=new AtomicInteger(64);DownloadRate rate=new DownloadRate(limit::get);ExecutorService jobs=Executors.newFixedThreadPool(3);
        CountDownLatch start=new CountDownLatch(1);List<Future<?>> results=new ArrayList<>();long began=System.nanoTime();
        try{for(int i=0;i<3;i++)results.add(jobs.submit(()->{try{start.await();rate.acquire(32768,new JmApi.Control());}catch(Exception e){throw new RuntimeException(e);}}));start.countDown();for(Future<?> result:results)result.get(8,TimeUnit.SECONDS);double elapsed=(System.nanoTime()-began)/1e9;assertTrue(elapsed>=1.35&&elapsed<6);
            limit.set(0);began=System.nanoTime();rate.acquire(Integer.MAX_VALUE,new JmApi.Control());assertTrue(System.nanoTime()-began<100_000_000);
            limit.set(1);JmApi.Control cancelled=new JmApi.Control();cancelled.cancel("PAUSE");try{rate.acquire(1024,cancelled);fail("pause must interrupt throttle");}catch(java.io.IOException expected){}
        }finally{jobs.shutdownNow();}
    }
    @Test public void favoritesKeepRelativeOrderWhenReversed()throws Exception {
        List<LibraryStore.Entry> entries=new ArrayList<>();for(int i=0;i<4;i++)entries.add(new LibraryStore.Entry(""+i,new String[]{"Z","B","A","C"}[i],"content://fixture/"+i,"","","zip",i%2==0));
        List<LibraryStore.Entry> sorted=LibrarySort.sorted(context,entries,"name",true);assertEquals("0",sorted.get(0).id);assertEquals("2",sorted.get(1).id);assertEquals("3",sorted.get(2).id);assertEquals("1",sorted.get(3).id);
    }
}
