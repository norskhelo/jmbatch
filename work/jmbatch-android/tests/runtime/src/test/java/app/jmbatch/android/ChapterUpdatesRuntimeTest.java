package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.os.Looper;
import android.view.View;
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
    void record(List<ChapterRules.Chapter> options,List<ChapterRules.Chapter> selected)throws Exception {LibraryStore.get(context).sync(Collections.singletonList(done(options,selected)));}
    List<String> ids(List<ChapterRules.Chapter> chapters){List<String> ids=new ArrayList<>();for(ChapterRules.Chapter c:chapters)ids.add(c.id);return ids;}
    @Test public void stableIdsSkipOldSelectionsAndSurviveRemovalReordering()throws Exception {
        record(catalog.subList(0,3),catalog.subList(0,1));
        assertEquals(Collections.singletonList("800004"),ids(ChapterUpdates.compare(context,"123456",Arrays.asList(catalog.get(2),catalog.get(0),catalog.get(3))).fresh));
        assertEquals(Collections.singletonList("800004"),ids(ChapterUpdates.compare(context,"123456",catalog).fresh));
    }
    @Test public void legacyPrefixAndUnknownImportEstablishSafeBaseline()throws Exception {
        record(Collections.emptyList(),catalog.subList(0,2));
        assertEquals(Arrays.asList("800003","800004"),ids(ChapterUpdates.compare(context,"123456",catalog).fresh));
        LibraryStore.get(context).importFound(Collections.singletonList(new LibraryStore.Entry("999","import","content://fixture/import","","","zip",false)));
        assertTrue(ChapterUpdates.compare(context,"999",catalog).initialized);
        assertFalse(ChapterUpdates.compare(context,"999",catalog).initialized);
        assertTrue(ChapterUpdates.compare(context,"999",catalog).fresh.isEmpty());
    }
    @Test public void declinedFailedCancelledChecksStayPendingUntilSuccessfulDownload()throws Exception {
        record(catalog.subList(0,2),catalog.subList(0,2));
        for(String status:new String[]{"queued","paused","failed","cancelled"}){
            Store.Task task=done(catalog,catalog);task.status=status;LibraryStore.get(context).sync(Collections.singletonList(task));
            assertEquals(2,ChapterUpdates.compare(context,"123456",catalog).fresh.size());
        }
        record(catalog,catalog);assertTrue(ChapterUpdates.compare(context,"123456",catalog).fresh.isEmpty());
    }
    @Test public void queueUsesNewKeyNormalSettingsRestartAndDuplicateProtection()throws Exception {
        store.tasks.add(done(catalog.subList(0,2),catalog.subList(0,2)));
        Store.Task other=new Store.Task("777",store.settings);other.status="paused";store.tasks.add(other);
        LibraryStore.Entry parent=new LibraryStore.Entry("123456","Original",store.tasks.get(0).resultUri,"",store.settings.outputLabel,store.settings.format,false);
        Store.Task update=store.addChapterUpdate(parent,catalog,catalog.subList(2,4),store.settings);
        assertEquals("queued",update.status);assertEquals("paused",other.status);assertNotEquals(store.tasks.get(0).key,update.key);
        assertEquals(Arrays.asList("800003","800004"),ids(update.selectedChapters));
        assertEquals(store.settings.json().toString(),update.settings.json().toString());
        Store.Task loaded=new Store.Task(update.json());assertEquals(parent.uri,loaded.updateParent);assertEquals("paused",loaded.status);assertEquals(ids(update.selectedChapters),ids(loaded.selectedChapters));
        try{store.addChapterUpdate(parent,catalog,catalog.subList(2,4),store.settings);fail();}catch(IOException expected){}
        update.status="cancelled";
        Field file=Store.class.getDeclaredField("file");file.setAccessible(true);Object original=file.get(store);
        try{
            file.set(store,new android.util.AtomicFile(new File(context.getFilesDir(),"queue.json")){
                @Override public FileOutputStream startWrite()throws IOException {throw new IOException("disk full");}
            });
            try{store.addChapterUpdate(parent,catalog,catalog.subList(2,4),store.settings);fail();}catch(IOException expected){}
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
    interface Fetch { List<ChapterRules.Chapter> get(String id,Store.Settings options,String cookie,JmApi.Control control)throws Exception; }
    int sessions;
    void open(Fetch fetch)throws Exception {
        if(store.tasks.isEmpty()&&LibraryStore.get(context).list("",false).isEmpty())store.tasks.add(done(catalog.subList(0,2),catalog.subList(0,2)));
        controller=Robolectric.buildActivity(Activity.class);Activity activity=controller.get();
        activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup();
        screen=new LibraryScreen(activity,store,(options,cookie,control)->{sessions++;return id->fetch.get(id,options,cookie,control);});screen.show();settle();
    }
    View withText(View root,String text){
        ArrayList<View> matches=new ArrayList<>();
        root.findViewsWithText(matches,text,View.FIND_VIEWS_WITH_TEXT);
        assertFalse(text,matches.isEmpty());
        return matches.get(0);
    }
    void clickCheck()throws Exception {
        Button button=(Button)withText((View)get(screen,"toolbar"),"检查更新");
        assertTrue(button.isEnabled());button.performClick();
    }
    void check()throws Exception {
        clickCheck();
        ((ExecutorService)get(screen,"updateWorker")).submit(()->{}).get(10,TimeUnit.SECONDS);
        settle();
    }
    @Test public void actualLibraryButtonAsksThenDispatchesNormalServiceOnlyAfterConsent()throws Exception {
        int[] calls={0};open((id,options,cookie,control)->{calls[0]++;assertEquals("123456",id);return catalog;});
        check();assertEquals(1,calls[0]);assertEquals(1,store.tasks.size());
        AlertDialog dialog=ShadowAlertDialog.getLatestAlertDialog();assertTrue(dialog.isShowing());
        withText(dialog.getWindow().getDecorView(),"2 章");
        withText(dialog.getWindow().getDecorView(),"取消").performClick();check();
        assertEquals(1,store.tasks.size());dialog=ShadowAlertDialog.getLatestAlertDialog();
        withText(dialog.getWindow().getDecorView(),"确认").performClick();
        settle();
        assertEquals(2,store.tasks.size());assertEquals(Arrays.asList("800003","800004"),ids(store.tasks.get(1).selectedChapters));
        Intent intent=shadowOf(RuntimeEnvironment.getApplication()).getNextStartedService();
        assertEquals(store.tasks.get(0).resultUri,store.tasks.get(1).updateParent);
        assertNotNull(intent);assertEquals(DownloadService.SELECTED,intent.getAction());
        assertEquals(DownloadService.class.getName(),intent.getComponent().getClassName());
    }
    @Test public void tenBooksShareOneSessionWithBoundedParallelism()throws Exception {
        for(int i=0;i<10;i++){
            Store.Task t=new Store.Task(""+(123400+i),store.settings);
            t.status="done";t.resultUri="content://app.jmbatch.android.exports/"+t.id+".zip";t.title=t.id;
            t.chapterOptions=catalog.subList(0,2);t.selectedChapters=t.chapterOptions;store.tasks.add(t);
        }
        java.util.concurrent.atomic.AtomicInteger active=new java.util.concurrent.atomic.AtomicInteger(), peak=new java.util.concurrent.atomic.AtomicInteger(),calls=new java.util.concurrent.atomic.AtomicInteger();
        CountDownLatch firstFour=new CountDownLatch(4);
        open((id,settings,cookie,control)->{
            int current=active.incrementAndGet();peak.accumulateAndGet(current,Math::max);
            try{calls.incrementAndGet();firstFour.countDown();assertTrue(firstFour.await(3,TimeUnit.SECONDS));Thread.sleep(40);return catalog;}
            finally{active.decrementAndGet();}
        });
        long start=System.nanoTime();check();
        assertEquals(1,sessions);assertEquals(10,calls.get());assertEquals(4,peak.get());assertEquals(0,active.get());
        System.out.println("BATCH books=10 sessions="+sessions+" parallel="+peak.get()+" elapsed_ms="+TimeUnit.NANOSECONDS.toMillis(System.nanoTime()-start));
    }
    @Test public void requestFailureNeverQueuesDownloads()throws Exception {
        open((id,options,cookie,control)->{throw new IOException("offline fixture");});
        check();assertEquals(1,store.tasks.size());
        AlertDialog dialog=ShadowAlertDialog.getLatestAlertDialog();
        String text=((TextView)dialog.findViewById(android.R.id.message)).getText().toString();
        assertTrue(text.contains("JM123456"));assertTrue(text.contains("offline fixture"));
    }
    @Test public void oneFailedSeriesDoesNotHideAnotherOrQueueWithoutConsent()throws Exception {
        Store.Task partial=new Store.Task("654321",store.settings);
        partial.status="done";partial.resultUri="content://app.jmbatch.android.exports/partial.pdf";
        partial.settings.format="pdf";partial.chapterOptions=catalog.subList(0,3);partial.selectedChapters=catalog.subList(0,1);
        store.tasks.add(partial);
        Store.Task duplicate=done(catalog.subList(0,2),catalog.subList(0,2));
        store.tasks.add(duplicate);
        Store.Task latest=done(catalog.subList(0,2),catalog.subList(1,2));
        latest.resultUri=duplicate.resultUri+"-copy";store.tasks.add(latest);
        List<String> requested=Collections.synchronizedList(new ArrayList<>());
        open((id,options,cookie,control)->{
            requested.add(id);control.check();
            if(id.equals("123456"))throw new IOException("fixture timeout");
            return catalog;
        });
        check();assertEquals(2,requested.size());assertEquals(new HashSet<>(Arrays.asList("123456","654321")),new HashSet<>(requested));
        AlertDialog dialog=ShadowAlertDialog.getLatestAlertDialog();
        String text=((TextView)dialog.findViewById(android.R.id.message)).getText().toString();
        assertTrue(text.contains("JM654321"));assertTrue(text.contains("1 章"));
        assertTrue(text.contains("JM123456"));assertTrue(text.contains("fixture timeout"));
        assertEquals(3,store.tasks.size());
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).performClick();settle();
        assertEquals(4,store.tasks.size());assertEquals("654321",store.tasks.get(3).id);
        assertEquals(Collections.singletonList("800004"),ids(store.tasks.get(3).selectedChapters));
    }
    @Test public void deletedLegacyUpdateAndEmptyQueueUseOriginal76Folders()throws Exception {
        catalog.clear();
        for(int i=1;i<=245;i++)catalog.add(new ChapterRules.Chapter(""+(900000+i),i,"Chapter "+i));
        File root=new File(AlbumStorage.root(context),"JM1452133-fixture-"+UUID.randomUUID().toString().substring(0,8));
        for(int i=1;i<=76;i++){
            File folder=new File(root,String.format(Locale.ROOT,"%04d",i));assertTrue(folder.mkdirs());
            Files.write(new File(folder,"00001.jpg").toPath(),new byte[]{7});
        }
        String uri=ExportProvider.uri(context,root).toString();
        LibraryStore library=LibraryStore.get(context);
        library.importFound(Collections.singletonList(new LibraryStore.Entry("1452133","Original",uri,"","local","images",false,"",76)));
        JSONObject legacy=new JSONObject().put("1452133",new JSONObject().put("known",new JSONArray(ids(catalog))));
        Files.write(new File(context.getFilesDir(),"chapter-updates.json").toPath(),legacy.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));

        open((id,settings,cookie,control)->{assertEquals("1452133",id);return catalog;});
        check();assertTrue(store.tasks.isEmpty());
        AlertDialog dialog=ShadowAlertDialog.getLatestAlertDialog();
        assertNotNull("Expected an update prompt for the deleted volume",dialog);
        withText(dialog.getWindow().getDecorView(),"169 章");
        withText(dialog.getWindow().getDecorView(),"确认").performClick();settle();
        assertEquals(1,store.tasks.size());assertEquals(uri,store.tasks.get(0).updateParent);
        assertEquals(ids(catalog.subList(76,245)),ids(store.tasks.get(0).selectedChapters));
        assertEquals(76,root.list().length);
        Field field=LibraryStore.class.getDeclaredField("instance");field.setAccessible(true);field.set(null,null);
        List<ChapterRules.Chapter> reordered=new ArrayList<>(catalog);Collections.reverse(reordered);
        List<ChapterRules.Chapter> fresh=ChapterUpdates.compare(context,"1452133",reordered).fresh;
        assertEquals(169,fresh.size());assertEquals("900245",fresh.get(0).id);
    }

    @Test public void oldDocumentTreeReadsChapterDirectoriesAndKeepsNewInsertionsPending()throws Exception {
        ChapterDeletionRuntimeTest fixture=new ChapterDeletionRuntimeTest();fixture.setup();
        LibraryStore.Entry original=fixture.fixture(false,true);
        JSONObject legacy=new JSONObject().put(original.id,new JSONObject().put("known",new JSONArray(ids(catalog))));
        Files.write(new File(context.getFilesDir(),"chapter-updates.json").toPath(),legacy.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
        ChapterRules.Chapter inserted=new ChapterRules.Chapter("700000",1,"Inserted");
        List<ChapterRules.Chapter> remote=new ArrayList<>(catalog);remote.add(0,inserted);
        assertEquals(Arrays.asList("700000","800004"),ids(ChapterUpdates.compare(context,original.id,remote).fresh));
    }
    @Test public void unrelatedImportCannotMaskUpdatesForTrackedCopy()throws Exception {
        record(catalog.subList(0,2),catalog.subList(0,1));
        LibraryStore.get(context).importFound(Collections.singletonList(new LibraryStore.Entry("123456","Extra","content://fixture/other","","","pdf",false)));
        assertEquals(ids(catalog.subList(2,4)),ids(ChapterUpdates.compare(context,"123456",catalog).fresh));
    }
    @Test public void removingOnlyTheTaskKeepsCoverageDeletingItsFileRestoresUpdates()throws Exception {
        Store.Task first=done(catalog.subList(0,2),catalog.subList(0,1)),update=done(catalog,catalog.subList(2,4));
        File folder=AlbumStorage.root(context);folder.mkdirs();
        File file=new File(folder,"JM123456-extra-abcdef12.zip");
        Files.write(file.toPath(),new byte[]{1,2});
        update.resultUri=ExportProvider.uri(context,file).toString();update.settings.format="zip";
        store.tasks.add(first);store.tasks.add(update);
        LibraryStore library=LibraryStore.get(context);library.sync(store.snapshot());
        TaskRecordRemoval.prepare(store,null);assertTrue(store.snapshot().isEmpty());
        assertTrue(ChapterUpdates.compare(context,first.id,catalog).fresh.isEmpty());
        library.remove(store,library.byUri(update.resultUri),true);assertFalse(file.exists());
        assertEquals(ids(catalog.subList(2,4)),ids(ChapterUpdates.compare(context,first.id,catalog).fresh));
    }
    @Test public void fetchPreservesCallersCancellationReason()throws Exception {
        JmApi.Control control=new JmApi.Control();
        control.cancel("检查已取消");
        try{ChapterUpdates.open(store.settings,"",control).get("654321");fail();}catch(IOException expected){}
        assertEquals("检查已取消",control.stop);
    }
    @Test public void legacySingleLocalChapterCanBelongToSeries()throws Exception {
        Store.Task legacy=done(Collections.emptyList(),catalog.subList(0,1));
        legacy.settings.format="pdf";
        store.tasks.add(legacy);
        Store.Task single=new Store.Task("700",store.settings);
        single.status="done";single.resultUri="content://app.jmbatch.android.exports/single.zip";
        single.selectedChapters=catalog.subList(0,1);single.chapterOptions=single.selectedChapters;
        store.tasks.add(single);
        List<String> requested=Collections.synchronizedList(new ArrayList<>());
        open((id,options,cookie,control)->{requested.add(id);return catalog;});
        check();
        assertEquals(Collections.singletonList(legacy.id),requested);
        withText(ShadowAlertDialog.getLatestAlertDialog().getWindow().getDecorView(),"3 章");
    }
    @Test public void cancellationDuringMetadataCheckLeavesQueueAndHistoryUnchanged()throws Exception {
        CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
        open((id,options,cookie,control)->{entered.countDown();assertTrue(release.await(5,TimeUnit.SECONDS));assertEquals("检查已取消",control.stop);return catalog;});
        clickCheck();
        assertTrue(entered.await(5,TimeUnit.SECONDS));call("cancel",new Class<?>[0]);release.countDown();
        ((ExecutorService)get(screen,"updateWorker")).submit(()->{}).get(10,TimeUnit.SECONDS);settle();
        assertNull(ShadowAlertDialog.getLatestAlertDialog());
        assertEquals(1,store.tasks.size());assertEquals(2,ChapterUpdates.compare(context,"123456",catalog).fresh.size());
    }
    @After public void close()throws Exception {
        AlertDialog dialog=ShadowAlertDialog.getLatestAlertDialog();if(dialog!=null)dialog.dismiss();
        if(screen!=null)screen.close();if(controller!=null)controller.pause().stop().destroy();
        shadowOf(Looper.getMainLooper()).idle();
        if(screen!=null){((ExecutorService)get(screen,"worker")).awaitTermination(10,TimeUnit.SECONDS);((ExecutorService)get(screen,"coverWorker")).awaitTermination(10,TimeUnit.SECONDS);}
    }
}
