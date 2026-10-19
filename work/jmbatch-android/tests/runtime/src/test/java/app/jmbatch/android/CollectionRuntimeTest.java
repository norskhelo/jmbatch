package app.jmbatch.android;

import android.content.Context;
import android.graphics.Bitmap;
import android.util.AtomicFile;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.*;
import java.io.*;
import java.nio.file.Files;
import java.lang.reflect.Field;
import java.util.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},shadows={CollectionRuntimeTest.WindowsAtomicRename.class})
@LooperMode(LooperMode.Mode.PAUSED)
public class CollectionRuntimeTest {
    /** API 30+ AtomicFile uses File.renameTo over an existing base, which works
     * on Android/Linux but fails on Windows. Bridge only this private primitive;
     * the actual framework still writes, syncs, closes and recovers the files. */
    @Implements(AtomicFile.class)
    public static class WindowsAtomicRename {
        @Implementation(minSdk=30) protected static void rename(File from,File to)throws IOException {
            Files.move(from.toPath(),to.toPath(),java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        }
    }
    Context context;LibraryStore library;File file;List<LibraryStore.Entry> comics;
    private void reset()throws Exception {Field singleton=LibraryStore.class.getDeclaredField("instance");singleton.setAccessible(true);singleton.set(null,null);}
    @Before public void setup()throws Exception {
        context=RuntimeEnvironment.getApplication();file=new File(context.getFilesDir(),"library.json");new AtomicFile(file).delete();reset();
        library=LibraryStore.get(context);comics=new ArrayList<>();
        for(int i=0;i<6;i++)comics.add(new LibraryStore.Entry(""+i,"Comic "+i,"content://app.jmbatch.android.exports/book"+i,"","test","zip",i==0));
        library.importFound(comics);
    }
    @Test public void legacyMigrationMoveRenameDeletePreservesData()throws Exception {
        JSONObject old=new JSONObject(new String(Files.readAllBytes(file.toPath()),"UTF-8"));old.remove("collections");
        for(int i=0;i<old.getJSONArray("entries").length();i++)old.getJSONArray("entries").getJSONObject(i).remove("collection");
        Files.write(file.toPath(),old.toString().getBytes("UTF-8"));reset();library=LibraryStore.get(context);
        assertEquals(6,library.browse("",false,"").size());String folder=library.createCollection("待读");
        library.moveToCollection(comics.subList(0,2),folder);library.renameCollection(folder,"旅行");
        library.importFound(comics);library.setFavorites(comics.subList(0,1),true);
        JSONObject saved=new JSONObject(new String(Files.readAllBytes(file.toPath()),"UTF-8"));
        assertEquals("Saved JSON must contain renamed collection","旅行",saved.getJSONObject("collections").getString(folder));
        reset();library=LibraryStore.get(context);assertEquals(6,library.list("",false).size());assertEquals("旅行",library.collectionName(folder));assertEquals(2,library.browse("",false,folder).size());
        assertEquals(folder,library.browse("Comic 0",false,"").get(0).uri);assertEquals(folder,library.browse("",true,"").get(0).uri);
        assertEquals(1,library.browse("旅行",false,"").size());assertEquals(0,library.browse("unknown",false,"").size());
        library.deleteCollection(folder);assertEquals(6,library.browse("",false,"").size());assertEquals(1,library.list("",true).size());
        assertEquals(comics.get(0).uri,library.list("Comic 0",false).get(0).uri);
    }
    @Test public void invalidNamesAndTargetsDoNotChangeDisk()throws Exception {
        String folder=library.createCollection("Read");byte[] before=Files.readAllBytes(file.toPath());
        for(String name:new String[]{"", " ","漫画库","read","a\nb",String.join("",Collections.nCopies(41,"x"))}){
            try{library.createCollection(name);fail(name);}catch(IOException expected){}
            assertArrayEquals(before,Files.readAllBytes(file.toPath()));
        }
        try{library.moveToCollection(comics,"missing");fail();}catch(IOException expected){}
        try{library.moveToCollection(Arrays.asList(comics.get(0),new LibraryStore.Entry("x","x","missing","","","zip",false)),folder);fail();}catch(IOException expected){}
        assertArrayEquals(before,Files.readAllBytes(file.toPath()));
    }
    @Test public void recordSaveFailureRollsBackFoldersAndMembership()throws Exception {
        String folder=library.createCollection("待读");library.moveToCollection(comics.subList(0,2),folder);
        byte[] before=Files.readAllBytes(file.toPath());Field field=LibraryStore.class.getDeclaredField("file");field.setAccessible(true);
        field.set(library,new AtomicFile(file){@Override public FileOutputStream startWrite()throws IOException{throw new IOException("disk full");}});
        for(int operation=0;operation<4;operation++){
            try{if(operation==0)library.createCollection("new");else if(operation==1)library.renameCollection(folder,"other");else if(operation==2)library.deleteCollection(folder);else library.moveToCollection(comics,"");fail();}catch(IOException expected){}
            assertEquals("待读",library.collectionName(folder));assertEquals(2,library.browse("",false,folder).size());assertEquals(1,library.collections().size());assertArrayEquals(before,Files.readAllBytes(file.toPath()));
        }
    }
    @Test public void taskAndChapterReplacementPreserveCollection()throws Exception {
        String folder=library.createCollection("待读");library.moveToCollection(comics.subList(0,1),folder);
        Store.Task task=new Store.Task("0",new Store.Settings());task.status="done";task.resultUri=comics.get(0).uri;task.title="new title";
        library.sync(Collections.singletonList(task));library.favorite(comics.get(0));
        LibraryStore.Entry next=new LibraryStore.Entry("0","new title","content://app.jmbatch.android.exports/new","","test","zip",false);
        Store store=Store.get(context);library.replaceChapters(store,comics.get(0),next);
        assertEquals(next.uri,library.browse("",false,folder).get(0).uri);
        assertEquals(folder,library.browse("",false,folder).get(0).collection);
    }
    @Test public void previewsBoundedAndMissingCoversHandled()throws Exception {
        String folder=library.createCollection("待读");library.moveToCollection(comics,folder);
        List<LibraryStore.Entry> previews=library.collectionPreviews().get(folder);assertEquals(4,previews.size());
        Bitmap bitmap=CollectionCover.load(context,previews);assertNotNull(bitmap);assertEquals(144,bitmap.getWidth());assertEquals(192,bitmap.getHeight());
        library.moveToCollection(comics,"");assertTrue(library.collectionPreviews().get(folder).isEmpty());assertNotNull(CollectionCover.load(context,Collections.emptyList()));
    }
    @Test public void corruptFolderReferenceProtectsOriginalFile()throws Exception {
        JSONObject data=new JSONObject(new String(Files.readAllBytes(file.toPath()),"UTF-8"));data.getJSONArray("entries").getJSONObject(0).put("collection","missing");
        byte[] bad=data.toString().getBytes("UTF-8");Files.write(file.toPath(),bad);reset();library=LibraryStore.get(context);
        try{library.createCollection("new");fail();}catch(IOException expected){}
        assertArrayEquals(bad,Files.readAllBytes(file.toPath()));
    }
    @Test public void frameworkAtomicFileActuallyReplacesExistingFile()throws Exception {
        File probe=new File(context.getFilesDir(),"atomic-probe.json");Files.write(probe.toPath(),"before".getBytes("UTF-8"));
        AtomicFile atomic=new AtomicFile(probe);FileOutputStream stream=atomic.startWrite();stream.write("after".getBytes("UTF-8"));atomic.finishWrite(stream);
        assertEquals("after",new String(Files.readAllBytes(probe.toPath()),"UTF-8"));
    }
}
