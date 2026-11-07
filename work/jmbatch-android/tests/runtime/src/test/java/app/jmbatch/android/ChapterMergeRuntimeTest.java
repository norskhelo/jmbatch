package app.jmbatch.android;

import android.content.*;
import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import android.net.Uri;
import android.util.AtomicFile;
import java.io.*;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.util.*;
import java.util.zip.*;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(manifest=Config.NONE,sdk={29,35},shadows={CollectionRuntimeTest.WindowsAtomicRename.class})
public class ChapterMergeRuntimeTest {
    Context c;Store store;LibraryStore library;File root,jpeg;
    @Before public void setup()throws Exception {
        c=RuntimeEnvironment.getApplication();resetSingletons();root=AlbumStorage.root(c);root.mkdirs();
        for(String name:new String[]{"chapter-merge.json","library.json","queue.json","chapter-updates.json"})
            new AtomicFile(new File(c.getFilesDir(),name)).delete();
        store=Store.get(c);library=LibraryStore.get(c);
        jpeg=File.createTempFile("page-",".jpg",c.getCacheDir());
        assertTrue(ImageIO.write(new BufferedImage(6,8,BufferedImage.TYPE_INT_RGB),"jpg",jpeg));
    }
    void resetSingletons()throws Exception {
        for(Class<?> t:new Class<?>[]{Store.class,LibraryStore.class}){Field f=t.getDeclaredField("instance");f.setAccessible(true);f.set(null,null);}
    }
    LibraryStore.Entry book(String format,String kind,int groups)throws Exception {
        String name="JM1452133-"+kind+"-"+UUID.randomUUID().toString().substring(0,8);
        File source=new File(root,name+(format.equals("images")?"":"."+format));
        byte[] bytes=Files.readAllBytes(jpeg.toPath());List<Core.Page> pdf=new ArrayList<>();
        if(format.equals("zip")){
            try(ZipOutputStream out=new ZipOutputStream(new FileOutputStream(source))){
                for(int i=1;i<=groups;i++){out.putNextEntry(new ZipEntry(AlbumRules.imageName(i,1,groups)));out.write(bytes);out.closeEntry();}
            }
        }else if(format.equals("pdf")){
            for(int i=0;i<groups;i++)pdf.add(new Core.Page(jpeg,6,8));
            Core.writePdf(source,pdf,(a,b)->{});
        }else{
            for(int i=1;i<=groups;i++){File p=new File(source,AlbumRules.imageName(i,1,groups));p.getParentFile().mkdirs();Files.write(p.toPath(),bytes);}
        }
        LibraryStore.Entry book=new LibraryStore.Entry("1452133",kind,ExportProvider.uri(c,source).toString(),"","local",format,kind.equals("base"),"",groups);
        library.importFound(Collections.singletonList(book));return book;
    }
    Store.Task taskFor(LibraryStore.Entry base,int count)throws Exception {
        List<ChapterRules.Chapter> chapters=new ArrayList<>();
        for(int i=1;i<=count;i++)chapters.add(new ChapterRules.Chapter(""+(5000+i),i,"c"+i));
        return store.addChapterUpdate(base,chapters,chapters,store.settings);
    }
    List<AlbumStorage.Image> pages(int count){
        List<AlbumStorage.Image> images=new ArrayList<>();
        for(int i=1;i<=count;i++)images.add(new AlbumStorage.Image(i,1,Uri.fromFile(jpeg),jpeg.length(),"page.jpg"));return images;
    }
    @Test public void oneHundredPlus145SameFolderAndRepeatIsIdempotent()throws Exception {
        LibraryStore.Entry base=book("images","base",100);
        Store.Task task=taskFor(base,145);
        assertEquals(base.uri,ChapterMerge.download(store,task,pages(145),()->{}));
        assertEquals(base.uri,ChapterMerge.download(store,task,pages(145),()->{}));
        library.sync(store.snapshot());assertEquals(1,library.list("",false).size());
        assertEquals(245,library.byUri(base.uri).chapterCount);
        AlbumStorage.Album merged=AlbumStorage.load(c,Uri.parse(base.uri));assertEquals(245,merged.images.size());
        assertEquals(245,merged.images.get(244).chapter);
        assertArrayEquals(Files.readAllBytes(jpeg.toPath()),Files.readAllBytes(AlbumStorage.local(c,merged.images.get(244).uri).toPath()));
        assertEquals("done",task.status);
        try(ReaderSource reader=new ReaderSource(c,library.byUri(base.uri),()->{})){
            assertEquals(100,reader.chapters[99]);assertEquals(101,reader.chapters[100]);
        }
        List<LibraryStore.Entry> exported=AlbumExporter.export(c,Uri.parse(base.uri),"","local","zip",false,false,false,()->{},message->{});
        assertEquals(1,exported.size());
        try(ZipFile zip=new ZipFile(AlbumStorage.local(c,Uri.parse(exported.get(0).uri)))){assertEquals(245,ArchivePages.read(zip).size());}

    }
    @Test public void pdfKeepsEveryOriginalJpegAndFileName()throws Exception {
        LibraryStore.Entry base=book("pdf","base",2);Store.Task update=taskFor(base,1);
        ChapterMerge.download(store,update,pages(1),()->{});
        File expected=new File(c.getCacheDir(),"expected.pdf");Core.Page page=new Core.Page(jpeg,6,8);
        Core.writePdf(expected,Arrays.asList(page,page,page),(a,b)->{});
        assertArrayEquals(Files.readAllBytes(expected.toPath()),Files.readAllBytes(AlbumStorage.local(c,Uri.parse(base.uri)).toPath()));
        assertTrue(store.cleanupNotice,store.cleanupNotice.isEmpty());assertEquals(3,library.byUri(base.uri).chapterCount);
    }
    @Test public void journalFinishesAfterQueueWriteFailsWithoutAddingPagesTwice()throws Exception {
        LibraryStore.Entry base=book("images","base",2);Store.Task update=taskFor(base,1);
        Field f=Store.class.getDeclaredField("file");f.setAccessible(true);
        f.set(store,new AtomicFile(new File(c.getFilesDir(),"queue.json")){
            @Override public FileOutputStream startWrite()throws IOException {throw new IOException("simulated full disk");}
        });
        try{ChapterMerge.download(store,update,pages(1),()->{});fail();}catch(IOException expected){assertEquals(true,expected.getMessage().contains("full disk"));}
        resetSingletons();store=Store.get(c);library=LibraryStore.get(c);
        assertEquals("done",store.tasks.get(0).status);assertEquals(1,library.list("",false).size());assertEquals(3,library.byUri(base.uri).chapterCount);
        assertEquals(3,AlbumStorage.load(c,Uri.parse(base.uri)).images.size());assertFalse(new File(c.getFilesDir(),"chapter-merge.json").exists());
    }
    @Test public void safOriginalNameAndFolderSurviveStorageFailureThenRetry()throws Exception {
        ChapterDeletionRuntimeTest fixture=new ChapterDeletionRuntimeTest();
        fixture.setup();store=fixture.store;library=fixture.library;
        LibraryStore.Entry base=fixture.fixture(false,true);Store.Task task=taskFor(base,1);
        fixture.provider.failRename=true;
        try{ChapterMerge.download(store,task,pages(1),()->{});fail();}catch(Exception expected){}
        assertEquals(6,AlbumStorage.load(c,Uri.parse(base.uri)).images.size());
        fixture.provider.failRename=false;
        assertEquals(base.uri,ChapterMerge.download(store,task,pages(1),()->{}));
        assertEquals(7,AlbumStorage.load(c,Uri.parse(base.uri)).images.size());
        assertEquals(1,library.list("",false).size());
    }
    @Test public void abandonedStagingIsCleanedWithoutTouchingOtherCopies()throws Exception {
        LibraryStore.Entry base=book("images","base",1);
        File temp=new File(c.getCacheDir(),"chapter-merge/prepare-test");assertTrue(temp.mkdirs());
        String name=".jmbatch-merge-"+UUID.randomUUID()+".partial";
        File staged=new File(root,name),other=new File(root,name+"-other");assertTrue(staged.mkdir());assertTrue(other.mkdir());
        Downloader.writeTextAtomic(new File(temp,"output.json"),new JSONObject().put("tree","").put("name",name).toString());
        resetSingletons();store=Store.get(c);
        assertFalse(staged.exists());assertFalse(temp.exists());assertTrue(other.exists());assertTrue(AlbumStorage.local(c,Uri.parse(base.uri)).exists());
    }
    @Test public void cancellationAndExtraFilesPreserveOriginal()throws Exception {
        LibraryStore.Entry base=book("images","base",2);Store.Task task=taskFor(base,1);
        try{ChapterMerge.download(store,task,pages(1),()->{throw new IOException("stopped");});fail();}catch(IOException expected){}
        File foreign=new File(AlbumStorage.local(c,Uri.parse(base.uri)),"notes.txt");Files.write(foreign.toPath(),new byte[]{1});
        try{ChapterMerge.download(store,task,pages(1),()->{});fail();}catch(IOException expected){assertTrue(expected.getMessage().contains("额外"));}
        assertTrue(foreign.exists());assertEquals(2,library.byUri(base.uri).chapterCount);
    }
}
