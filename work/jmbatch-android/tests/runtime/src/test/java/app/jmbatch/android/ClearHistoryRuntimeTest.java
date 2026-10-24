package app.jmbatch.android;

import android.app.*;
import android.content.Intent;
import android.graphics.Rect;
import android.os.*;
import android.util.AtomicFile;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.lang.reflect.*;
import java.nio.file.Files;
import java.time.Duration;
import java.util.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.android.controller.ActivityController;
import org.robolectric.annotation.*;
import org.robolectric.shadows.ShadowAlertDialog;
import org.robolectric.shadows.ShadowToast;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

/** Clear records through the production confirmation dialog, using isolated tasks. */
@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},qualifiers="w360dp-h800dp-mdpi",shadows={CollectionRuntimeTest.WindowsAtomicRename.class})
@LooperMode(LooperMode.Mode.PAUSED)
public class ClearHistoryRuntimeTest {
    ActivityController<MainActivity> controller;
    MainActivity activity;
    Store store;

    static Field field(Class<?> type,String name)throws Exception {Field f=type.getDeclaredField(name);f.setAccessible(true);return f;}
    static Object call(Object target,String name,Class<?>[] types,Object...args)throws Exception {Method m=target.getClass().getDeclaredMethod(name,types);m.setAccessible(true);return m.invoke(target,args);}
    @Before public void setup()throws Exception {
        new Instrumentation().setInTouchMode(true);
        for(Class<?> type:new Class<?>[]{Store.class,LibraryStore.class})field(type,"instance").set(null,null);
        for(String name:new String[]{"queue.json","library.json"})new AtomicFile(new File(RuntimeEnvironment.getApplication().getFilesDir(),name)).delete();
        RuntimeEnvironment.getApplication().getSharedPreferences("updates",0).edit().putBoolean("automatic",false).commit();
        controller=Robolectric.buildActivity(MainActivity.class);activity=controller.get();activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup().visible();
        store=Store.get(activity);
        ((Handler)field(MainActivity.class,"handler").get(activity)).removeCallbacksAndMessages(null);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(100));
    }
    @After public void close()throws Exception {
        if(controller!=null){AlertDialog dialog=ShadowAlertDialog.getLatestAlertDialog();if(dialog!=null)dialog.dismiss();controller.pause().stop().destroy();shadowOf(Looper.getMainLooper()).idle();}
    }
    Store.Task task(String status) {
        Store.Task task=new Store.Task("99"+(store.tasks.size()+1),new Store.Settings());task.status=status;task.title="fixture-"+status;store.tasks.add(task);return task;
    }
    static Button button(View root,String label) {
        if(root instanceof Button&&(label.equals(root.getContentDescription())||label.contentEquals(((Button)root).getText())))return (Button)root;
        if(root instanceof ViewGroup)for(int i=0;i<((ViewGroup)root).getChildCount();i++){Button b=button(((ViewGroup)root).getChildAt(i),label);if(b!=null)return b;}
        return null;
    }
    AlertDialog confirm()throws Exception {
        Button clear=button(activity.getWindow().getDecorView(),"清除下载记录");assertNotNull(clear);assertTrue(clear.performClick());
        AlertDialog dialog=ShadowAlertDialog.getLatestAlertDialog();assertNotNull(dialog);assertTrue(dialog.isShowing());return dialog;
    }
    void choose(AlertDialog dialog,String label){Button b=button(dialog.getWindow().getDecorView(),label);assertNotNull(b);b.performClick();shadowOf(Looper.getMainLooper()).idle();assertFalse(dialog.isShowing());}
    void render()throws Exception {call(activity,"render",new Class<?>[0]);}

    void drainCleanup()throws Exception {
        Intent intent=shadowOf(activity.getApplication()).getNextStartedService();
        assertNotNull("Deletion must start the cleanup service",intent);assertEquals(DownloadService.CLEANUP,intent.getAction());
        org.robolectric.android.controller.ServiceController<DownloadService> service=Robolectric.buildService(DownloadService.class).create();
        try{
            service.get().onStartCommand(intent,0,1);
            long end=System.nanoTime()+java.util.concurrent.TimeUnit.SECONDS.toNanos(10);
            while(true){
                shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(250));
                boolean pending=false;for(Store.Task task:store.snapshot())pending|=task.discardRequested&&task.status.equals("cancelling");
                if(!pending)break;
                assertTrue("Cleanup must finish without losing pending batch items",System.nanoTime()<end);Thread.sleep(10);
            }
            render();
        }finally{service.destroy();}
    }
    File cache(Store.Task task)throws Exception {
        File file=new File(activity.getFilesDir(),"work/"+task.key+"/images/1.jpg");file.getParentFile().mkdirs();Files.write(file.toPath(),new byte[]{1,2});return file;
    }
    File output(Store.Task task,boolean folder)throws Exception {
        File root=new File(AlbumStorage.root(activity),"fixture-"+task.key+(folder?"":".partial"));
        File file=folder?new File(root,"001/1.jpg"):root;file.getParentFile().mkdirs();Files.write(file.toPath(),new byte[]{3,4});
        task.cleanupUri=ExportProvider.uri(activity,root).toString();return root;
    }

    @Test public void pausedAndFailedRecordsClearAndStayGoneAfterReload()throws Exception {
        task("paused");task("failed");task("done");task("cancelled");for(int i=0;i<5;i++)cache(task("paused"));store.save();render();
        choose(confirm(),"确认");assertEquals(8,store.tasks.size());drainCleanup();assertTrue("Stopped records must clear",store.tasks.isEmpty());
        assertTrue(((Map<?,?>)field(MainActivity.class,"rows").get(activity)).isEmpty());
        assertTrue(ShadowToast.getTextOfLatestToast().contains("8"));
        field(Store.class,"instance").set(null,null);assertTrue(Store.get(activity).tasks.isEmpty());
    }
    @Test public void cancelLeavesRecordsAndRemovesBlur()throws Exception {
        task("paused");store.save();render();byte[] before=Files.readAllBytes(activity.getFileStreamPath("queue.json").toPath());
        ViewGroup decor=(ViewGroup)activity.getWindow().getDecorView();int children=decor.getChildCount();
        choose(confirm(),"取消");assertEquals(1,store.tasks.size());assertArrayEquals(before,Files.readAllBytes(activity.getFileStreamPath("queue.json").toPath()));assertEquals(children,decor.getChildCount());
    }
    @Test public void activePendingAndCleanupRecordsArePreserved()throws Exception {
        Store.Task paused=task("paused"),draining=task("paused");store.activeKeys.add(draining.key);
        task("running");task("resetting");task("queued");task("cancelling");
        store.save();List<Store.Task> keep=new ArrayList<>(store.tasks);keep.remove(paused);
        choose(confirm(),"确认");drainCleanup();assertEquals(keep,store.tasks);assertEquals("queued",keep.get(3).status);assertTrue(ShadowToast.getTextOfLatestToast().contains("已保留"));
    }
    @Test public void completedFilesCacheAndLibraryRemainAvailable()throws Exception {
        Store.Task paused=task("paused");Store.Task done=task("done");done.settings.format="zip";done.resultUri="content://"+activity.getPackageName()+".exports/clear-output-fixture.zip";
        File cached=cache(paused),successfulCache=cache(done),output=new File(activity.getExternalFilesDir(null),"exports/clear-output-fixture.zip");cached.getParentFile().mkdirs();output.getParentFile().mkdirs();Files.write(cached.toPath(),new byte[]{1,2});Files.write(output.toPath(),new byte[]{3,4});store.save();
        choose(confirm(),"确认");drainCleanup();assertTrue(store.tasks.isEmpty());assertFalse(cached.exists());assertArrayEquals(new byte[]{1,2},Files.readAllBytes(successfulCache.toPath()));assertArrayEquals(new byte[]{3,4},Files.readAllBytes(output.toPath()));assertEquals(done.resultUri,LibraryStore.get(activity).list("",false).get(0).uri);
    }
    @Test public void saveFailureKeepsRowsAndPersistedRecords()throws Exception {
        Store.Task paused=task("paused");store.save();render();byte[] before=Files.readAllBytes(activity.getFileStreamPath("queue.json").toPath());AtomicFile original=(AtomicFile)field(Store.class,"file").get(store);
        field(Store.class,"file").set(store,new AtomicFile(activity.getFileStreamPath("queue.json")){@Override public FileOutputStream startWrite()throws IOException{throw new IOException("fixture disk full");}});
        try{choose(confirm(),"确认");assertEquals(Collections.singletonList(paused),store.tasks);assertFalse(paused.discardRequested);assertEquals("paused",paused.status);assertNull(shadowOf(activity.getApplication()).getNextStartedService());assertArrayEquals(before,Files.readAllBytes(activity.getFileStreamPath("queue.json").toPath()));assertTrue(ShadowAlertDialog.getLatestAlertDialog().isShowing());}
        finally{field(Store.class,"file").set(store,original);}
    }
    @Test public void emptyOrProtectedQueueHasVisibleFeedback()throws Exception {
        choose(confirm(),"确认");assertNotNull("Clearing an empty queue must explain the result",ShadowToast.getTextOfLatestToast());assertTrue(ShadowToast.getTextOfLatestToast().contains("暂无"));
        task("running");choose(confirm(),"确认");assertEquals(1,store.tasks.size());assertTrue(ShadowToast.getTextOfLatestToast().contains("暂停"));
    }
    @Test public void busyLibraryKeepsRecords()throws Exception {
        Store.Task paused=task("paused");store.save();store.libraryBusy=true;
        choose(confirm(),"确认");assertEquals(Collections.singletonList(paused),store.tasks);assertTrue(ShadowAlertDialog.getLatestAlertDialog().isShowing());store.libraryBusy=false;
    }
    @Test public void clearStillWorksAfterPageRoundTrip()throws Exception {
        task("paused");store.save();
        for(boolean library:new boolean[]{true,false}){call(activity,"setFrontPage",new Class<?>[]{boolean.class,boolean.class},library,true);shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(1200));assertNull(field(MainActivity.class,"pageExchange").get(activity));}
        choose(confirm(),"确认");drainCleanup();assertTrue(store.tasks.isEmpty());
    }

    View menu()throws Exception {return (View)field(MainActivity.class,"taskSheet").get(activity);}
    void select(Store.Task task)throws Exception {
        render();shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(100));
        Object row=((Map<?,?>)field(MainActivity.class,"rows").get(activity)).get(task.key);
        assertTrue(((View)field(row.getClass(),"card").get(row)).performLongClick());
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(350));
    }
    void assertMenuVisible()throws Exception {
        View sheet=menu(),pages=(View)field(MainActivity.class,"pages").get(activity);Rect visible=new Rect(),viewport=new Rect();
        assertEquals(View.VISIBLE,sheet.getVisibility());assertTrue("Menu must intersect the viewport",sheet.getGlobalVisibleRect(visible));assertTrue(pages.getGlobalVisibleRect(viewport));
        assertTrue(sheet.getHeight()>0);assertEquals("Menu must be completely visible",sheet.getHeight(),visible.height());assertEquals("Menu must align with the visible page bottom",viewport.bottom,visible.bottom);
    }
    @Test public void taskMenuLongPressShowsCountAndSelection()throws Exception {
        Store.Task first=task("paused");Store.Task second=task("paused");select(first);assertMenuVisible();
        assertEquals("已选中1项",((TextView)field(MainActivity.class,"selectedCount").get(activity)).getText().toString());
        select(second);assertMenuVisible();assertEquals("已选中2项",((TextView)field(MainActivity.class,"selectedCount").get(activity)).getText().toString());
        Object row=((Map<?,?>)field(MainActivity.class,"rows").get(activity)).get(first.key);assertEquals(View.VISIBLE,((View)field(row.getClass(),"chosen").get(row)).getVisibility());
    }
    @Test public void taskMenuReturnReopenAndCancelKeepRecords()throws Exception {
        Store.Task first=task("paused");store.save();select(first);button(menu(),"返回").performClick();shadowOf(Looper.getMainLooper()).idle();
        assertEquals(View.GONE,menu().getVisibility());assertFalse(field(MainActivity.class,"selecting").getBoolean(activity));assertEquals(1,store.tasks.size());
        select(first);assertMenuVisible();button(menu(),"删除任务").performClick();choose(ShadowAlertDialog.getLatestAlertDialog(),"取消");assertEquals(1,store.tasks.size());assertMenuVisible();
    }
    @Test public void taskMenuReanchorsWhenViewportShrinks()throws Exception {
        select(task("paused"));assertMenuVisible();View pages=(View)field(MainActivity.class,"pages").get(activity);
        LinearLayout.LayoutParams params=(LinearLayout.LayoutParams)pages.getLayoutParams();params.height=Ui.dp(activity,360);params.weight=0;pages.setLayoutParams(params);
        shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(350));assertEquals(Ui.dp(activity,360),pages.getHeight());assertMenuVisible();
    }
    @Test public void taskMenuSurvivesPageRoundTrip()throws Exception {
        select(task("paused"));assertMenuVisible();
        for(boolean library:new boolean[]{true,false}){call(activity,"setFrontPage",new Class<?>[]{boolean.class,boolean.class},library,true);shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(1200));}
        assertMenuVisible();button(menu(),"返回").performClick();assertEquals(View.GONE,menu().getVisibility());
    }
    @Test public void taskMenuDeleteRemovesOnlySelectedRecord()throws Exception {
        Store.Task first=task("paused"),second=task("paused");store.save();select(first);assertMenuVisible();button(menu(),"删除任务").performClick();choose(ShadowAlertDialog.getLatestAlertDialog(),"确认");
        drainCleanup();assertEquals(Collections.singletonList(second),store.tasks);assertEquals(View.GONE,menu().getVisibility());
    }
    @Test public void incompleteOutputsAndCachesDeleteWhileOtherTasksRemain()throws Exception {
        Store.Task paused=task("paused"),failed=task("failed"),keep=task("paused");
        File partial=output(paused,false),folder=output(failed,true),firstCache=cache(paused),secondCache=cache(failed),other=cache(keep);store.save();
        select(paused);select(failed);button(menu(),"删除任务").performClick();choose(ShadowAlertDialog.getLatestAlertDialog(),"确认");
        assertTrue(partial.exists());assertTrue(folder.exists());assertEquals(3,store.tasks.size());
        drainCleanup();assertEquals(Collections.singletonList(keep),store.tasks);assertFalse(partial.exists());assertFalse(folder.exists());assertFalse(firstCache.exists());assertFalse(secondCache.exists());assertTrue(other.exists());
    }
    @Test public void failedCleanupKeepsRecordAndCanRetryFromClearButton()throws Exception {
        Store.Task task=task("paused");File cached=cache(task);task.cleanupUri="content://"+activity.getPackageName()+".exports/../forbidden";store.save();
        choose(confirm(),"确认");drainCleanup();assertEquals(Collections.singletonList(task),store.tasks);assertEquals("cancel_failed",task.status);assertTrue(task.discardRequested);assertTrue(cached.exists());
        assertEquals("cancel_failed",new Store.Task(task.json()).status);
        task.cleanupUri="";store.save();choose(confirm(),"确认");drainCleanup();assertTrue(store.tasks.isEmpty());assertFalse(cached.exists());
    }
    @Test public void pendingRemovalSurvivesReloadAndResumesOnOpeningActivity()throws Exception {
        Store.Task task=task("paused");File cached=cache(task);store.save();
        TaskRecordRemoval.prepare(store,null);assertTrue(cached.exists());
        controller.pause().stop().destroy();controller=null;field(Store.class,"instance").set(null,null);
        store=Store.get(activity);assertTrue(store.tasks.get(0).discardRequested);assertEquals("cancelling",store.tasks.get(0).status);
        controller=Robolectric.buildActivity(MainActivity.class);activity=controller.get();activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup().visible();
        ((Handler)field(MainActivity.class,"handler").get(activity)).removeCallbacksAndMessages(null);
        drainCleanup();assertTrue(store.tasks.isEmpty());assertFalse(cached.exists());
    }
    @Test public void cancellingConfirmationLeavesTaskFilesUntouched()throws Exception {
        Store.Task task=task("paused");File cached=cache(task),partial=output(task,false);store.save();
        select(task);button(menu(),"删除任务").performClick();choose(ShadowAlertDialog.getLatestAlertDialog(),"取消");
        assertFalse(task.discardRequested);assertTrue(cached.exists());assertTrue(partial.exists());assertNull(shadowOf(activity.getApplication()).getNextStartedService());
    }
    @Test public void selectingActiveTaskRejectsEntireDeletion()throws Exception {
        Store.Task done=task("done"),active=task("paused");store.activeKeys.add(active.key);File cached=cache(active);store.save();
        select(done);select(active);button(menu(),"删除任务").performClick();choose(ShadowAlertDialog.getLatestAlertDialog(),"确认");
        assertEquals(2,store.tasks.size());assertTrue(cached.exists());assertFalse(active.discardRequested);assertTrue(ShadowAlertDialog.getLatestAlertDialog().isShowing());
    }
    @Test public void completedSelectedRecordKeepsFiles()throws Exception {
        Store.Task done=task("done");File result=output(done,true),cached=cache(done);done.resultUri=done.cleanupUri;done.cleanupUri="";done.settings.format="images";store.save();
        select(done);button(menu(),"删除任务").performClick();choose(ShadowAlertDialog.getLatestAlertDialog(),"确认");
        assertTrue(store.tasks.isEmpty());assertTrue(result.exists());assertTrue(cached.exists());assertEquals(done.resultUri,LibraryStore.get(activity).list("",false).get(0).uri);assertNull(shadowOf(activity.getApplication()).getNextStartedService());
    }
    @Test public void cleanupRecordSaveFailureRetainsRetryTracking()throws Exception {
        Store.Task task=task("paused");File cached=cache(task);store.save();choose(confirm(),"确认");
        AtomicFile original=(AtomicFile)field(Store.class,"file").get(store);
        field(Store.class,"file").set(store,new AtomicFile(activity.getFileStreamPath("queue.json")){@Override public FileOutputStream startWrite()throws IOException{throw new IOException("fixture disk full");}});
        try{drainCleanup();assertEquals(Collections.singletonList(task),store.tasks);assertEquals("cancel_failed",task.status);assertFalse(cached.exists());}
        finally{field(Store.class,"file").set(store,original);}
        choose(confirm(),"确认");drainCleanup();assertTrue(store.tasks.isEmpty());
    }
    @Test public void selectedSafCleanupRetriesWithoutDeletingCompletedSibling()throws Exception {
        File root=new File(activity.getFilesDir(),"saf-"+UUID.randomUUID());assertTrue(root.mkdirs());
        File partial=new File(root,"incomplete.partial"),complete=new File(root,"complete.zip");Files.write(partial.toPath(),new byte[]{3});Files.write(complete.toPath(),new byte[]{4});
        ChapterDeletionRuntimeTest.TreeProvider provider=new ChapterDeletionRuntimeTest.TreeProvider(root);
        android.content.pm.ProviderInfo info=new android.content.pm.ProviderInfo();info.authority="chapters.test";info.exported=true;info.grantUriPermissions=true;info.readPermission=info.writePermission="android.permission.MANAGE_DOCUMENTS";provider.attachInfo(activity,info);
        ChapterDeletionRuntimeTest.Bridge bridge=new ChapterDeletionRuntimeTest.Bridge(provider);bridge.attachInfo(activity,info);org.robolectric.shadows.ShadowContentResolver.registerProviderInternal(info.authority,bridge);
        Store.Task paused=task("paused"),done=task("done");paused.cleanupUri="content://chapters.test/tree/root/document/root%2Fincomplete.partial";done.resultUri="content://chapters.test/tree/root/document/root%2Fcomplete.zip";done.settings.format="zip";
        File cached=cache(paused);provider.failDelete="root/incomplete.partial";store.save();choose(confirm(),"确认");drainCleanup();
        assertEquals(Collections.singletonList(paused),store.tasks);assertEquals("cancel_failed",paused.status);assertTrue(partial.exists());assertTrue(cached.exists());assertArrayEquals(new byte[]{4},Files.readAllBytes(complete.toPath()));
        provider.failDelete="";select(paused);button(menu(),"删除任务").performClick();choose(ShadowAlertDialog.getLatestAlertDialog(),"确认");drainCleanup();
        assertTrue(store.tasks.isEmpty());assertFalse(partial.exists());assertFalse(cached.exists());assertTrue(complete.exists());assertEquals(done.resultUri,LibraryStore.get(activity).list("",false).get(0).uri);assertEquals(2,provider.deletes);
    }

}
