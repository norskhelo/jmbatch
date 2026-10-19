package app.jmbatch.android;

import android.app.Activity;
import android.app.Instrumentation;
import android.os.Bundle;
import android.os.Looper;
import android.widget.GridView;
import android.widget.RadioGroup;
import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.time.Duration;
import java.util.ArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;
import org.junit.Before;
import org.junit.After;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.LooperMode;
import org.robolectric.android.controller.ActivityController;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

/** Full production dialog and Android 10 widgets, including phone touch mode. */
@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE, sdk={29}, qualifiers="w360dp-h800dp-mdpi")
@LooperMode(LooperMode.Mode.PAUSED)
public class LibraryScreenRuntimeTest {
    private ActivityController<? extends Activity> controller;
    private Activity activity;
    private LibraryScreen screen;

    @Before public void resetIsolatedApp() throws Exception {
        new Instrumentation().setInTouchMode(true);
        for(Class<?> type:new Class<?>[]{Store.class,LibraryStore.class}) {
            Field field=type.getDeclaredField("instance");field.setAccessible(true);field.set(null,null);
        }
        for(String name:new String[]{"queue.json","library.json"}) {
            File file=new File(RuntimeEnvironment.getApplication().getFilesDir(),name);
            if(file.exists())assertTrue(file.delete());
        }
        RuntimeEnvironment.getApplication().getSharedPreferences("display",0).edit().clear().commit();
    }
    @After public void close() throws Exception {
        if(screen!=null)screen.close();
        if(controller!=null)controller.pause().stop().destroy();
        frames(); // Dialog dispatches its dismiss listener through the main looper.
        if(screen!=null) {
            ((ExecutorService)field(screen,"worker")).awaitTermination(10,TimeUnit.SECONDS);
            ((ExecutorService)field(screen,"coverWorker")).awaitTermination(10,TimeUnit.SECONDS);
        }
    }
    private static Object field(Object value,String name) throws Exception {
        Field field=value.getClass().getDeclaredField(name);field.setAccessible(true);return field.get(value);
    }
    private void call(String name,Class<?>[] types,Object... args) throws Exception {
        Method method=LibraryScreen.class.getDeclaredMethod(name,types);method.setAccessible(true);method.invoke(screen,args);
    }
    private static void frames(){shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));}
    private void settle() throws Exception {
        ((ExecutorService)field(screen,"worker")).submit(()->{}).get(10,TimeUnit.SECONDS);
        frames();
    }
    private GridView grid() throws Exception {return (GridView)field(screen,"list");}
    private void fixtures(int count) throws Exception {
        ArrayList<LibraryStore.Entry> entries=new ArrayList<>();
        for(int i=0;i<count;i++)entries.add(new LibraryStore.Entry(""+i,"Comic "+i,
            "content://app.jmbatch.android.exports/book"+i,"","test","images",i%2==0));
        LibraryStore.get(RuntimeEnvironment.getApplication()).importFound(entries);
    }
    private void open(boolean tiles,int count) throws Exception {
        fixtures(count);
        controller=Robolectric.buildActivity(Activity.class);
        activity=controller.get();activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);
        activity.getApplicationInfo().targetSdkVersion=34;
        activity.getSharedPreferences("display",0).edit().putBoolean("library",tiles).commit();
        controller.setup();screen=new LibraryScreen(activity,Store.get(activity));screen.show();settle();
        assertTrue(screen.isOpen());assertTrue("test must exercise touch mode",grid().isInTouchMode());
        assertEquals(count,grid().getCount());assertTrue("usable library viewport",grid().getHeight()>0);
        assertEquals(tiles?4:1,grid().getNumColumns());
        if(count>0)assertTrue("comics visible",grid().getChildCount()>0);
    }

    @Test public void chapterDeleteButtonChoosesConfirmsAndRefreshes() throws Exception {
        open(false,0);
        File book=new File(AlbumStorage.root(activity),"JM123-delete-12345678");assertTrue(book.mkdirs());
        for(int c=1;c<=3;c++)for(int p=1;p<=2;p++){
            File image=new File(book,String.format("%04d/%05d.jpg",c,p));image.getParentFile().mkdirs();java.nio.file.Files.write(image.toPath(),new byte[]{(byte)c,(byte)p,1});
        }
        LibraryStore.Entry entry=new LibraryStore.Entry("123","Delete fixture",ExportProvider.uri(activity,book).toString(),"","test","images",false);
        LibraryStore.get(activity).importFound(java.util.Collections.singletonList(entry));call("load",new Class<?>[]{});settle();
        call("setBatchMode",new Class<?>[]{boolean.class},true);call("itemClick",new Class<?>[]{int.class},0);frames();
        @SuppressWarnings("unchecked") java.util.List<android.widget.Button> buttons=(java.util.List<android.widget.Button>)field(screen,"singleButtons");
        android.widget.Button button=buttons.stream().filter(b->b.getText().toString().equals("删除章节")).findFirst().get();assertTrue(button.isEnabled());button.performClick();settle();settle();
        android.app.AlertDialog picker=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();assertTrue(picker.isShowing());assertEquals(3,picker.getListView().getCount());
        picker.getListView().performItemClick(picker.getListView().getChildAt(1),1,1);
        picker.getButton(android.app.AlertDialog.BUTTON_POSITIVE).performClick();
        android.app.AlertDialog confirmation=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();assertNotSame(picker,confirmation);
        confirmation.getButton(android.app.AlertDialog.BUTTON_POSITIVE).performClick();settle();settle();
        assertFalse(book.exists());assertEquals(1,grid().getCount());
        assertTrue(((android.widget.TextView)field(screen,"status")).getText().toString().contains("删除 1 章"));
        assertEquals(4,AlbumStorage.load(activity,android.net.Uri.parse(LibraryStore.get(activity).list("",false).get(0).uri)).images.size());
    }
    private void display(boolean tiles) throws Exception {
        RadioGroup selector=(RadioGroup)field(screen,"displaySelector");
        selector.check(selector.getChildAt(tiles?1:0).getId());frames();
        assertEquals(tiles?4:1,grid().getNumColumns());
        assertTrue(grid().getChildCount()>0);
    }
    private void scroll() throws Exception {
        grid().smoothScrollToPositionFromTop(40,-13,0);frames();
        assertTrue("scrolled away from beginning",grid().getFirstVisiblePosition()>0);
    }
    @Test public void emptyList() throws Exception {open(false,0);}
    @Test public void collectionsShareGridNavigateMoveAndRestoreState() throws Exception {
        open(true,6);LibraryStore library=LibraryStore.get(activity);
        String folder=library.createCollection("待读");
        java.util.List<LibraryStore.Entry> comics=library.list("",false);
        library.moveToCollection(comics.subList(0,2),folder);call("load",new Class<?>[0]);settle();
        assertEquals(5,grid().getCount());assertTrue(((LibraryStore.Entry)grid().getItemAtPosition(0)).isCollection());
        call("setBatchMode",new Class<?>[]{boolean.class},true);frames();call("select",new Class<?>[]{int.class},0);
        assertEquals(4,screen.saveState().getStringArrayList("selected").size());
        call("itemClick",new Class<?>[]{int.class},0);settle();
        assertEquals(folder,screen.saveState().getString("collection"));assertFalse(screen.saveState().getBoolean("batch"));assertEquals(2,grid().getCount());
        Bundle saved=screen.saveState();screen.close();frames();screen=new LibraryScreen(activity,Store.get(activity));screen.show(saved);settle();
        assertEquals(folder,screen.saveState().getString("collection"));assertEquals(2,grid().getCount());
        call("setBatchMode",new Class<?>[]{boolean.class},true);frames();call("select",new Class<?>[]{int.class},0);
        call("moveToCollection",new Class<?>[0]);
        android.app.AlertDialog chooser=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();
        assertEquals(2,chooser.getListView().getCount());chooser.getListView().performItemClick(null,0,0);settle();settle();
        assertEquals(0,grid().getCount());assertEquals(7,library.browse("",false,"").size());
        ((android.widget.Button)field(screen,"backButton")).performClick();settle();assertEquals(7,grid().getCount());
        call("itemLongClick",new Class<?>[]{int.class},0);
        android.app.AlertDialog manage=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();assertEquals(3,manage.getListView().getCount());
        manage.getListView().performItemClick(null,2,2);
        android.app.AlertDialog confirm=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();assertNotSame(manage,confirm);
        confirm.getButton(android.app.AlertDialog.BUTTON_POSITIVE).performClick();settle();settle();assertEquals(6,grid().getCount());
    }
    @Test public void emptyTiles() throws Exception {open(true,0);}
    @Test public void populatedList() throws Exception {open(false,80);}
    @Test public void populatedTiles() throws Exception {open(true,80);}
    @Test @Config(qualifiers="w320dp-h800dp-mdpi")
    public void narrowTiles() throws Exception {
        android.content.res.Resources resources=RuntimeEnvironment.getApplication().getResources();
        android.content.res.Configuration config=new android.content.res.Configuration(resources.getConfiguration());
        config.fontScale=1.8f;resources.updateConfiguration(config,resources.getDisplayMetrics());
        open(true,80);assertFourAcross();
    }
    @Test @Config(qualifiers="w800dp-h360dp-mdpi")
    public void wideTiles() throws Exception {open(true,80);assertFourAcross();}
    @Test @Config(sdk={29,35})
    public void coversFollowCardWidthWithoutCroppingAndSurviveModeSwitch() throws Exception {
        open(true,12);
        android.view.View row=grid().getAdapter().getView(0,null,grid());
        android.widget.ImageView image=(android.widget.ImageView)field(row,"image");
        for(int width:new int[]{48,64,96,180}){
            for(int[] size:new int[][]{{72,96},{192,96},{48,192}}){
                android.graphics.Bitmap bitmap=android.graphics.Bitmap.createBitmap(size[0],size[1],android.graphics.Bitmap.Config.ARGB_8888);
                image.setImageBitmap(bitmap);
                row.measure(android.view.View.MeasureSpec.makeMeasureSpec(width,android.view.View.MeasureSpec.EXACTLY),
                            android.view.View.MeasureSpec.makeMeasureSpec(0,android.view.View.MeasureSpec.UNSPECIFIED));
                row.layout(0,0,width,row.getMeasuredHeight());
                android.view.View frame=(android.view.View)image.getParent();
                assertEquals(Math.round(frame.getWidth()*4f/3f),frame.getHeight());
                android.graphics.RectF bounds=new android.graphics.RectF(image.getDrawable().getBounds());
                image.getImageMatrix().mapRect(bounds);
                assertTrue(bounds.left>=-.01f&&bounds.top>=-.01f);
                assertTrue(bounds.right<=image.getWidth()+.01f&&bounds.bottom<=image.getHeight()+.01f);
                assertEquals(size[0]/(float)size[1],bounds.width()/bounds.height(),.01f);
                assertEquals(image.getWidth()/2f,bounds.centerX(),.6f);
                assertEquals(image.getHeight()/2f,bounds.centerY(),.6f);
            }
        }
        display(false);
        android.view.View listRow=grid().getAdapter().getView(0,row,grid());
        assertNotSame(row,listRow);
        android.view.View frame=(android.view.View)((android.widget.ImageView)field(listRow,"image")).getParent();
        assertEquals(64,frame.getLayoutParams().width);assertEquals(86,frame.getLayoutParams().height);
        display(true);assertFourAcross();
    }
    private void assertFourAcross() throws Exception {
        for(int i=0;i<4;i++){
            android.view.View child=grid().getChildAt(i);
            assertEquals(grid().getChildAt(0).getTop(),child.getTop());
            assertTrue(child.getLeft()>=0&&child.getRight()<=grid().getWidth());
            android.view.View frame=((android.view.ViewGroup)child).getChildAt(0);
            assertEquals("cover height follows the actual column width",Math.round(frame.getWidth()*4f/3f),frame.getHeight());
        }
        if(grid().getChildCount()>4)assertTrue(grid().getChildAt(4).getTop()>grid().getChildAt(0).getTop());
        else assertEquals("one complete row fits the landscape viewport",4,grid().getChildCount());
    }
    @Test public void mainActivityEntry() throws Exception {
        fixtures(24);controller=Robolectric.buildActivity(MainActivity.class);activity=controller.get();
        activity.getSharedPreferences("display",0).edit().putBoolean("downloads",true).commit();
        activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);
        activity.getApplicationInfo().targetSdkVersion=34;controller.setup();
        assertEquals(android.widget.LinearLayout.class,field(activity,"queue").getClass());
        assertEquals(android.widget.LinearLayout.VERTICAL,((android.widget.LinearLayout)field(activity,"queue")).getOrientation());
        ((android.os.Handler)field(activity,"handler")).removeCallbacksAndMessages(null);
        Method open=MainActivity.class.getDeclaredMethod("showLibrary");open.setAccessible(true);open.invoke(activity);
        screen=(LibraryScreen)field(activity,"libraryScreen");settle();
        assertTrue(screen.isOpen());assertEquals(24,grid().getCount());assertTrue(grid().getChildCount()>0);
        // Stop the activity's updater timer before advancing simulated time further.
        controller.pause().stop().destroy();controller=null;
    }
    @Test public void switchModesPreservesBatchAndVisibleComic() throws Exception {
        open(false,80);scroll();
        int position=grid().getFirstVisiblePosition();
        call("itemLongClick",new Class<?>[]{int.class},position);
        frames(); // Complete the batch-toolbar layout before the next user action.
        Bundle before=screen.saveState();
        for(boolean tiles:new boolean[]{true,false,true,false}) {
            display(tiles);
            assertTrue(screen.saveState().getBoolean("batch"));
            assertEquals(before.getStringArrayList("selected"),screen.saveState().getStringArrayList("selected"));
            assertTrue("original comic "+position+" stays visible in tiles="+tiles+" (visible "+grid().getFirstVisiblePosition()+".."+grid().getLastVisiblePosition()+")",grid().getFirstVisiblePosition()<=position&&grid().getLastVisiblePosition()>=position);
        }
    }
    @Test public void refreshAndReopenRestoreViewport() throws Exception {
        open(false,80);scroll();Bundle before=screen.saveState();
        call("load",new Class<?>[0]);settle();
        assertEquals(before.getBundle("viewport").getString("anchor"),screen.saveState().getBundle("viewport").getString("anchor"));
        assertEquals(before.getBundle("viewport").getInt("top"),screen.saveState().getBundle("viewport").getInt("top"));
        screen.close();frames();screen=new LibraryScreen(activity,Store.get(activity));screen.show(before);settle();
        assertEquals(before.getBundle("viewport").getString("anchor"),screen.saveState().getBundle("viewport").getString("anchor"));
    }
}
