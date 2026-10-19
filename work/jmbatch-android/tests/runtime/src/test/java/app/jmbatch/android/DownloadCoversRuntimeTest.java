package app.jmbatch.android;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Rect;
import android.os.Looper;
import android.util.LruCache;
import android.widget.ImageView;
import android.widget.TextView;
import java.io.File;
import java.lang.reflect.*;
import java.nio.file.Files;
import java.time.Duration;
import java.util.concurrent.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.*;
import static org.junit.Assert.*;

/** Actual worker, LRU and view binding; cached synthetic bitmaps avoid device codecs. */
@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},qualifiers="w360dp-h800dp-mdpi")
@LooperMode(LooperMode.Mode.PAUSED)
public class DownloadCoversRuntimeTest {
    Context context;DownloadCovers covers;Store.Task task;CountingImage image;
    DownloadCovers.Target target;TextView placeholder;Bitmap red,blue;File first;
    static class CountingImage extends ImageView {
        boolean visible=true;int assignments;
        CountingImage(Context context){super(context);}
        @Override public boolean getGlobalVisibleRect(Rect rect,android.graphics.Point offset){return visible;}
        @Override public void setImageBitmap(Bitmap bitmap){assignments++;super.setImageBitmap(bitmap);}
    }
    Object field(String name)throws Exception {Field f=DownloadCovers.class.getDeclaredField(name);f.setAccessible(true);return f.get(covers);}
    void seed(Store.Task value,Bitmap bitmap)throws Exception {
        DownloadCoverRules.Source source=DownloadCoverRules.resolve(new File(context.getFilesDir(),"work"),value.key,value.status,value.resultUri,value.settings.format);
        Class<?> type=Class.forName("app.jmbatch.android.DownloadCovers$Cover");Constructor<?> ctor=type.getDeclaredConstructor(Bitmap.class);ctor.setAccessible(true);
        ((LruCache)field("cache")).put(source.stamp,ctor.newInstance(bitmap));
    }
    File page(Store.Task value)throws Exception {
        File file=new File(context.getFilesDir(),"work/"+value.key+"/images/0001/00001.jpg");file.getParentFile().mkdirs();Files.write(file.toPath(),new byte[]{1,2,3});return file;
    }
    void flush()throws Exception {
        ((ThreadPoolExecutor)field("worker")).submit(()->{}).get(5,TimeUnit.SECONDS);
        Shadows.shadowOf(Looper.getMainLooper()).idle();
    }
    void tick(){Shadows.shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(2));}
    @Before public void setup()throws Exception {
        context=RuntimeEnvironment.getApplication();covers=new DownloadCovers(context);
        task=new Store.Task("123456",new Store.Settings());task.status="running";first=page(task);
        red=Bitmap.createBitmap(54,72,Bitmap.Config.ARGB_8888);blue=Bitmap.createBitmap(54,72,Bitmap.Config.ARGB_8888);seed(task,red);
        image=new CountingImage(context);placeholder=new TextView(context);target=new DownloadCovers.Target(image,placeholder);
    }
    @After public void close(){covers.close();}
    @Test public void unchangedProgressNeverRebindsTheSameImage()throws Exception {
        covers.bind(task,target);flush();assertEquals(1,image.assignments);
        for(int i=0;i<12;i++){tick();task.done++;covers.bind(task,target);flush();}
        assertEquals("Progress polling must not reassign the bitmap",1,image.assignments);
        assertEquals(android.view.View.GONE,placeholder.getVisibility());
    }
    @Test public void scrollBackRestoresBeforeThrottleOrPendingGate()throws Exception {
        covers.bind(task,target);flush();image.visible=false;covers.bind(task,target);
        assertNull(image.getDrawable());
        image.visible=true;target.pending=true;covers.bind(task,target);
        assertSame(red,((android.graphics.drawable.BitmapDrawable)image.getDrawable()).getBitmap());assertNotNull(image.getDrawable());
        assertEquals(android.view.View.GONE,placeholder.getVisibility());
    }
    @Test public void offscreenCompletionIsImmediatelyReusable()throws Exception {
        covers.bind(task,target);image.visible=false;flush();assertNull(image.getDrawable());
        image.visible=true;covers.bind(task,target);
        assertSame(red,((android.graphics.drawable.BitmapDrawable)image.getDrawable()).getBitmap());assertNotNull(image.getDrawable());
    }
    @Test public void cleanupHandoffKeepsCoverUntilFinishedSourceIsReady()throws Exception {
        covers.bind(task,target);flush();assertTrue(first.delete());tick();covers.bind(task,target);flush();
        assertSame(red,((android.graphics.drawable.BitmapDrawable)image.getDrawable()).getBitmap());assertEquals(1,image.assignments);
        task.status="done";task.resultUri="content://synthetic/finished.zip";seed(task,blue);
        tick();covers.bind(task,target);flush();assertSame(blue,((android.graphics.drawable.BitmapDrawable)image.getDrawable()).getBitmap());assertEquals(2,image.assignments);
    }
    @Test public void repairedFirstPageReplacesExistingImage()throws Exception {
        covers.bind(task,target);flush();Files.write(first.toPath(),new byte[]{4,5,6,7});seed(task,blue);
        tick();covers.bind(task,target);flush();assertSame(blue,((android.graphics.drawable.BitmapDrawable)image.getDrawable()).getBitmap());assertEquals(2,image.assignments);
    }
    @Test public void oldCallbackCannotOverwriteAnotherTask()throws Exception {
        covers.bind(task,target);
        ((ThreadPoolExecutor)field("worker")).submit(()->{}).get(5,TimeUnit.SECONDS);
        Store.Task other=new Store.Task("123457",new Store.Settings());other.status="running";page(other);seed(other,blue);
        covers.bind(other,target);flush();assertSame(blue,((android.graphics.drawable.BitmapDrawable)image.getDrawable()).getBitmap());assertEquals(1,image.assignments);
    }
    @Test public void removalDiscardsLateResult()throws Exception {
        covers.bind(task,target);target.remove();flush();assertNull(image.getDrawable());
    }
    @Test public void activityScrollRestoresCoverWithoutWaitingForTimer()throws Exception {
        Field singleton=Store.class.getDeclaredField("instance");singleton.setAccessible(true);singleton.set(null,null);
        Store store=Store.get(context);store.tasks.clear();store.tasks.add(task);
        org.robolectric.android.controller.ActivityController<MainActivity> controller=Robolectric.buildActivity(MainActivity.class);
        MainActivity activity=controller.get();activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);
        try{
            controller.setup().visible();
            Field loader=MainActivity.class.getDeclaredField("downloadCovers");loader.setAccessible(true);((DownloadCovers)loader.get(activity)).close();loader.set(activity,covers);
            Field handler=MainActivity.class.getDeclaredField("handler");handler.setAccessible(true);((android.os.Handler)handler.get(activity)).removeCallbacksAndMessages(null);
            Method render=MainActivity.class.getDeclaredMethod("render");render.setAccessible(true);render.invoke(activity);
            android.view.View decor=activity.getWindow().getDecorView();
            decor.measure(android.view.View.MeasureSpec.makeMeasureSpec(360,android.view.View.MeasureSpec.EXACTLY),android.view.View.MeasureSpec.makeMeasureSpec(800,android.view.View.MeasureSpec.EXACTLY));decor.layout(0,0,360,800);
            Field focus=MainActivity.class.getDeclaredField("inputFocus");focus.setAccessible(true);
            android.widget.ScrollView scroll=(android.widget.ScrollView)((android.view.ViewGroup)focus.get(activity)).getChildAt(0);
            Field queue=MainActivity.class.getDeclaredField("queue");queue.setAccessible(true);int y=((android.view.View)queue.get(activity)).getTop();
            Field rows=MainActivity.class.getDeclaredField("rows");rows.setAccessible(true);Object row=((java.util.Map)rows.get(activity)).get(task.key);
            Field cover=row.getClass().getDeclaredField("cover");cover.setAccessible(true);DownloadCovers.Target actual=(DownloadCovers.Target)cover.get(row);
            assertEquals(ImageView.ScaleType.CENTER_CROP,actual.image.getScaleType());
            scroll.scrollTo(0,y);flush();assertNotNull("First scroll must load a visible row",actual.image.getDrawable());
            scroll.scrollTo(0,0);assertNull("Row should release its off-screen bitmap",actual.image.getDrawable());
            actual.next=Long.MAX_VALUE;scroll.scrollTo(0,y);
            assertNotNull("Scroll callback must restore before the 700ms render timer",actual.image.getDrawable());
            assertSame(red,((android.graphics.drawable.BitmapDrawable)actual.image.getDrawable()).getBitmap());
        }finally{controller.pause().stop().destroy();singleton.set(null,null);}
    }
}
