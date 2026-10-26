package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.content.pm.ProviderInfo;
import android.database.*;
import android.net.Uri;
import android.os.*;
import android.provider.OpenableColumns;
import android.widget.Button;
import java.io.*;
import java.lang.reflect.*;
import java.nio.file.Files;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.*;
import org.robolectric.android.controller.ActivityController;
import org.robolectric.shadows.*;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},qualifiers="w360dp-h800dp-mdpi")
@LooperMode(LooperMode.Mode.PAUSED)
public class FileSharingRuntimeTest {
    ActivityController<Activity> controller;
    Activity activity;
    LibraryScreen screen;
    ExportProvider provider;
    @Before public void setup()throws Exception{
        for(Class<?> type:new Class<?>[]{Store.class,LibraryStore.class}){
            Field f=type.getDeclaredField("instance");f.setAccessible(true);f.set(null,null);
        }
        for(String name:new String[]{"queue.json","library.json"})
            Files.deleteIfExists(new File(RuntimeEnvironment.getApplication().getFilesDir(),name).toPath());
        controller=Robolectric.buildActivity(Activity.class);activity=controller.get();
        activity.setTheme(android.R.style.Theme_Material_Light_NoActionBar);controller.setup();
        provider=new ExportProvider();register(activity.getPackageName()+".exports",provider);
        AlbumStorage.root(activity).mkdirs();
    }
    @After public void close()throws Exception{
        if(screen!=null)screen.close();frames();
        if(screen!=null)((ExecutorService)field(screen,"worker")).awaitTermination(10,TimeUnit.SECONDS);
        controller.pause().stop().destroy();frames();
    }
    void register(String authority,ContentProvider p){ProviderInfo info=new ProviderInfo();info.authority=authority;info.grantUriPermissions=true;p.attachInfo(activity,info);ShadowContentResolver.registerProviderInternal(authority,p);}
    static Object field(Object target,String name)throws Exception{Field f=target.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(target);}
    static Object call(Object target,String name,Class<?>[] types,Object... args)throws Exception{Method m=target.getClass().getDeclaredMethod(name,types);m.setAccessible(true);return m.invoke(target,args);}
    static void frames(){shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(200));}
    void drain()throws Exception{((ExecutorService)field(screen,"worker")).submit(()->{}).get(10,TimeUnit.SECONDS);}
    void settle()throws Exception{drain();frames();drain();frames();}
    LibraryStore.Entry entry(String suffix)throws Exception{
        File file=new File(AlbumStorage.root(activity),"JM123-"+UUID.randomUUID()+suffix);
        Files.write(file.toPath(),new byte[]{1,2,3,4});
        return new LibraryStore.Entry("123",file.getName(),ExportProvider.uri(activity,file).toString(),"","test",suffix.toLowerCase(Locale.ROOT).endsWith(".pdf")?"pdf":"zip",false,"",1,4);
    }
    Intent prepare(LibraryStore.Entry... items)throws Exception{return FileSharing.prepare(activity,Arrays.asList(items),new CancellationSignal());}
    void matches(Intent intent,String action,String mime)throws Exception{
        IntentFilter target=new IntentFilter(action);target.addDataType(mime);
        assertTrue(target.match(intent.getAction(),intent.getType(),null,null,null,"share-test")>=0);
    }
    Intent next(){Intent chooser=shadowOf(activity).getNextStartedActivity();assertNotNull(chooser);assertEquals(Intent.ACTION_CHOOSER,chooser.getAction());assertTrue((chooser.getFlags()&Intent.FLAG_GRANT_READ_URI_PERMISSION)!=0);assertNotNull(chooser.getClipData());return chooser.getParcelableExtra(Intent.EXTRA_INTENT);}
    void open(LibraryStore.Entry... entries)throws Exception{
        LibraryStore.get(activity).importFound(Arrays.asList(entries));
        screen=new LibraryScreen(activity,Store.get(activity));screen.show();settle();
        call(screen,"setBatchMode",new Class<?>[]{boolean.class},true);
        for(int i=0;i<entries.length;i++)call(screen,"itemClick",new Class<?>[]{int.class},i);
        frames();
    }
    @SuppressWarnings("unchecked") void clickShare()throws Exception{
        List<Button> buttons=(List<Button>)field(screen,"batchButtons");
        Button share=buttons.stream().filter(b->"分享".contentEquals(b.getContentDescription()==null?"":b.getContentDescription())).findFirst().get();
        assertTrue(share.isEnabled());assertTrue(share.performClick());
    }
    @Test public void singlePdfAndZipMatchSingleFileTargets()throws Exception{
        for(String suffix:new String[]{".pdf",".zip"}){
            LibraryStore.Entry e=entry(suffix);Intent i=prepare(e);
            assertEquals(Intent.ACTION_SEND,i.getAction());assertEquals(LibraryRules.mimeType(e.title),i.getType());
            assertEquals(Uri.parse(e.uri),i.getParcelableExtra(Intent.EXTRA_STREAM));matches(i,Intent.ACTION_SEND,i.getType());
        }
    }
    @Test public void homogeneousBatchesAndMixedTypesMatchTargets()throws Exception{
        for(String suffix:new String[]{".pdf",".zip"}){
            LibraryStore.Entry a=entry(suffix),b=entry(suffix);Intent i=prepare(a,b);
            assertEquals(Intent.ACTION_SEND_MULTIPLE,i.getAction());assertEquals(LibraryRules.mimeType(a.title),i.getType());
            assertEquals(Arrays.asList(Uri.parse(a.uri),Uri.parse(b.uri)),i.getParcelableArrayListExtra(Intent.EXTRA_STREAM));
            assertEquals(2,i.getClipData().getItemCount());assertEquals(Uri.parse(b.uri),i.getClipData().getItemAt(1).getUri());matches(i,Intent.ACTION_SEND_MULTIPLE,i.getType());
        }
        Intent mixed=prepare(entry(".pdf"),entry(".zip"),entry(".pdf"));assertEquals("*/*",mixed.getType());matches(mixed,Intent.ACTION_SEND_MULTIPLE,"*/*");
    }
    @Test public void uppercasePdfProviderAndDirectoryShareAgree()throws Exception{
        LibraryStore.Entry e=entry(".PDF");Uri uri=Uri.parse(e.uri);assertEquals("application/pdf",provider.getType(uri));
        SavedDirectory browser=new SavedDirectory(activity,"","test");browser.show();
        Object item=null;
        try{
            for(int attempt=0;attempt<100&&item==null;attempt++){
                frames();for(Object candidate:(List<?>)field(browser,"items"))if(uri.equals(field(candidate,"uri")))item=candidate;
                if(item==null)Thread.sleep(20);
            }
            assertNotNull("background directory listing",item);assertEquals("application/pdf",field(item,"mime"));
            call(browser,"open",new Class<?>[]{item.getClass(),boolean.class},item,true);
            assertEquals("application/pdf",next().getType());
        }finally{((AlertDialog)field(browser,"dialog")).dismiss();frames();}
    }
    @Test public void providerMetadataReadOnlyBytesAndShareGrantsRemainValid()throws Exception{
        LibraryStore.Entry e=entry(".pdf");Uri uri=Uri.parse(e.uri);Intent i=prepare(e);
        assertEquals(uri,i.getClipData().getItemAt(0).getUri());assertTrue((i.getFlags()&Intent.FLAG_GRANT_READ_URI_PERMISSION)!=0);
        try(Cursor c=provider.query(uri,null,null,null,null)){assertTrue(c.moveToFirst());assertEquals(e.title,c.getString(c.getColumnIndex(OpenableColumns.DISPLAY_NAME)));assertEquals(4,c.getLong(c.getColumnIndex(OpenableColumns.SIZE)));}
        try(InputStream in=activity.getContentResolver().openInputStream(uri)){assertArrayEquals(new byte[]{1,2,3,4},read(in));}
        try{provider.openFile(uri,"w");fail("write access");}catch(FileNotFoundException expected){}
    }
    static byte[] read(InputStream in)throws IOException{ByteArrayOutputStream out=new ByteArrayOutputStream();int b;while((b=in.read())!=-1)out.write(b);return out.toByteArray();}
    @Test public void missingFileAndUnreadableProviderBlockWholeBatch()throws Exception{
        LibraryStore.Entry a=entry(".pdf"),b=entry(".zip");Files.delete(AlbumStorage.local(activity,Uri.parse(b.uri)).toPath());
        try{prepare(a,b);fail("missing file shared");}catch(IOException expected){assertTrue(expected.getMessage().contains("文件不存在"));}
        TestProvider denied=new TestProvider();denied.denied=true;register("share.test",denied);
        try{prepare(a,remote());fail("revoked permission shared");}catch(IOException expected){assertTrue(expected.getMessage().contains("读取权限已失效"));}
    }
    @Test public void cancelledAndImageFolderRequestsDoNotPrepareShare()throws Exception{
        CancellationSignal signal=new CancellationSignal();signal.cancel();
        try{FileSharing.prepare(activity,Collections.singletonList(entry(".pdf")),signal);fail("cancelled share");}catch(OperationCanceledException expected){}
        try{prepare(new LibraryStore.Entry("123","folder","content://invalid/folder","","","images",false));fail("folder shared");}catch(IOException expected){assertTrue(expected.getMessage().contains("先导出"));}
    }
    @Test public void realShareButtonReadsSafInBackgroundThenOpensChooser()throws Exception{
        TestProvider remote=new TestProvider();remote.file=AlbumStorage.local(activity,Uri.parse(entry(".zip").uri));register("share.test",remote);
        open(remote());clickShare();settle();Intent intent=next();
        assertEquals(Intent.ACTION_SEND,intent.getAction());assertEquals("application/zip",intent.getType());
        assertTrue(remote.opens>0);assertFalse("file preflight on UI thread",remote.openedOnMain);
    }
    @Test public void realShareButtonShowsMissingFileBeforeChooser()throws Exception{
        LibraryStore.Entry e=entry(".zip");open(e);Files.delete(AlbumStorage.local(activity,Uri.parse(e.uri)).toPath());clickShare();settle();
        assertNull(shadowOf(activity).getNextStartedActivity());
        AlertDialog error=ShadowAlertDialog.getLatestAlertDialog();assertTrue(error.isShowing());assertTrue(shadowOf(error).getMessage().toString().contains("文件不存在"));error.dismiss();
    }
    @Test public void cancelAfterPreflightBeforeCallbackDoesNotOpenChooser()throws Exception{
        open(entry(".zip"));clickShare();drain();call(screen,"cancel",new Class<?>[]{});settle();assertNull(shadowOf(activity).getNextStartedActivity());
    }
    @Test public void closeAfterPreflightBeforeCallbackDoesNotOpenChooser()throws Exception{
        open(entry(".zip"));clickShare();drain();screen.close();frames();assertNull(shadowOf(activity).getNextStartedActivity());
    }
    LibraryStore.Entry remote(){return new LibraryStore.Entry("123","remote.zip","content://share.test/tree/root/document/root%2Fremote.zip","content://share.test/tree/root","test","zip",false,"",1,4);}
    public static class TestProvider extends ContentProvider {
        File file;boolean denied,openedOnMain;int opens;
        public boolean onCreate(){return true;}
        public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){
            MatrixCursor c=new MatrixCursor(projection);Object[] values=new Object[projection.length];
            for(int j=0;j<projection.length;j++)values[j]=projection[j].equals("_display_name")?"remote.zip":projection[j].equals("mime_type")?"application/zip":4L;c.addRow(values);return c;
        }
        public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{
            if(denied)throw new SecurityException("revoked");opens++;openedOnMain|=Looper.myLooper()==Looper.getMainLooper();return ParcelFileDescriptor.open(file,ParcelFileDescriptor.MODE_READ_ONLY);
        }
        public String getType(Uri uri){return "application/zip";}
        public Uri insert(Uri u,ContentValues v){throw new UnsupportedOperationException();}
        public int update(Uri u,ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
        public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
    }
}
