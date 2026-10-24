package app.jmbatch.android;

import android.app.Activity;
import android.os.Looper;
import android.view.View;
import android.widget.*;
import java.io.File;
import java.lang.reflect.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.android.controller.ActivityController;
import org.robolectric.annotation.*;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},shadows={CollectionRuntimeTest.WindowsAtomicRename.class})
@LooperMode(LooperMode.Mode.PAUSED)
public class LibraryMoveScrollRuntimeTest {
    ActivityController<Activity> controller; Activity activity; LibraryScreen screen;
    LibraryStore library; String folder; List<LibraryStore.Entry> books;
    static Object field(Object o,String name)throws Exception{Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(o);}
    Object call(String name,Class<?>[] types,Object...args)throws Exception{Method m=LibraryScreen.class.getDeclaredMethod(name,types);m.setAccessible(true);return m.invoke(screen,args);}
    GridView grid()throws Exception{return (GridView)field(screen,"list");}
    void settle()throws Exception{for(int i=0;i<3;i++){((ExecutorService)field(screen,"worker")).submit(()->{}).get(10,TimeUnit.SECONDS);shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(300));}}
    @Before public void setup()throws Exception{
        for(Class<?> type:new Class<?>[]{Store.class,LibraryStore.class}){Field f=type.getDeclaredField("instance");f.setAccessible(true);f.set(null,null);}
        controller=Robolectric.buildActivity(Activity.class);activity=controller.get();activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup();
        for(String file:new String[]{"library.json","queue.json"})new android.util.AtomicFile(new File(activity.getFilesDir(),file)).delete();
        library=LibraryStore.get(activity);folder=library.createCollection("A folder");books=new ArrayList<>();
        for(int i=0;i<32;i++)books.add(new LibraryStore.Entry(""+(100+i),"Book "+i,"content://fixture/"+i,"","","zip",false,"",1));
        library.importFound(books);screen=new LibraryScreen(activity,Store.get(activity));screen.show();settle();
    }
    @After public void close(){if(screen!=null)screen.close();if(controller!=null)controller.pause().stop().destroy();shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));}
    int index(String uri)throws Exception{for(int i=0;i<grid().getCount();i++)if(((LibraryStore.Entry)grid().getItemAtPosition(i)).uri.equals(uri))return i;return -1;}
    void assertMarked(String uri)throws Exception{
        int i=index(uri);assertTrue(i>=0);View row=grid().getAdapter().getView(i,null,grid());
        View box=(View)field(row,"choice");assertEquals(View.VISIBLE,box.getVisibility());assertTrue(((Checkable)box).isChecked());assertTrue(grid().isItemChecked(i));
    }
    @Test public void folderAndComicCardsHaveSameHeightWhenRecycled()throws Exception{
        View recycled=null;int height=-1;
        for(int i:new int[]{0,1,0,4,0}){
            recycled=grid().getAdapter().getView(i,recycled,grid());
            recycled.measure(View.MeasureSpec.makeMeasureSpec(96,View.MeasureSpec.EXACTLY),View.MeasureSpec.makeMeasureSpec(0,View.MeasureSpec.UNSPECIFIED));
            if(height<0)height=recycled.getMeasuredHeight();else assertEquals("mixed grid row height",height,recycled.getMeasuredHeight());
        }
    }
    @Test public void moveKeepsChecksAcrossFoldersAndCancelRestoresBatch()throws Exception{
        String uri=books.get(0).uri;call("itemLongClick",new Class<?>[]{int.class},index(uri));
        call("beginMove",new Class<?>[0]);settle();assertMarked(uri);
        call("navigate",new Class<?>[]{String.class},folder);settle();
        assertEquals(Collections.singleton(uri),field(screen,"selected"));
        call("navigate",new Class<?>[]{String.class},"");settle();assertMarked(uri);
        int chosen=index(uri);grid().performItemClick(grid().getAdapter().getView(chosen,null,grid()),chosen,chosen);assertMarked(uri);
        int unchosen=index(books.get(1).uri);grid().performItemClick(grid().getAdapter().getView(unchosen,null,grid()),unchosen,unchosen);assertFalse(grid().isItemChecked(unchosen));
        String other=books.get(1).uri;call("itemLongClick",new Class<?>[]{int.class},index(other));
        assertEquals(Collections.singleton(uri),field(screen,"selected"));
        call("cancelMove",new Class<?>[0]);settle();assertTrue((Boolean)field(screen,"batchMode"));assertFalse((Boolean)field(screen,"moving"));assertMarked(uri);
    }
    @Test public void moveFromFolderCancelAndConfirmKeepOriginalItems()throws Exception{
        String uri=books.get(0).uri;library.moveToCollection(Collections.singletonList(books.get(0)),folder);
        call("navigate",new Class<?>[]{String.class},folder);settle();call("itemLongClick",new Class<?>[]{int.class},0);
        call("beginMove",new Class<?>[0]);settle();assertEquals(Collections.singleton(uri),field(screen,"selected"));
        call("cancelMove",new Class<?>[0]);settle();assertEquals(folder,field(screen,"collection"));assertMarked(uri);
        call("beginMove",new Class<?>[0]);settle();call("commitMove",new Class<?>[0]);settle();
        assertFalse((Boolean)field(screen,"moving"));assertFalse((Boolean)field(screen,"batchMode"));assertTrue(((Set<?>)field(screen,"selected")).isEmpty());
        assertTrue(library.browse("",false,"").stream().anyMatch(e->e.uri.equals(uri)));
        assertTrue(library.browse("",false,folder).isEmpty());
    }
    Object cacheCover(String uri)throws Exception{
        android.graphics.Bitmap bitmap=android.graphics.Bitmap.createBitmap(8,8,android.graphics.Bitmap.Config.ARGB_8888);
        Constructor<?> constructor=Class.forName("app.jmbatch.android.LibraryScreen$Cover").getDeclaredConstructor(android.graphics.Bitmap.class);constructor.setAccessible(true);
        Object cover=constructor.newInstance(bitmap);((android.util.LruCache)field(screen,"coverCache")).put(uri,cover);return cover;
    }
    @Test public void movingInDefaultLibraryKeepsCoversWithoutReloading()throws Exception{
        String uri=books.get(0).uri;call("itemLongClick",new Class<?>[]{int.class},index(uri));settle();
        Object cover=cacheCover(uri);Object generation=field(screen,"coverGeneration");Object entries=field(screen,"entries");
        call("beginMove",new Class<?>[0]);assertFalse("menu-only change must not reload",(Boolean)field(screen,"loading"));settle();
        assertSame(entries,field(screen,"entries"));assertEquals(generation,field(screen,"coverGeneration"));assertSame(cover,((android.util.LruCache)field(screen,"coverCache")).get(uri));assertMarked(uri);
        call("cancelMove",new Class<?>[0]);assertFalse((Boolean)field(screen,"loading"));settle();
        assertSame(entries,field(screen,"entries"));assertSame(cover,((android.util.LruCache)field(screen,"coverCache")).get(uri));assertMarked(uri);
    }
    @Test public void movingBetweenFoldersKeepsWarmCoverCache()throws Exception{
        String uri=books.get(0).uri;library.moveToCollection(Collections.singletonList(books.get(0)),folder);
        call("navigate",new Class<?>[]{String.class},folder);settle();call("itemLongClick",new Class<?>[]{int.class},0);settle();
        Object cover=cacheCover(uri);Object generation=field(screen,"coverGeneration");
        call("beginMove",new Class<?>[0]);settle();
        assertEquals("",field(screen,"collection"));assertEquals(generation,field(screen,"coverGeneration"));assertSame(cover,((android.util.LruCache)field(screen,"coverCache")).get(uri));
        call("navigate",new Class<?>[]{String.class},folder);settle();assertMarked(uri);
        call("navigate",new Class<?>[]{String.class},"");settle();call("cancelMove",new Class<?>[0]);settle();
        assertEquals(folder,field(screen,"collection"));assertSame(cover,((android.util.LruCache)field(screen,"coverCache")).get(uri));assertMarked(uri);
    }
}
