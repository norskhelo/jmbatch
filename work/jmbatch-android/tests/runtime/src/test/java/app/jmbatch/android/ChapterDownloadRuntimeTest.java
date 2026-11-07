package app.jmbatch.android;

import android.net.Uri;
import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import javax.imageio.ImageIO;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.*;
import org.robolectric.shadows.ShadowStatFs;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(manifest=Config.NONE,sdk={29,35},instrumentedPackages={"app.jmbatch.android"},
    shadows={CollectionRuntimeTest.WindowsAtomicRename.class,ChapterDownloadRuntimeTest.LocalApi.class})
public class ChapterDownloadRuntimeTest {
    static final int ADDED=145, ORIGINAL=100, FIRST=700000;
    static volatile Store.Task observed;
    static int expectedPages,doublePageChapter;
    static AtomicInteger details,requests,firstReady;
    static volatile long start,firstImageMs;
    static volatile boolean failLate;
    static byte[][] jpegs;
    ChapterMergeRuntimeTest fixture;
    LibraryStore.Entry base;
    Store.Task task;

    @Implements(value=JmApi.class,isInAndroidSdk=false)
    public static class LocalApi {
        @Implementation protected void initialize(){}
        @Implementation protected JSONObject detail(String type,String id)throws Exception {
            if(type.equals("album")){
                JSONArray series=new JSONArray();
                for(int i=0;i<ORIGINAL+ADDED;i++)series.put(new JSONObject().put("id",""+(FIRST+i)).put("sort",i+1));
                return new JSONObject().put("name","base").put("series",series);
            }
            int chapter=Integer.parseInt(id)-FIRST;
            assertTrue("Only selected chapters may be fetched",chapter>=ORIGINAL&&chapter<ORIGINAL+ADDED);
            if(failLate&&chapter==ORIGINAL+8)throw new IOException("synthetic chapter failure");
            Thread.sleep(chapter%4==0?32:8);
            details.incrementAndGet();
            JSONArray pages=new JSONArray().put("image.jpg");
            if(chapter==doublePageChapter)pages.put("second.jpg");
            return new JSONObject().put("images",pages);
        }
        @Implementation protected long scramble(String id){return 10000000;}
        @Implementation protected void image(String chapter,String name,File output,int round)throws Exception {
            if(requests.getAndIncrement()==0){
                firstReady.set(details.get());firstImageMs=java.lang.management.ManagementFactory.getRuntimeMXBean().getUptime()-start;assertEquals("Full page count before first image",expectedPages,observed.total);
            }
            Files.write(output.toPath(),jpegs[(Integer.parseInt(chapter)-FIRST)%jpegs.length]);
        }
    }
    @Before public void setup()throws Exception {
        fixture=new ChapterMergeRuntimeTest();fixture.setup();base=fixture.book("images","base",ORIGINAL);
        List<ChapterRules.Chapter> catalog=new ArrayList<>();
        for(int i=0;i<ORIGINAL+ADDED;i++)catalog.add(new ChapterRules.Chapter(""+(FIRST+i),i+1,"c"+i));
        task=fixture.store.addChapterUpdate(base,catalog,catalog.subList(ORIGINAL,catalog.size()),fixture.store.settings);
        ShadowStatFs.registerStats(fixture.store.cache(task),4000000,3000000,3000000);
        expectedPages=ADDED;doublePageChapter=-1;observed=task;details=new AtomicInteger();requests=new AtomicInteger();firstReady=new AtomicInteger();failLate=false;
        jpegs=new byte[13][];
        for(int i=0;i<jpegs.length;i++){
            ByteArrayOutputStream data=new ByteArrayOutputStream();
            ImageIO.write(new BufferedImage(11+i,8,BufferedImage.TYPE_INT_RGB),"jpg",data);jpegs[i]=data.toByteArray();
        }
        start=java.lang.management.ManagementFactory.getRuntimeMXBean().getUptime();
    }
    void download()throws Exception {
        assertEquals(base.uri,new Downloader(fixture.c,fixture.store,task,new JmApi.Control(),"").run());
    }
    @Test public void all145SelectedDetailsPrecedeFirstImageAndOutputKeepsChapterOrder()throws Exception {
        download();assertTrue(firstImageMs>=0);assertEquals(ADDED,firstReady.get());
        assertEquals(ADDED,requests.get());assertEquals(ADDED,details.get());assertEquals(ADDED,task.done);
        AlbumStorage.Album book=AlbumStorage.load(fixture.c,Uri.parse(base.uri));
        assertEquals(245,book.images.size());
        for(int i=ORIGINAL;i<book.images.size();i++){
            AlbumStorage.Image page=book.images.get(i);
            assertEquals(i+1,page.chapter);
            assertEquals(11+i%jpegs.length,Downloader.dimensions(AlbumStorage.local(fixture.c,page.uri)).outWidth);
        }
        System.out.println("START first_image_ms="+firstImageMs+" ready_chapters="+firstReady.get()+"/"+ADDED+" completed_pages="+task.done);
    }
    @Test public void ordinarySelectionCountsImagesAcrossOnlyTheTwoChosenChapters()throws Exception {
        Store.Task ordinary=new Store.Task(task.id,task.settings);
        Set<String> selected=new HashSet<>(Arrays.asList(""+(FIRST+ORIGINAL),""+(FIRST+ORIGINAL+3)));
        ordinary.selectedChapters=ChapterRules.select(task.chapterOptions,selected);
        expectedPages=3;doublePageChapter=ORIGINAL+3;observed=ordinary;
        ShadowStatFs.registerStats(fixture.store.cache(ordinary),4000000,3000000,3000000);
        String uri=new Downloader(fixture.c,fixture.store,ordinary,new JmApi.Control(),"").run();
        assertFalse(base.uri.equals(uri));assertEquals(2,firstReady.get());assertEquals(2,details.get());
        assertEquals(3,requests.get());assertEquals(3,ordinary.total);assertEquals(3,ordinary.done);
    }
    @Test public void metadataFailureStartsNoImageAndRetryValidatesExistingPages()throws Exception {
        failLate=true;
        try{download();fail("chapter error expected");}catch(IOException expected){assertTrue(expected.getMessage(),expected.getMessage().contains("synthetic"));}
        assertEquals(0,task.done);assertEquals(0,requests.get());
        File alreadySaved=new File(fixture.store.cache(task),"images/0101/00001.jpg");
        Files.createDirectories(alreadySaved.getParentFile().toPath());Files.write(alreadySaved.toPath(),jpegs[ORIGINAL%jpegs.length]);
        int saved=1;
        assertEquals(ORIGINAL,AlbumStorage.load(fixture.c,Uri.parse(base.uri)).images.size());
        assertTrue(task.resultUri.isEmpty());failLate=false;
        download();assertEquals(saved,task.cached);assertEquals(ADDED-saved,requests.get());assertEquals(ADDED,task.total);assertEquals(ADDED,task.done);
    }
}
