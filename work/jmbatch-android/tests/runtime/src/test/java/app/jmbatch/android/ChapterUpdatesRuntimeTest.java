package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.os.Looper;
import android.widget.Button;
import android.widget.TextView;
import java.io.*;
import java.lang.reflect.*;
import java.nio.file.Files;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.*;
import org.robolectric.android.controller.ActivityController;
import org.robolectric.shadows.ShadowAlertDialog;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},qualifiers="w360dp-h800dp-mdpi",shadows={CollectionRuntimeTest.WindowsAtomicRename.class})
@LooperMode(LooperMode.Mode.PAUSED)
public class ChapterUpdatesRuntimeTest {
    Context context;Store store;ActivityController<Activity> controller;LibraryScreen screen;
    List<ChapterRules.Chapter> catalog;
    static Object get(Object target,String name)throws Exception {Field f=target.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(target);}
    void call(String name,Class<?>[] types,Object... args)throws Exception {Method m=LibraryScreen.class.getDeclaredMethod(name,types);m.setAccessible(true);m.invoke(screen,args);}
    @Before public void reset()throws Exception {
        context=RuntimeEnvironment.getApplication();new Instrumentation().setInTouchMode(true);
        for(Class<?> type:new Class<?>[]{Store.class,LibraryStore.class}){Field f=type.getDeclaredField("instance");f.setAccessible(true);f.set(null,null);}
        for(String name:new String[]{"queue.json","queue.json.bak","library.json","library.json.bak","chapter-updates.json","chapter-updates.json.bak"})
            Files.deleteIfExists(new File(context.getFilesDir(),name).toPath());
        store=Store.get(context);catalog=new ArrayList<>();
        for(int i=0;i<4;i++)catalog.add(new ChapterRules.Chapter(""+(800001+i),i+1,"Chapter "+(i+1)));
    }
    Store.Task done(List<ChapterRules.Chapter> options,List<ChapterRules.Chapter> selected){
        Store.Task t=new Store.Task("123456",store.settings);t.status="done";t.resultUri="content://app.jmbatch.android.exports/old.zip";
        t.chapterOptions=options;t.selectedChapters=selected;return t;
    }
    void record(List<ChapterRules.Chapter> options,List<ChapterRules.Chapter> selected)throws Exception {ChapterUpdates.record(context,Collections.singletonList(done(options,selected)));}
    List<String> ids(List<ChapterRules.Chapter> chapters){List<String> ids=new ArrayList<>();for(ChapterRules.Chapter c:chapters)ids.add(c.id);return ids;}
    @Test public void stableIdsSkipOldSelectionsAndSurviveRemovalReordering()throws Exception {
        record(catalog.subList(0,3),catalog.subList(0,1));
        assertEquals(Collections.singletonList("800004"),ids(ChapterUpdates.compare(context,"123456",Arrays.asList(catalog.get(2),catalog.get(0),catalog.get(3))).fresh));
        assertEquals(Collections.singletonList("800004"),ids(ChapterUpdates.compare(context,"123456",catalog).fresh));
    }
    @Test public void legacyPrefixAndUnknownImportEstablishSafeBaseline()throws Exception {
        record(Collections.emptyList(),catalog.subList(0,2));
        assertEquals(Arrays.asList("800003","800004"),ids(ChapterUpdates.compare(context,"123456",catalog).fresh));
        assertTrue(ChapterUpdates.compare(context,"999",catalog).initialized);
        assertFalse(ChapterUpdates.compare(context,"999",catalog).initialized);
        assertTrue(ChapterUpdates.compare(context,"999",catalog).fresh.isEmpty());
    }
    @Test public void declinedFailedCancelledChecksStayPendingUntilSuccessfulDownload()throws Exception {
        record(catalog.subList(0,2),catalog.subList(0,2));
        for(String status:new String[]{"queued","paused","failed","cancelled"}){
            Store.Task task=done(catalog,catalog);task.status=status;ChapterUpdates.record(context,Collections.singletonList(task));
            assertEquals(2,ChapterUpdates.compare(context,"123456",catalog).fresh.size());
        }
        record(catalog,catalog);assertTrue(ChapterUpdates.compare(context,"123456",catalog).fresh.isEmpty());
    }
    @Test public void queueUsesNewKeyNormalSettingsRestartAndDuplicateProtection()throws Exception {
        store.tasks.add(done(catalog.subList(0,2),catalog.subList(0,2)));
        Store.Task other=new Store.Task("777",store.settings);other.status="paused";store.tasks.add(other);
        Store.Task update=store.addChapterUpdate("123456",catalog,catalog.subList(2,4),store.settings);
        assertEquals("queued",update.status);assertEquals("paused",other.status);assertNotEquals(store.tasks.get(0).key,update.key);
        assertEquals(Arrays.asList("800003","800004"),ids(update.selectedChapters));
        assertEquals(store.settings.json().toString(),update.settings.json().toString());
        Store.Task loaded=new Store.Task(update.json());assertEquals("paused",loaded.status);assertEquals(ids(update.selectedChapters),ids(loaded.selectedChapters));
        try{store.addChapterUpdate("123456",catalog,catalog.subList(2,4),store.settings);fail();}catch(IOException expected){}
        update.status="cancelled";
        Field file=Store.class.getDeclaredField("file");file.setAccessible(true);Object original=file.get(store);
        try{
            file.set(store,new android.util.AtomicFile(new File(context.getFilesDir(),"queue.json")){
                @Override public FileOutputStream startWrite()throws IOException {throw new IOException("disk full");}
            });
            try{store.addChapterUpdate("123456",catalog,catalog.subList(2,4),store.settings);fail();}catch(IOException expected){}
            assertEquals(3,store.tasks.size());
        }finally{file.set(store,original);}
    }
    @Test public void sharedCatalogParserUsesRemoteOrderAndRejectsDuplicates()throws Exception {
        JSONObject album=new JSONObject().put("series",new JSONArray().put(new JSONObject().put("id","99").put("sort",2)).put(new JSONObject().put("id","88").put("sort",1)));
        assertEquals(Arrays.asList("88","99"),ids(ChapterSelection.catalog(album,"123")));
        album.getJSONArray("series").put(new JSONObject().put("id","88"));
        try{ChapterSelection.catalog(album,"123");fail();}catch(IllegalArgumentException expected){}
        try{ChapterUpdates.compare(context,"123",Collections.emptyList());fail();}catch(IllegalArgumentException expected){}
        assertFalse(new File(context.getFilesDir(),"chapter-updates.json").exists());
    }
    void settle()throws Exception {
        for(int i=0;i<3;i++){
            ((ExecutorService)get(screen,"worker")).submit(()->{}).get(10,TimeUnit.SECONDS);
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(100));
        }
    }
    void open(ChapterUpdates.Fetch fetch)throws Exception {
        store.tasks.add(done(catalog.subList(0,2),catalog.subList(0,2)));
        controller=Robolectric.buildActivity(Activity.class);Activity activity=controller.get();
        activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup();
        screen=new LibraryScreen(activity,store,fetch);screen.show();settle();
        call("setBatchMode",new Class<?>[]{boolean.class},true);call("itemClick",new Class<?>[]{int.class},0);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(100));
    }
    void check()throws Exception {
        @SuppressWarnings("unchecked") List<Button> buttons=(List<Button>)get(screen,"singleButtons");
        Button button=buttons.stream().filter(b->b.getText().toString().equals("检查更新")).findFirst().get();
        assertTrue(button.isEnabled());button.performClick();settle();
    }
    @Test public void actualLibraryButtonAsksThenDispatchesNormalServiceOnlyAfterConsent()throws Exception {
        int[] calls={0};open((id,options,cookie,control)->{calls[0]++;assertEquals("123456",id);return catalog;});
        check();assertEquals(1,calls[0]);assertEquals(1,store.tasks.size());
        AlertDialog dialog=ShadowAlertDialog.getLatestAlertDialog();assertTrue(dialog.isShowing());
        assertTrue(((TextView)dialog.findViewById(android.R.id.message)).getText().toString().contains("发现 2"));
        dialog.getButton(AlertDialog.BUTTON_NEGATIVE).performClick();check();
        assertEquals(1,store.tasks.size());dialog=ShadowAlertDialog.getLatestAlertDialog();
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).performClick();
        settle();
        assertEquals(2,store.tasks.size());assertEquals(Arrays.asList("800003","800004"),ids(store.tasks.get(1).selectedChapters));
        Intent intent=shadowOf(RuntimeEnvironment.getApplication()).getNextStartedService();
        assertNotNull(intent);assertEquals(DownloadService.SELECTED,intent.getAction());
        assertEquals(DownloadService.class.getName(),intent.getComponent().getClassName());
    }
    @Test public void requestFailureNeverQueuesDownloads()throws Exception {
        open((id,options,cookie,control)->{throw new IOException("offline fixture");});
        check();assertEquals(1,store.tasks.size());
        AlertDialog dialog=ShadowAlertDialog.getLatestAlertDialog();assertTrue(((TextView)dialog.findViewById(android.R.id.message)).getText().toString().contains("offline fixture"));
    }
    @Test public void cancellationDuringMetadataCheckLeavesQueueAndHistoryUnchanged()throws Exception {
        CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
        open((id,options,cookie,control)->{entered.countDown();assertTrue(release.await(5,TimeUnit.SECONDS));assertEquals("检查已取消",control.stop);return catalog;});
        LibraryStore.Entry entry=LibraryStore.get(context).list("",false).get(0);
        call("checkUpdates",new Class<?>[]{LibraryStore.Entry.class},entry);
        assertTrue(entered.await(5,TimeUnit.SECONDS));call("cancel",new Class<?>[0]);release.countDown();settle();
        assertEquals(1,store.tasks.size());assertEquals(2,ChapterUpdates.compare(context,"123456",catalog).fresh.size());
    }
    @After public void close()throws Exception {
        AlertDialog dialog=ShadowAlertDialog.getLatestAlertDialog();if(dialog!=null)dialog.dismiss();
        if(screen!=null)screen.close();if(controller!=null)controller.pause().stop().destroy();
        shadowOf(Looper.getMainLooper()).idle();
        if(screen!=null){((ExecutorService)get(screen,"worker")).awaitTermination(10,TimeUnit.SECONDS);((ExecutorService)get(screen,"coverWorker")).awaitTermination(10,TimeUnit.SECONDS);}
    }
}
