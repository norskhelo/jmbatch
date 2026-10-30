package app.jmbatch.android;

import android.app.*;
import android.os.Looper;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.lang.reflect.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.*;
import org.robolectric.android.controller.ActivityController;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},shadows={CollectionRuntimeTest.WindowsAtomicRename.class})
@LooperMode(LooperMode.Mode.PAUSED)
public class FileOperationsRuntimeTest {
    ChapterDeletionRuntimeTest fixture;
    Store store; LibraryStore library;
    @Before public void setup()throws Exception {
        fixture=new ChapterDeletionRuntimeTest();fixture.setup();store=fixture.store;library=fixture.library;
    }
    Store.Task task(String id,String status) {
        Store.Task task=new Store.Task(id,new Store.Settings());task.status=status;store.tasks.add(task);store.running=true;return task;
    }
    @Test public void deleteAndForgetWhileOtherTaskRuns()throws Exception {
        LibraryStore.Entry entry=fixture.fixture(true,false);Store.Task other=task("999","running");store.activeKeys.add(other.key);
        library.remove(store,entry,false);
        assertTrue(AlbumStorage.local(fixture.context,android.net.Uri.parse(entry.uri)).exists());
        library.sync(store.snapshot());assertTrue(library.list("",false).isEmpty());assertTrue(store.running);assertEquals("running",other.status);
        library.importFound(Collections.singletonList(entry));library.remove(store,entry,true);
        assertFalse(AlbumStorage.local(fixture.context,android.net.Uri.parse(entry.uri)).exists());assertFalse(store.libraryBusy);
    }
    @Test public void chapterDeletionAndConcurrentCompletionPreserveBothRecords()throws Exception {
        LibraryStore.Entry entry=fixture.fixture(true,false);Store.Task other=task("999","running");
        ChapterDeletion.Plan plan=ChapterDeletion.inspect(fixture.context,entry,()->false);
        final boolean[] completed={false};
        ChapterDeletion.delete(fixture.context,store,entry,plan,Collections.singleton(2),()->false,message->{
            if(completed[0])return;completed[0]=true;
            CompletableFuture<Void> finished=CompletableFuture.runAsync(()->{
                synchronized(store){try{other.status="done";other.resultUri="content://fixture/completed.zip";library.sync(store.snapshot());store.save();}catch(Exception error){throw new RuntimeException(error);}}
            });
            try{finished.get(5,TimeUnit.SECONDS);}catch(Exception error){throw new RuntimeException(error);}
        });
        assertEquals(2,library.list("",false).size());assertEquals("done",other.status);assertTrue(store.running);assertFalse(store.libraryBusy);
        assertNotEquals(entry.uri,store.tasks.get(0).resultUri);
        library.sync(store.snapshot());assertEquals(2,library.list("",false).size());
    }
    @Test public void reservationSkipsOnlyMatchingTaskAndReleasesOnFinish()throws Exception {
        LibraryStore.Entry entry=fixture.fixture(true,false);Store.Task target=task("123","paused"),other=task("999","queued");
        store.beginFileOperation(Collections.singletonList(entry));store.resume();
        assertSame(other,store.next());assertTrue(store.fileBlocked(target));assertFalse(store.fileBlocked(other));assertFalse(store.globalFileOperation());
        other.status="done";assertNull(store.next());assertTrue(store.hasQueuedTasks());
        store.endFileOperation();assertSame(target,store.next());assertFalse(store.fileBlocked(target));
    }
    @Test public void allBusyStatesAndActualResultAreProtected()throws Exception {
        LibraryStore.Entry entry=fixture.fixture(true,false);Store.Task target=task("123","queued");
        for(String status:Arrays.asList("queued","running","resetting","cancelling","cancel_failed")){
            target.status=status;
            try{store.beginFileOperation(Collections.singletonList(entry));fail(status);}catch(IOException expected){assertTrue(expected.getMessage().contains("所选漫画"));}
            assertFalse(store.libraryBusy);
        }
        target.status="paused";store.activeKeys.add(target.key);
        try{library.remove(store,entry,true);fail();}catch(IOException expected){}store.activeKeys.clear();
        target.settings.outputUri="content://fixture/other";target.status="running";
        store.beginFileOperation(Collections.singletonList(entry));store.endFileOperation();
        target.resultUri=entry.uri;
        try{store.beginFileOperation(Collections.singletonList(entry));fail();}catch(IOException expected){}
        assertTrue(AlbumStorage.local(fixture.context,android.net.Uri.parse(entry.uri)).exists());
    }
    @Test public void failedBatchReleasesGuardAndKeepsOtherDownloads()throws Exception {
        LibraryStore.Entry entry=fixture.fixture(true,false);Store.Task other=task("999","running");
        assertTrue(AlbumStorage.local(fixture.context,android.net.Uri.parse(entry.uri)).delete());
        BatchOperations.Result result=library.removeMany(store,Collections.singletonList(entry),true,()->false,(a,b)->{});
        assertTrue(result.summary().contains("失败 1"));assertFalse(store.libraryBusy);assertEquals("running",other.status);
        assertEquals(1,library.list("",false).size());
    }
    @Test public void exportButtonWorksDuringDownloadAndReleasesReservation()throws Exception {
        LibraryStore.Entry entry=fixture.fixture(true,false);Store.Task other=task("999","running");
        ActivityController<Activity> controller=Robolectric.buildActivity(Activity.class).setup();Activity activity=controller.get();
        try{
            ExportScreen screen=new ExportScreen(activity,store,entry);screen.show();
            Field field=ExportScreen.class.getDeclaredField("dialog");field.setAccessible(true);AlertDialog dialog=(AlertDialog)field.get(screen);
            button(dialog.getWindow().getDecorView(),"zip").performClick();
            button(dialog.getWindow().getDecorView(),"确认").performClick();assertFalse(dialog.isShowing());
            long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(15);
            while(store.libraryBusy&&System.nanoTime()<end){Thread.sleep(10);shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(10));}
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(500));assertFalse(store.libraryBusy);
            assertEquals(2,library.list("",false).size());
            assertEquals("running",other.status);assertTrue(store.running);
            assertTrue(AlbumStorage.local(fixture.context,android.net.Uri.parse(entry.uri)).exists());
        }finally{
            AlertDialog result=org.robolectric.shadows.ShadowAlertDialog.getLatestAlertDialog();if(result!=null)result.dismiss();
            controller.pause().stop().destroy();shadowOf(Looper.getMainLooper()).idle();
        }
    }
    static Button button(View view,String text){
        if(view instanceof Button&&text.contentEquals(((Button)view).getText()))return (Button)view;
        if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++){Button found=button(((ViewGroup)view).getChildAt(i),text);if(found!=null)return found;}
        return null;
    }
}
