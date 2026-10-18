package app.jmbatch.android;

import android.content.*;
import android.content.pm.ProviderInfo;
import android.database.*;
import android.net.Uri;
import android.provider.DocumentsContract;
import android.graphics.Bitmap;
import android.os.Looper;
import android.widget.TextView;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.*;
import org.robolectric.android.controller.ActivityController;
import org.robolectric.shadows.ShadowContentResolver;
import java.io.*;
import java.nio.file.*;
import java.lang.reflect.*;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

/** Production reader and Android document APIs; synthetic books, no real device timings. */
@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29},qualifiers="w360dp-h800dp-mdpi")
@LooperMode(LooperMode.Mode.PAUSED)
public class ReaderAlbumRuntimeTest {
    Context context;File root;ActivityController<ReaderActivity> controller;
    @Before public void setup()throws Exception {
        context=RuntimeEnvironment.getApplication();
        root=new File(AlbumStorage.root(context),"JM123-reader-"+String.format("%08x",new Random().nextInt()));
        assertTrue(root.mkdirs());
        for(Class<?> type:new Class<?>[]{Store.class,LibraryStore.class}){Field f=type.getDeclaredField("instance");f.setAccessible(true);f.set(null,null);}
        for(String name:new String[]{"queue.json","library.json"})Files.deleteIfExists(new File(context.getFilesDir(),name).toPath());
    }
    @After public void close()throws Exception {
        if(controller!=null){ReaderActivity activity=controller.get();controller.pause().stop().destroy();((ExecutorService)field(activity,"worker")).awaitTermination(10,TimeUnit.SECONDS);shadowOf(Looper.getMainLooper()).idle();}
    }
    static Object field(Object target,String name)throws Exception {Field f=target.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(target);}
    JSONObject metadata(int chapters,int count,int version,long size)throws Exception {
        JSONArray entries=new JSONArray();for(int c=1;c<=chapters;c++)for(int p=1;p<=count;p++)entries.put(new JSONObject().put("chapter",c).put("page",p).put("file",version==1?AlbumRules.imageName(c,p):AlbumRules.imageName(c,p,chapters)).put("size",size));
        return new JSONObject().put("version",version).put("id","123").put("title","Synthetic reader book").put("entries",entries);
    }
    Uri uri(){return ExportProvider.uri(context,root);}
    void manifest(JSONObject value)throws Exception {Files.write(new File(root,AlbumRules.MANIFEST).toPath(),value.toString().getBytes("UTF-8"));}
    void image(String name,byte[] bytes)throws Exception {File file=new File(root,name);file.getParentFile().mkdirs();Files.write(file.toPath(),bytes);}
    ReaderAlbum open()throws Exception {return new ReaderAlbum(context,uri(),()->{},text->{});}
    @Test public void indexedLargeBookDoesNotInspectOtherChaptersBeforeResume()throws Exception {
        manifest(metadata(100,50,2,3));image("0050/00011.jpg",new byte[]{1,2,3});
        ReaderAlbum album=open();assertEquals(5000,album.chapters.length);assertEquals(0,album.checked());
        assertEquals(2460,album.next(2460));assertEquals(50,album.image(2460).chapter);assertEquals(1,album.checked());
        for(int p=12;p<=15;p++)image("0050/"+String.format("%05d.jpg",p),new byte[]{1,2,3});
        for(int index=2461;index<=2464;index++){assertEquals(index,album.next(2460));album.image(index);}
        assertEquals(2459,album.next(2460));
        // A jump takes priority over the previous background position.
        assertEquals(4000,album.next(4000));
        ReaderAlbum reopened=open();assertEquals(0,reopened.checked());assertEquals(50,reopened.image(2460).chapter);
    }
    @Test public void providerEnumerationIsLazyAndForwardPriorityCrossesChapters()throws Exception {
        TreeProvider provider=provider(120,5);Uri tree=tree();AlbumStorage.remember(context,tree,metadata(120,5,2,3));
        ReaderAlbum album=new ReaderAlbum(context,tree,()->{},text->{});
        assertEquals(Arrays.asList("root"),provider.queries);
        album.image(248);assertEquals(Arrays.asList("root","root/0050"),provider.queries);
        for(int index=249;index<=252;index++){assertEquals(index,album.next(248));album.image(index);}
        assertEquals(Arrays.asList("root","root/0050","root/0051"),provider.queries);
        assertEquals(400,album.next(400));album.image(400);
        assertEquals("root/0081",provider.queries.get(provider.queries.size()-1));
        // Reopen reuses saved metadata, querying only root and requested chapter.
        provider.queries.clear();ReaderAlbum again=new ReaderAlbum(context,tree,()->{},text->{});again.image(248);
        assertEquals(Arrays.asList("root","root/0050"),provider.queries);
    }
    @Test public void backgroundFindsMissingPagesWithoutBlockingGoodPageAndCanRetry()throws Exception {
        manifest(metadata(2,20,2,3));image("0002/00001.jpg",new byte[]{1,2,3});ReaderAlbum album=open();
        assertNotNull(album.image(20));int calls=0;Map<Integer,String> errors=new HashMap<>();
        while(album.pending()){int before=album.checked();errors.putAll(album.check(20));assertTrue(album.checked()-before<=16);assertTrue(++calls<50);}
        assertEquals(40,album.checked());assertEquals(39,album.failed());assertFalse(errors.containsKey(20));
        image("0001/00001.jpg",new byte[]{1,2,3});album.retry(0);assertNotNull(album.image(0));assertEquals(38,album.failed());
        image("0002/00001.jpg",new byte[]{1});album.retry(20);
        try{album.image(20);fail("changed size accepted");}catch(IOException expected){}
    }
    @Test public void oldLayoutAndFlatFolderBothRestore()throws Exception {
        manifest(metadata(1,2,1,3));image("0001/00002.jpg",new byte[]{1,2,3});assertNotNull(open().image(1));
        manifest(metadata(1,2,2,3));image("00002.jpg",new byte[]{1,2,3});assertNotNull(open().image(1));
    }
    @Test public void missingOrCorruptIndexRebuildsAndPersists()throws Exception {
        image("00001.jpg",new byte[]{1,2,3});image("00002.jpg",new byte[]{1,2,3});
        List<String> progress=new ArrayList<>();ReaderAlbum first=new ReaderAlbum(context,uri(),()->{},progress::add);
        assertEquals(2,first.chapters.length);assertTrue(AlbumStorage.index(context,uri()).isFile());
        assertTrue(progress.stream().anyMatch(s->s.contains("已发现 2 页")));
        // Corrupted private index is recovered from the real folder.
        Files.write(AlbumStorage.index(context,uri()).toPath(),new byte[]{'{'});
        assertEquals(2,open().chapters.length);
        Files.write(new File(root,AlbumRules.MANIFEST).toPath(),new byte[]{'{'});
        assertEquals(2,open().chapters.length);
    }
    @Test public void currentManifestReplacesOldSavedMetadata()throws Exception {
        AlbumStorage.remember(context,uri(),metadata(1,1,2,3));manifest(metadata(1,3,2,3));image("00003.jpg",new byte[]{1,2,3});
        ReaderAlbum album=open();assertEquals(3,album.chapters.length);assertNotNull(album.image(2));
    }
    @Test public void unsafeIndexIsNotUsedAndCancellationStopsWork()throws Exception {
        JSONObject invalid=metadata(1,1,2,3);invalid.getJSONArray("entries").getJSONObject(0).put("file","../outside.jpg");manifest(invalid);
        try{open();fail("unsafe index accepted");}catch(Exception expected){}
        manifest(metadata(1,1,2,3));AtomicBoolean cancelled=new AtomicBoolean();
        ReaderAlbum album=new ReaderAlbum(context,uri(),()->{if(cancelled.get())throw new InterruptedIOException();},text->{});
        cancelled.set(true);try{album.check(0);fail("cancel ignored");}catch(InterruptedIOException expected){}
        assertEquals(0,album.checked());
    }
    @Test public void activityShowsSavedPageBeforeFullValidationAndStopsOnClose()throws Exception {
        activityResume("paged");
    }
    @Test public void scrollingResumesAndPrefetchesWithoutUnboundedDecodeQueue()throws Exception {
        activityResume("scroll");
    }
    private void activityResume(String mode)throws Exception {
        ByteArrayOutputStream out=new ByteArrayOutputStream();Bitmap bitmap=Bitmap.createBitmap(600,900,Bitmap.Config.ARGB_8888);bitmap.eraseColor(-1);bitmap.compress(Bitmap.CompressFormat.JPEG,85,out);bitmap.recycle();byte[] bytes=out.toByteArray();
        manifest(metadata(100,50,2,bytes.length));for(int p=11;p<=17;p++)image("0050/"+String.format("%05d.jpg",p),bytes);
        String key=uri().toString();context.getSharedPreferences("reader-history",0).edit().putString(key,new JSONObject().put("page",2460).put("mode",mode).toString()).commit();
        LibraryStore.Entry entry=new LibraryStore.Entry("123","Synthetic",key,"","","images",false);
        Intent intent=new Intent(context,ReaderActivity.class).putExtra("entry",entry.json().toString());
        controller=Robolectric.buildActivity(ReaderActivity.class,intent);controller.get().setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup().visible();
        ReaderActivity activity=controller.get();ReaderPager pager=null;android.util.LruCache<?,?> cache=null;
        for(int i=0;i<40;i++){
            ((ExecutorService)field(activity,"worker")).submit(()->{}).get(10,TimeUnit.SECONDS);
            shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(16));pager=(ReaderPager)field(activity,"pager");
            cache=(android.util.LruCache<?,?>)field(activity,"cache");
            if(mode.equals("paged")?pager!=null&&pager.displayed()==2460:cache.size()>0)break;
        }
        if(mode.equals("paged")){assertNotNull(pager);assertEquals(2460,pager.displayed());}
        else{assertEquals(2460,((android.widget.ListView)field(activity,"list")).getFirstVisiblePosition());assertTrue(cache.size()>0);}
        ReaderAlbum album=(ReaderAlbum)field(field(activity,"source"),"album");assertTrue(album.checked()<50);assertTrue(album.pending());
        assertTrue(((TextView)field(activity,"status")).getText().toString().contains("页"));
        for(int i=0;i<20;i++){
            ((ExecutorService)field(activity,"worker")).submit(()->{}).get(10,TimeUnit.SECONDS);shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(16));
        }
        assertTrue(cache.size()<=32*1024*1024);assertTrue(((ReaderRequests)field(activity,"requests")).waiting()<=8);
        assertFalse("forward pages checked before whole book",album.next(2460)>=2460&&album.next(2460)<=2464);
        assertTrue(album.pending());
        controller.pause().stop().destroy();controller=null;
        assertTrue(((ExecutorService)field(activity,"worker")).awaitTermination(10,TimeUnit.SECONDS));
        shadowOf(Looper.getMainLooper()).idle();
    }
    private Uri tree(){return DocumentsContract.buildDocumentUriUsingTree(Uri.parse("content://reader.test/tree/root"),"root");}
    private TreeProvider provider(int chapters,int pages){
        TreeProvider provider=new TreeProvider(chapters,pages);ProviderInfo info=new ProviderInfo();info.authority="reader.test";provider.attachInfo(context,info);ShadowContentResolver.registerProviderInternal(info.authority,provider);return provider;
    }
    public static class TreeProvider extends ContentProvider {
        final int chapters,pages;final List<String> queries=new ArrayList<>();TreeProvider(int c,int p){chapters=c;pages=p;}
        public boolean onCreate(){return true;}
        public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){
            String id=DocumentsContract.getDocumentId(uri);queries.add(id);MatrixCursor cursor=new MatrixCursor(projection);
            if(id.equals("root")){for(int c=1;c<=chapters;c++){String name=String.format("%04d",c);cursor.addRow(new Object[]{"root/"+name,name,DocumentsContract.Document.MIME_TYPE_DIR,0L});}}
            else for(int p=1;p<=pages;p++){String name=String.format("%05d.jpg",p);cursor.addRow(new Object[]{id+"/"+name,name,"image/jpeg",3L});}
            return cursor;
        }
        public String getType(Uri uri){return null;}public Uri insert(Uri uri,ContentValues v){throw new UnsupportedOperationException();}public int delete(Uri uri,String s,String[] a){throw new UnsupportedOperationException();}public int update(Uri uri,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
    }
}
