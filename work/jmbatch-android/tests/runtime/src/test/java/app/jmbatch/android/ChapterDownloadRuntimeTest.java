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
    static CountDownLatch firstImage;
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
            // Hold the rest of the catalogue until the downloader actually requests a page.
            if(chapter>=ORIGINAL+4&&!firstImage.await(5,TimeUnit.SECONDS))throw new IOException("first image waited for all chapter details");
            if(failLate&&chapter==ORIGINAL+8)throw new IOException("synthetic chapter failure");
            Thread.sleep(chapter%4==0?32:8);
            details.incrementAndGet();
            return new JSONObject().put("images",new JSONArray().put("image.jpg"));
        }
        @Implementation protected long scramble(String id){return 10000000;}
        @Implementation protected void image(String chapter,String name,File output,int round)throws Exception {
            if(requests.getAndIncrement()==0){
                firstReady.set(details.get());firstImageMs=java.lang.management.ManagementFactory.getRuntimeMXBean().getUptime()-start;firstImage.countDown();
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
        firstImage=new CountDownLatch(1);details=new AtomicInteger();requests=new AtomicInteger();firstReady=new AtomicInteger();failLate=false;
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
    @Test public void firstImageStartsBeforeAll145DetailsAndOutputKeepsChapterOrder()throws Exception {
        download();assertTrue(firstImageMs>=0);assertTrue(firstReady.get()>=1&&firstReady.get()<ADDED);
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
    @Test public void laterMetadataFailureKeepsOriginalAndRetryReusesDownloadedPages()throws Exception {
        failLate=true;
        try{download();fail("chapter error expected");}catch(IOException expected){assertTrue(expected.getMessage(),expected.getMessage().contains("synthetic"));}
        int saved=task.done;assertTrue(saved>0&&saved<ADDED);
        assertEquals(ORIGINAL,AlbumStorage.load(fixture.c,Uri.parse(base.uri)).images.size());
        assertTrue(task.resultUri.isEmpty());failLate=false;
        download();assertEquals(saved,task.cached);assertEquals(ADDED,requests.get());assertEquals(ADDED,task.total);assertEquals(ADDED,task.done);
    }
}
