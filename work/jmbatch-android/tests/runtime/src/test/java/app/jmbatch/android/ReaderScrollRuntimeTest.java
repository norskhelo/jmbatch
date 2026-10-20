
package app.jmbatch.android;

import android.content.*;
import android.graphics.Bitmap;
import android.graphics.drawable.BitmapDrawable;
import android.os.Looper;
import android.util.LruCache;
import android.view.*;
import android.widget.*;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.*;
import org.robolectric.android.controller.ActivityController;
import java.io.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},qualifiers="w480dp-h1067dp-xxhdpi")
@LooperMode(LooperMode.Mode.PAUSED)
public class ReaderScrollRuntimeTest {
    ActivityController<ReaderActivity> controller;
    int layoutPasses;
    static Field member(Object target,String name)throws Exception {
        Field field=target.getClass().getDeclaredField(name);field.setAccessible(true);return field;
    }
    static Object get(Object target,String name)throws Exception {return member(target,name).get(target);}
    static void set(Object target,String name,Object value)throws Exception {member(target,name).set(target,value);}
    static Object invoke(Object target,String name)throws Exception {
        Method method=target.getClass().getDeclaredMethod(name);method.setAccessible(true);return method.invoke(target);
    }
    static void record(String name,JSONObject result)throws Exception {
        Path folder=Paths.get(System.getProperty("jm.test.classes")).getParent().getParent().resolve("reader-measurements");
        Files.createDirectories(folder);
        Path output=folder.resolve(name+"-api"+RuntimeEnvironment.getApiLevel()+".json");
        Files.write(output,result.toString(2).getBytes("UTF-8"));
        System.out.println("PROBE "+name+" saved ("+result.toString().length()+" chars)");
    }
    @After public void close()throws Exception {
        if(controller!=null) {
            ReaderActivity activity=controller.get();controller.pause().stop().destroy();
            ((ExecutorService)get(activity,"worker")).awaitTermination(10,TimeUnit.SECONDS);
            shadowOf(Looper.getMainLooper()).idle();
        }
    }
    @SuppressWarnings("unchecked")
    @Test public void cacheEvictionKeepsTheDisplayedImageAndItsHeight()throws Exception {
        // Attached Activity without onCreate: no file reads/worker requests in this controlled row probe.
        ReaderActivity activity=Robolectric.buildActivity(ReaderActivity.class).get();
        activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);
        set(activity,"viewportWidth",360);set(activity,"closed",true);
        Class<?> rowType=Class.forName("app.jmbatch.android.ReaderActivity$PageRow");
        Constructor<?> constructor=rowType.getDeclaredConstructor(ReaderActivity.class);constructor.setAccessible(true);
        FrameLayout row=(FrameLayout)constructor.newInstance(activity);
        Method bind=ReaderActivity.class.getDeclaredMethod("bind",rowType,int.class);bind.setAccessible(true);
        LruCache<String,Bitmap> cache=(LruCache<String,Bitmap>)get(activity,"cache");
        Bitmap shown=Bitmap.createBitmap(360,1080,Bitmap.Config.ARGB_8888);
        String key=new ReaderRequests.Job(0,0,360,0).key;
        cache.put(key,shown);bind.invoke(activity,row,0);
        ImageView image=(ImageView)get(row,"image");TextView label=(TextView)get(row,"label");
        int initialHeight=image.getLayoutParams().height;
        // Put three images at the production maximum 4 MP, through the real 32 MiB LRU.
        for(int i=1;i<=3;i++)cache.put("pressure-"+i,Bitmap.createBitmap(1600,2500,Bitmap.Config.ARGB_8888));
        assertNull(cache.get(key));assertNotNull(image.getDrawable());
        bind.invoke(activity,row,0);
        int missHeight=image.getLayoutParams().height,missVisibility=label.getVisibility();
        boolean retained=((BitmapDrawable)image.getDrawable()).getBitmap()==shown;
        cache.put(key,shown);bind.invoke(activity,row,0);
        int recovered=image.getLayoutParams().height;
        assertEquals(1080,initialHeight);assertEquals(initialHeight,missHeight);assertEquals(View.GONE,missVisibility);
        assertTrue(retained);assertEquals(initialHeight,recovered);assertEquals(View.GONE,label.getVisibility());
        record("cache-eviction",new JSONObject().put("initial_height",initialHeight)
            .put("cache_miss_height",missHeight).put("reloaded_height",recovered)
            .put("old_drawable_still_present",retained).put("loading_over_valid_image",missVisibility==View.VISIBLE)
            .put("cache_evictions",cache.evictionCount()).put("trigger","synthetic cache pressure, no gesture"));
        cache.evictAll();
        ((ExecutorService)get(activity,"worker")).shutdown();
        ((ExecutorService)get(activity,"libraryWorker")).shutdown();
    }
    void frame(ReaderActivity activity)throws Exception {
        ((ExecutorService)get(activity,"worker")).submit(()->{}).get(10,TimeUnit.SECONDS);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(16));
    }
    JSONObject snapshot(ReaderActivity activity,int tick)throws Exception {
        ListView list=(ListView)get(activity,"list");
        LruCache<?,?> cache=(LruCache<?,?>)get(activity,"cache");
        JSONObject value=new JSONObject().put("tick",tick).put("generation",get(activity,"generation"))
            .put("puts",cache.putCount()).put("evictions",cache.evictionCount()).put("cache_bytes",cache.size())
            .put("cache_keys",new JSONArray(cache.snapshot().keySet())).put("layouts",layoutPasses)
            .put("viewport_width",get(activity,"viewportWidth")).put("viewport_height",get(activity,"viewportHeight"));
        if(list!=null) {
            value.put("first",list.getFirstVisiblePosition());JSONArray rows=new JSONArray();
            for(int i=0;i<list.getChildCount();i++){
                View row=list.getChildAt(i);ImageView image=(ImageView)get(row,"image");TextView label=(TextView)get(row,"label");
                rows.put(new JSONObject().put("index",list.getFirstVisiblePosition()+i).put("top",row.getTop())
                    .put("height",row.getHeight()).put("image_height",image.getLayoutParams().height)
                    .put("loading",label.getVisibility()==View.VISIBLE).put("tag",row.getTag()));
            }
            value.put("rows",rows);
        }
        return value;
    }
    @Test public void naturalColdOpenAndScrollTrace()throws Exception {
        naturalTrace(0);
    }
    @Test public void coldResumeWithMoreVisiblePages()throws Exception {
        naturalTrace(1);
    }
    private void naturalTrace(int savedPage)throws Exception {
        Context context=RuntimeEnvironment.getApplication();
        new android.app.Instrumentation().setInTouchMode(true);
        for(Class<?> type:new Class<?>[]{Store.class,LibraryStore.class}){Field f=type.getDeclaredField("instance");f.setAccessible(true);f.set(null,null);}
        for(String name:new String[]{"queue.json","library.json"})Files.deleteIfExists(new File(context.getFilesDir(),name).toPath());
        File root=new File(AlbumStorage.root(context),"JM123-scroll-"+UUID.randomUUID().toString().substring(0,8));assertTrue(root.mkdirs());
        byte[][] variants=new byte[3][];
        int[][] dimensions={{1600,2400},{2400,1200},{1200,3600}};
        for(int i=0;i<3;i++){
            ByteArrayOutputStream out=new ByteArrayOutputStream();
            Bitmap b=Bitmap.createBitmap(dimensions[i][0],dimensions[i][1],Bitmap.Config.ARGB_8888);
            b.eraseColor(0xffdddddd);assertTrue(b.compress(Bitmap.CompressFormat.JPEG,80,out));b.recycle();variants[i]=out.toByteArray();
        }
        JSONArray entries=new JSONArray();
        for(int i=0;i<42;i++){
            String name=String.format("%05d.jpg",i+1);byte[] bytes=variants[i%3];
            Files.write(new File(root,name).toPath(),bytes);
            entries.put(new JSONObject().put("chapter",1).put("page",i+1).put("file",name).put("size",bytes.length));
        }
        JSONObject manifest=new JSONObject().put("version",2).put("id","123").put("title","Synthetic scroll diagnosis").put("entries",entries);
        Files.write(new File(root,AlbumRules.MANIFEST).toPath(),manifest.toString().getBytes("UTF-8"));
        String key=ExportProvider.uri(context,root).toString();
        context.getSharedPreferences("reader-history",0).edit().putString(key,new JSONObject().put("page",savedPage).put("mode","scroll").toString()).commit();
        LibraryStore.Entry entry=new LibraryStore.Entry("123","Synthetic scroll diagnosis",key,"","","images",false);
        controller=Robolectric.buildActivity(ReaderActivity.class,new Intent(context,ReaderActivity.class).putExtra("entry",entry.json().toString()));
        controller.get().setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup().visible();
        ReaderActivity activity=controller.get();JSONArray trace=new JSONArray();
        activity.getWindow().getDecorView().getViewTreeObserver().addOnGlobalLayoutListener(()->layoutPasses++);
        for(int i=0;i<100;i++){frame(activity);trace.put(snapshot(activity,i));}
        assertNotNull(get(activity,"list"));
        // Deterministic ListView scroll input through the real framework; pause afterward.
        ListView list=(ListView)get(activity,"list");
        assertTrue("must model phone touch mode",list.isInTouchMode());
        for(int i=100;i<180;i++){list.scrollListBy(240);frame(activity);trace.put(snapshot(activity,i));}
        for(int i=180;i<240;i++){frame(activity);trace.put(snapshot(activity,i));}
        for(int i=240;i<320;i++){list.scrollListBy(-240);frame(activity);trace.put(snapshot(activity,i));}
        for(int i=320;i<380;i++){frame(activity);trace.put(snapshot(activity,i));}
        JSONObject settled=trace.getJSONObject(339),last=trace.getJSONObject(379);
        assertEquals("no repeated decode while stationary",settled.getInt("puts"),last.getInt("puts"));
        assertEquals("no eviction loop",settled.getInt("evictions"),last.getInt("evictions"));
        assertEquals("no stationary layout loop",settled.getInt("layouts"),last.getInt("layouts"));
        String geometry=settled.getJSONArray("rows").toString();
        for(int i=340;i<380;i++){
            JSONObject current=trace.getJSONObject(i);assertEquals("stable page heights and scroll anchor",geometry,current.getJSONArray("rows").toString());
            JSONArray rows=current.getJSONArray("rows");for(int j=0;j<rows.length();j++)assertFalse("no loading over a ready image",rows.getJSONObject(j).getBoolean("loading"));
        }
        assertTrue(((LruCache<?,?>)get(activity,"cache")).size()<=32*1024*1024);
        assertTrue(((ReaderRequests)get(activity,"requests")).waiting()<=8);
        if(savedPage==1)checkLifecycle(activity);
        record("natural-trace-"+savedPage,new JSONObject().put("frames",trace).put("touch_mode",list.isInTouchMode())
            .put("saved_page",savedPage).put("input","cold open, scroll forward, hold, scroll backward, hold; synthetic JPEGs"));
    }

    @SuppressWarnings("unchecked")
    @Test public void recycledRowsKeepGeometryWithoutKeepingTheOldImage()throws Exception {
        ReaderActivity activity=Robolectric.buildActivity(ReaderActivity.class).get();
        activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);set(activity,"viewportWidth",360);set(activity,"closed",true);
        Class<?> rowType=Class.forName("app.jmbatch.android.ReaderActivity$PageRow");
        Constructor<?> constructor=rowType.getDeclaredConstructor(ReaderActivity.class);constructor.setAccessible(true);
        FrameLayout row=(FrameLayout)constructor.newInstance(activity);
        Method bind=ReaderActivity.class.getDeclaredMethod("bind",rowType,int.class);bind.setAccessible(true);
        LruCache<String,Bitmap> cache=(LruCache<String,Bitmap>)get(activity,"cache");
        Bitmap old=Bitmap.createBitmap(360,1080,Bitmap.Config.ARGB_8888);
        cache.put(new ReaderRequests.Job(0,0,360,0).key,old);bind.invoke(activity,row,0);
        android.graphics.drawable.Drawable drawable=((ImageView)get(row,"image")).getDrawable();
        for(int i=0;i<20;i++)bind.invoke(activity,row,0);
        assertSame("same bitmap does not recreate drawable",drawable,((ImageView)get(row,"image")).getDrawable());
        cache.evictAll();invoke(row,"release");
        assertNull(get(row,"shown"));assertNull(((ImageView)get(row,"image")).getDrawable());
        bind.invoke(activity,row,0);
        assertEquals("cached geometry survives bitmap eviction and recycling",1080,((ImageView)get(row,"image")).getLayoutParams().height);
        assertEquals(View.VISIBLE,((TextView)get(row,"label")).getVisibility());
        bind.invoke(activity,row,1);
        assertNull("another page must not display the old image",((ImageView)get(row,"image")).getDrawable());
        assertTrue(((TextView)get(row,"label")).getText().toString().contains("第 2 页"));
        Map<Integer,String> errors=(Map<Integer,String>)get(activity,"errors");errors.put(1,"synthetic missing page");bind.invoke(activity,row,1);
        assertTrue(((TextView)get(row,"label")).getText().toString().contains("读取失败"));
        set(activity,"viewportWidth",720);set(activity,"generation",1);bind.invoke(activity,row,0);
        assertEquals("known aspect ratio is reused at the new width",2160,((ImageView)get(row,"image")).getLayoutParams().height);
        assertNull("new generation cannot reuse stale bitmap",((ImageView)get(row,"image")).getDrawable());
        ((ExecutorService)get(activity,"worker")).shutdown();((ExecutorService)get(activity,"libraryWorker")).shutdown();
    }
    @SuppressWarnings("unchecked")
    @Test public void visibleImagesSurviveCombinedSizesLargerThanTheLruBudget()throws Exception {
        ReaderActivity activity=Robolectric.buildActivity(ReaderActivity.class).get();
        activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);set(activity,"viewportWidth",1600);set(activity,"closed",true);
        Class<?> rowType=Class.forName("app.jmbatch.android.ReaderActivity$PageRow");
        Constructor<?> constructor=rowType.getDeclaredConstructor(ReaderActivity.class);constructor.setAccessible(true);
        Method bind=ReaderActivity.class.getDeclaredMethod("bind",rowType,int.class);bind.setAccessible(true);
        LruCache<String,Bitmap> cache=(LruCache<String,Bitmap>)get(activity,"cache");FrameLayout[] rows=new FrameLayout[3];
        for(int i=0;i<3;i++){
            rows[i]=(FrameLayout)constructor.newInstance(activity);
            cache.put(new ReaderRequests.Job(0,i,1600,0).key,Bitmap.createBitmap(1600,2500,Bitmap.Config.ARGB_8888));
            bind.invoke(activity,rows[i],i);
        }
        assertTrue(cache.evictionCount()>0);
        for(int cycle=0;cycle<20;cycle++)for(int i=0;i<3;i++){
            bind.invoke(activity,rows[i],i);assertEquals(2500,((ImageView)get(rows[i],"image")).getLayoutParams().height);
            assertEquals(View.GONE,((TextView)get(rows[i],"label")).getVisibility());
        }
        for(FrameLayout row:rows)invoke(row,"release");cache.evictAll();
        ((ExecutorService)get(activity,"worker")).shutdown();((ExecutorService)get(activity,"libraryWorker")).shutdown();
    }
    private void checkLifecycle(ReaderActivity activity)throws Exception {
        ListView list=(ListView)get(activity,"list");int first=list.getFirstVisiblePosition(),top=list.getChildAt(0).getTop();
        int generation=(Integer)get(activity,"generation");
        ReaderChrome chrome=(ReaderChrome)get(activity,"chrome");chrome.show(false);
        for(int i=0;i<24;i++)frame(activity);
        assertEquals("height-only chrome changes keep decoded generation",generation,get(activity,"generation"));
        assertEquals(first,list.getFirstVisiblePosition());assertEquals(top,list.getChildAt(0).getTop());
        int page=(Integer)get(activity,"page");invoke(activity,"toggleMode");
        for(int i=0;i<30;i++)frame(activity);
        ReaderPager pager=(ReaderPager)get(activity,"pager");assertNotNull(pager);assertEquals(page,pager.displayed());
        invoke(activity,"toggleMode");for(int i=0;i<30;i++)frame(activity);
        assertEquals(page,((ListView)get(activity,"list")).getFirstVisiblePosition());
        // Start a cold jump then close before its callback. No late render may refill the cache.
        Method go=ReaderActivity.class.getDeclaredMethod("go",int.class);go.setAccessible(true);go.invoke(activity,35);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(1));
        controller.pause().stop().destroy();controller=null;
        assertTrue(((ExecutorService)get(activity,"worker")).awaitTermination(10,TimeUnit.SECONDS));
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(100));
        assertEquals(0,((LruCache<?,?>)get(activity,"cache")).size());
        assertTrue(((Map<?,?>)get(activity,"pageSizes")).isEmpty());
    }
}
