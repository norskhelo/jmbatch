package app.jmbatch.android;

import android.app.Activity;
import android.content.Context;
import android.os.Looper;
import android.view.View;
import android.view.ViewGroup;
import android.widget.*;
import java.io.*;
import java.lang.reflect.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.android.controller.ActivityController;
import org.robolectric.annotation.*;
import org.robolectric.shadows.ShadowPopupMenu;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},shadows={CollectionRuntimeTest.WindowsAtomicRename.class})
@LooperMode(LooperMode.Mode.PAUSED)
public class LibrarySortRuntimeTest {
    Context context;LibraryStore library;List<LibraryStore.Entry> comics;
    ActivityController<Activity> controller;LibraryScreen screen;
    @Before public void setup()throws Exception {
        context=RuntimeEnvironment.getApplication();
        for(Class<?> type:new Class<?>[]{Store.class,LibraryStore.class}) {Field f=type.getDeclaredField("instance");f.setAccessible(true);f.set(null,null);}
        new android.util.AtomicFile(new File(context.getFilesDir(),"library.json")).delete();
        new android.util.AtomicFile(new File(context.getFilesDir(),"queue.json")).delete();
        library=LibraryStore.get(context);comics=new ArrayList<>();
    }
    @After public void close()throws Exception {
        if(screen!=null)screen.close();
        if(controller!=null)controller.pause().stop().destroy();
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));
    }
    LibraryStore.Entry book(String title,boolean favorite,int chapters,String folder)throws Exception {
        File dir=new File(AlbumStorage.root(context),"JM123-"+UUID.randomUUID()+"-12345678");assertTrue(dir.mkdirs());
        for(int i=1;i<=chapters;i++) {
            File page=new File(dir,String.format("%04d/00001.jpg",i));assertTrue(page.getParentFile().mkdirs());
            java.nio.file.Files.write(page.toPath(),new byte[]{1,2,3});
        }
        assertTrue(dir.setLastModified(1_700_000_000_000L+chapters*10_000));
        LibraryStore.Entry e=new LibraryStore.Entry(title,title,ExportProvider.uri(context,dir).toString(),"","fixture","images",favorite,folder);
        comics.add(e);return e;
    }
    List<String> titles(List<LibraryStore.Entry> entries){List<String> result=new ArrayList<>();for(LibraryStore.Entry e:entries)result.add(e.title);return result;}
    @Test public void pinyinComparesEveryCharacterAndPreservesSyllableBoundaries() {
        List<String> names=new ArrayList<>(Arrays.asList("安中白","白安","安中阿","安波","安","安阿"));
        names.sort((a,b)->NameSort.compare(NameSort.key(a),NameSort.key(b)));
        assertEquals(Arrays.asList("安","安阿","安波","安中阿","安中白","白安"),names);
        names=new ArrayList<>(Arrays.asList("先安","西中","先","西安","西"));
        names.sort((a,b)->NameSort.compare(NameSort.key(a),NameSort.key(b)));
        assertEquals(Arrays.asList("西","西安","西中","先","先安"),names);
        names=new ArrayList<>(Arrays.asList("安白","鞍阿","安阿"));
        names.sort((a,b)->NameSort.compare(NameSort.key(a),NameSort.key(b)));
        assertEquals(Arrays.asList("鞍阿","安阿","安白"),names);
        assertArrayEquals(new String[]{"he","a"},NameSort.key("𠀀阿"));
        assertArrayEquals(new String[]{"𠮷","a"},NameSort.key("𠮷阿"));
        assertArrayEquals(new String[]{"nv"},NameSort.key("女"));
        assertArrayEquals(new String[]{"fan","ti"},NameSort.key("繁體"));
        assertTrue(NameSort.compare(NameSort.key("\ue000"),NameSort.key("😀"))<0);
        names=new ArrayList<>(Arrays.asList("A2","a10","A1","a","[安]","","安"));
        names.sort((a,b)->NameSort.compare(NameSort.key(a),NameSort.key(b)));
        assertEquals(Arrays.asList("","[安]","a","A1","a10","A2","安"),names);
    }
    @Test public void pinyinSortsAllGroupsAndBreaksMetadataTies()throws Exception {
        library.createCollection("白安");library.createCollection("安阿");
        book("安白",false,1,"");book("安阿",false,1,"");
        book("白安",true,1,"");book("安阿",true,1,"");library.importFound(comics);
        List<LibraryStore.Entry> source=library.browse("",false,"");
        for(String mode:new String[]{"name","size","time","chapters"})
            assertEquals(mode,Arrays.asList("安阿","白安","安阿","白安","安阿","安白"),titles(LibrarySort.sorted(context,source,mode)));
    }
    @Test public void allModesSortEveryGroupAndAllFolderMembers()throws Exception {
        String a=library.createCollection("A folder"),z=library.createCollection("Z folder"),empty=library.createCollection("Empty");
        book("B ordinary",false,1,"");book("A ordinary",false,2,"");
        book("D favorite",true,1,"");book("C favorite",true,2,"");
        for(int i=0;i<5;i++)book("member a "+i,false,i==4?3:1,a);
        book("member z",true,2,z);
        library.importFound(comics);
        assertTrue(library.fillChapterCounts(library.list("",false)));
        assertTrue(library.fillSizes(library.list("",false)));
        List<LibraryStore.Entry> source=library.browse("",false,"");
        assertEquals(Arrays.asList("A folder","Empty","Z folder","C favorite","D favorite","A ordinary","B ordinary"),titles(LibrarySort.sorted(context,source,"name")));
        for(String mode:new String[]{"size","time","chapters"}) {
            List<String> expected=Arrays.asList("A folder","Z folder","Empty","C favorite","D favorite","A ordinary","B ordinary");
            assertEquals(mode,expected,titles(LibrarySort.sorted(context,source,mode)));
            assertEquals(mode,expected,titles(LibrarySort.sorted(context,source,mode)));
        }
        assertEquals(Arrays.asList("member z"),titles(LibrarySort.sorted(context,library.browse("",false,z),"chapters")));
        assertEquals(7,source.size());
    }
    static Object field(Object object,String name)throws Exception {Field f=object.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(object);}
    void settle()throws Exception {for(int i=0;i<2;i++){((ExecutorService)field(screen,"worker")).submit(()->{}).get(10,TimeUnit.SECONDS);shadowOf(Looper.getMainLooper()).idleFor(Duration.ofSeconds(1));}}
    static Button button(View view,String description) {
        if(view instanceof Button&&description.contentEquals(view.getContentDescription()==null?"":view.getContentDescription()))return (Button)view;
        if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++){Button b=button(((ViewGroup)view).getChildAt(i),description);if(b!=null)return b;}
        return null;
    }
    @Test public void toolbarKeepsIconAndRepeatedMenuChoiceStaysAscending()throws Exception {
        library.createCollection("Z folder");book("Z favorite",true,1,"");book("A favorite",true,1,"");book("A ordinary",false,1,"");library.importFound(comics);
        controller=Robolectric.buildActivity(Activity.class);Activity activity=controller.get();activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup();
        screen=new LibraryScreen(activity,Store.get(activity));screen.show();settle();
        Button sort=(Button)field(screen,"sortButton");assertEquals("排序方式",sort.getText().toString());
        Button create=button((View)field(screen,"page"),"新建收藏夹");assertNotNull(create);assertFalse(create.getText().toString().contains("新建收藏夹"));
        for(int repeat=0;repeat<2;repeat++) {
            sort.performClick();PopupMenu popup=ShadowPopupMenu.getLatestPopupMenu();assertNotNull(popup);
            shadowOf(popup).getOnMenuItemClickListener().onMenuItemClick(popup.getMenu().getItem(0));popup.dismiss();settle();
            @SuppressWarnings("unchecked") List<LibraryStore.Entry> entries=(List<LibraryStore.Entry>)field(screen,"entries");
            assertEquals(Arrays.asList("Z folder","A favorite","Z favorite","A ordinary"),titles(entries));
            assertEquals("排序方式",sort.getText().toString());
        }
        create.performClick();shadowOf(Looper.getMainLooper()).idle();assertTrue(org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog().isShowing());
        org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog().dismiss();
    }

    @Test public void completionPersistsCountsAfterQueueRemovalFavoritesAndMoves()throws Exception {
        Store store=Store.get(context);List<Store.Task> tasks=new ArrayList<>();
        for(String format:new String[]{"images","zip","pdf"}){
            Store.Settings settings=new Store.Settings();settings.format=format;
            Store.Task task=new Store.Task("123",settings);task.status="done";task.title=format;
            task.resultUri=ExportProvider.uri(context,new File(AlbumStorage.root(context),"JM123-missing-12345678."+format)).toString();
            task.selectedChapters=Arrays.asList(new ChapterRules.Chapter("101",1,"one"),new ChapterRules.Chapter("109",9,"nine"));tasks.add(task);
        }
        library.sync(tasks);String folder=library.createCollection("saved");
        library.setFavorites(library.list("",false),true);library.moveToCollection(library.list("",false),folder);
        Field instance=LibraryStore.class.getDeclaredField("instance");instance.setAccessible(true);instance.set(null,null);
        library=LibraryStore.get(context);library.sync(Collections.emptyList());
        assertEquals(3,library.list("",false).size());
        for(LibraryStore.Entry entry:library.list("",false)){assertEquals(2,entry.chapterCount);assertTrue(entry.favorite);assertEquals(folder,entry.collection);}
        assertFalse(library.fillChapterCounts(library.list("",false)));
        assertEquals(Arrays.asList("images","pdf","zip"),titles(LibrarySort.sorted(context,library.browse("",false,folder),"chapters")));
    }

    @Test public void oldMetadataIsSavedOnceAndSortingDoesNotReadFiles()throws Exception {
        LibraryStore.Entry one=book("Z one",false,1,""),many=book("A many",false,3,"");library.importFound(comics);
        assertTrue(library.fillChapterCounts(library.list("",false)));
        for(LibraryStore.Entry entry:comics){File file=AlbumStorage.local(context,android.net.Uri.parse(entry.uri));assertTrue(file.renameTo(new File(file.getParentFile(),file.getName()+"-moved")));}
        Field instance=LibraryStore.class.getDeclaredField("instance");instance.setAccessible(true);instance.set(null,null);library=LibraryStore.get(context);
        assertFalse(library.fillChapterCounts(library.list("",false)));
        for(int i=0;i<3;i++)assertEquals(Arrays.asList("A many","Z one"),titles(LibrarySort.sorted(context,library.list("",false),"chapters")));
    }

    @Test public void chapterAndSizeMenusSortImmediatelyWhileMetadataWorkerIsOccupied()throws Exception {
        book("Z one",false,1,"");book("A many",false,3,"");library.importFound(comics);library.fillChapterCounts(library.list("",false));
        controller=Robolectric.buildActivity(Activity.class);Activity activity=controller.get();activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup();
        screen=new LibraryScreen(activity,Store.get(activity));screen.show();settle();
        CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
        ((ExecutorService)field(screen,"worker")).submit(()->{entered.countDown();try{release.await(10,TimeUnit.SECONDS);}catch(InterruptedException e){Thread.currentThread().interrupt();}});
        assertTrue(entered.await(5,TimeUnit.SECONDS));
        try{
            for(int choice:new int[]{2,3,2}){
                Button sort=(Button)field(screen,"sortButton");sort.performClick();PopupMenu popup=ShadowPopupMenu.getLatestPopupMenu();
                shadowOf(popup).getOnMenuItemClickListener().onMenuItemClick(popup.getMenu().getItem(choice));popup.dismiss();
                assertFalse((Boolean)field(screen,"loading"));
                @SuppressWarnings("unchecked") List<LibraryStore.Entry> entries=(List<LibraryStore.Entry>)field(screen,"entries");
                assertEquals(Arrays.asList("A many","Z one"),titles(entries));
            }
        }finally{release.countDown();}
    }

    @Test public void sizeCacheSurvivesFavoriteMoveSyncAndRestartWithoutReadingFiles()throws Exception {
        book("A small",false,1,"");book("Z large",false,3,"");library.importFound(comics);
        assertTrue(library.fillSizes(library.list("",false)));
        // Filling the chapter cache later must retain already cached sizes.
        assertTrue(library.fillChapterCounts(library.list("",false)));
        String folder=library.createCollection("saved");library.moveToCollection(library.list("",false),folder);
        library.setFavorites(library.list("",false),true);library.favorite(library.list("",false).get(0));library.setFavorites(library.list("",false),true);
        Store.Task renamed=new Store.Task("A small",new Store.Settings());renamed.status="done";renamed.title="B small";renamed.resultUri=comics.get(0).uri;library.sync(Collections.singletonList(renamed));
        for(LibraryStore.Entry entry:comics){File file=AlbumStorage.local(context,android.net.Uri.parse(entry.uri));assertTrue(file.renameTo(new File(file.getParentFile(),file.getName()+"-moved")));}
        Field instance=LibraryStore.class.getDeclaredField("instance");instance.setAccessible(true);instance.set(null,null);library=LibraryStore.get(context);
        assertFalse(library.fillSizes(library.list("",false)));
        for(LibraryStore.Entry entry:library.list("",false)){assertTrue(entry.favorite);assertEquals(folder,entry.collection);assertEquals(entry.title.equals("Z large")?9:3,entry.sizeBytes);}
        for(int i=0;i<3;i++)assertEquals(Arrays.asList("Z large","B small"),titles(LibrarySort.sorted(context,library.browse("",false,folder),"size")));
    }

    @Test public void sizeCacheMigratesLegacyRecordsAndRetriesMissingFiles()throws Exception {
        File root=AlbumStorage.root(context);root.mkdirs();File missing=new File(root,"JM123-size.zip");
        LibraryStore.Entry item=new LibraryStore.Entry("123","cached",ExportProvider.uri(context,missing).toString(),"","","zip",false,"",1);
        org.json.JSONObject legacy=item.json();legacy.remove("sizeBytes");assertEquals(-1,new LibraryStore.Entry(legacy).sizeBytes);
        library.importFound(Collections.singletonList(new LibraryStore.Entry(legacy)));
        assertFalse(library.fillSizes(library.list("",false)));assertEquals(-1,library.list("",false).get(0).sizeBytes);
        assertTrue(missing.createNewFile());assertTrue(library.fillSizes(library.list("",false)));assertEquals(0,library.list("",false).get(0).sizeBytes);
    }

    public static class SizeProvider extends android.content.ContentProvider {
        int queries;Long bytes;CountDownLatch entered,release;
        @Override public boolean onCreate(){return true;}
        @Override public android.database.Cursor query(android.net.Uri uri,String[] columns,String selection,String[] args,String order){
            queries++;if(entered!=null){entered.countDown();try{release.await(5,TimeUnit.SECONDS);}catch(InterruptedException e){Thread.currentThread().interrupt();}}
            android.database.MatrixCursor cursor=new android.database.MatrixCursor(columns);cursor.addRow(new Object[]{bytes});return cursor;
        }
        @Override public String getType(android.net.Uri uri){return "application/zip";}
        @Override public android.net.Uri insert(android.net.Uri uri,android.content.ContentValues values){throw new UnsupportedOperationException();}
        @Override public int delete(android.net.Uri uri,String s,String[] args){throw new UnsupportedOperationException();}
        @Override public int update(android.net.Uri uri,android.content.ContentValues v,String s,String[] args){throw new UnsupportedOperationException();}
    }
    @Test public void providerSizeIsPrefetchedWithoutBlockingCachedSortOrCachingUnknownAsZero()throws Exception {
        SizeProvider provider=new SizeProvider();android.content.pm.ProviderInfo info=new android.content.pm.ProviderInfo();info.authority="sizes.test";provider.attachInfo(context,info);
        org.robolectric.shadows.ShadowContentResolver.registerProviderInternal(info.authority,provider);
        library.importFound(Collections.singletonList(new LibraryStore.Entry("123","remote","content://sizes.test/book.zip","","","zip",false,"",1)));
        List<LibraryStore.Entry> pending=library.list("",false);LibrarySort.sorted(context,pending,"size");assertEquals(0,provider.queries);
        assertFalse(library.fillSizes(pending));assertEquals(-1,library.list("",false).get(0).sizeBytes);
        provider.bytes=12345L;provider.entered=new CountDownLatch(1);provider.release=new CountDownLatch(1);
        ExecutorService io=Executors.newFixedThreadPool(2);
        try{
            Future<Boolean> fill=io.submit(()->library.fillSizes(pending));assertTrue(provider.entered.await(5,TimeUnit.SECONDS));
            assertEquals(1,io.submit(()->LibrarySort.sorted(context,library.list("",false),"size")).get(2,TimeUnit.SECONDS).size());
            provider.release.countDown();assertTrue(fill.get(5,TimeUnit.SECONDS));
        }finally{provider.release.countDown();io.shutdownNow();}
        int reads=provider.queries;provider.bytes=null;
        for(int i=0;i<4;i++)assertEquals(12345,LibrarySort.sorted(context,library.list("",false),"size").get(0).sizeBytes);
        assertFalse(library.fillSizes(library.list("",false)));assertEquals(reads,provider.queries);
    }
}
