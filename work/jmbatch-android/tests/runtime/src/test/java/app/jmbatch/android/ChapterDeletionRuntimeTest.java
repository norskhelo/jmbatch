package app.jmbatch.android;

import android.content.*;
import android.content.pm.ProviderInfo;
import android.database.*;
import android.net.Uri;
import android.os.*;
import android.provider.*;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.*;
import org.robolectric.shadows.ShadowContentResolver;
import java.io.*;
import java.lang.reflect.Field;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.zip.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29})
@LooperMode(LooperMode.Mode.PAUSED)
public class ChapterDeletionRuntimeTest {
    Context context;Store store;LibraryStore library;File root;TreeProvider provider;
    @Before public void setup()throws Exception {
        context=RuntimeEnvironment.getApplication();
        for(Class<?> type:new Class<?>[]{Store.class,LibraryStore.class}){Field field=type.getDeclaredField("instance");field.setAccessible(true);field.set(null,null);}
        for(String name:new String[]{"queue.json","library.json"})Files.deleteIfExists(new File(context.getFilesDir(),name).toPath());
        context.getSharedPreferences("reader-history",0).edit().clear().commit();
        store=Store.get(context);library=LibraryStore.get(context);
        root=new File(AlbumStorage.root(context),"JM123-test-"+UUID.randomUUID().toString().substring(0,8));assertTrue(root.mkdirs());
    }
    LibraryStore.Entry fixture(boolean zip,boolean saf)throws Exception {
        File source=zip?new File(root.getParentFile(),root.getName()+".zip"):root;
        if(zip){try(ZipOutputStream out=new ZipOutputStream(new FileOutputStream(source))){for(int c=1;c<=3;c++)for(int p=1;p<=2;p++){out.putNextEntry(new ZipEntry(String.format("%04d/%05d.jpg",c,p)));out.write(new byte[]{(byte)c,(byte)p,7});out.closeEntry();}out.putNextEntry(new ZipEntry("notes.txt"));out.write(new byte[]{9,8});out.closeEntry();}}
        else for(int c=1;c<=3;c++)for(int p=1;p<=2;p++){File image=new File(root,String.format("%04d/%05d.jpg",c,p));image.getParentFile().mkdirs();Files.write(image.toPath(),new byte[]{(byte)c,(byte)p,7});}
        String tree="";Uri uri=ExportProvider.uri(context,source);
        if(saf){
            provider=new TreeProvider(root.getParentFile());ProviderInfo info=new ProviderInfo();info.authority="chapters.test";info.exported=true;info.grantUriPermissions=true;info.readPermission=info.writePermission="android.permission.MANAGE_DOCUMENTS";
            provider.attachInfo(context,info);
            // Robolectric routes legacy resolver queries directly to the provider,
            // bypassing Android's transport conversion to Bundle query arguments.
            Bridge bridge=new Bridge(provider);bridge.attachInfo(context,info);ShadowContentResolver.registerProviderInternal(info.authority,bridge);
            tree="content://chapters.test/tree/root";uri=DocumentsContract.buildDocumentUriUsingTree(Uri.parse(tree),"root/"+source.getName());
        }
        LibraryStore.Entry item=new LibraryStore.Entry("123","test",uri.toString(),tree,"test",zip?"zip":"images",true);
        library.importFound(Collections.singletonList(item));Store.Settings settings=new Store.Settings();settings.format=item.format;settings.outputUri=tree;
        Store.Task task=new Store.Task("123",settings);task.status="done";task.title="test";task.resultUri=item.uri;store.tasks.add(task);store.save();
        context.getSharedPreferences("reader-history",0).edit().putString(item.uri,new JSONObject().put("page",4).put("mode","paged").put("bookmarks",new JSONArray(Arrays.asList(0,2,4,5))).toString()).commit();
        return item;
    }
    String delete(LibraryStore.Entry entry,Integer... removed)throws Exception {
        return ChapterDeletion.delete(context,store,entry,ChapterDeletion.inspect(context,entry,()->false),new HashSet<>(Arrays.asList(removed)),()->false,t->{});
    }
    void assertUpdated(LibraryStore.Entry old,boolean saf)throws Exception {
        List<LibraryStore.Entry> all=library.list("",false);assertEquals(1,all.size());LibraryStore.Entry next=all.get(0);assertTrue(next.favorite);assertNotEquals(old.uri,next.uri);assertEquals(next.uri,store.tasks.get(0).resultUri);
        assertEquals(4,ChapterDeletion.inspect(context,next,()->false).chapters.size());
        assertEquals(2,next.chapterCount);
        store.tasks.get(0).selectedChapters=Arrays.asList(new ChapterRules.Chapter("1",1,"one"),new ChapterRules.Chapter("2",2,"two"),new ChapterRules.Chapter("3",3,"three"));
        library.sync(store.snapshot());assertEquals(2,library.list("",false).get(0).chapterCount);
        JSONObject state=new JSONObject(context.getSharedPreferences("reader-history",0).getString(next.uri,"{}"));assertEquals(2,state.getInt("page"));assertEquals("[0,2,3]",state.getJSONArray("bookmarks").toString());assertEquals("paged",state.getString("mode"));
        assertFalse(root.exists());assertFalse(store.libraryBusy);
    }
    @Test public void localFolderRemapsStateAndCanBeDeletedAgain()throws Exception {
        LibraryStore.Entry old=fixture(false,false);delete(old,2);assertUpdated(old,false);
        LibraryStore.Entry next=library.list("",false).get(0);AlbumStorage.Album album=AlbumStorage.load(context,Uri.parse(next.uri));
        assertArrayEquals(new byte[]{3,1,7},Files.readAllBytes(AlbumStorage.local(context,album.images.get(2).uri).toPath()));
        delete(next,1);LibraryStore.Entry last=library.list("",false).get(0);AlbumStorage.forget(context,Uri.parse(last.uri));
        assertEquals(1,last.chapterCount);
        assertEquals(2,AlbumStorage.load(context,Uri.parse(last.uri)).images.size());
        assertEquals("00001.jpg",AlbumStorage.load(context,Uri.parse(last.uri)).images.get(0).file);
    }
    @Test public void zipPreservesRawPagesAndOtherEntries()throws Exception {
        LibraryStore.Entry old=fixture(true,false);delete(old,1,3);LibraryStore.Entry next=library.list("",false).get(0);
        try(ZipFile zip=new ZipFile(AlbumStorage.local(context,Uri.parse(next.uri)))){assertEquals(3,zip.size());assertArrayEquals(new byte[]{2,1,7},read(zip.getInputStream(zip.getEntry("0002/00001.jpg"))));assertArrayEquals(new byte[]{9,8},read(zip.getInputStream(zip.getEntry("notes.txt"))));}
        assertFalse(AlbumStorage.local(context,Uri.parse(old.uri)).exists());
    }
    @Test public void safFolderAndZipUseValidatedPublication()throws Exception {
        LibraryStore.Entry old=fixture(false,true);delete(old,2);assertUpdated(old,true);
        assertTrue(provider.creates>0);assertTrue(provider.renames>0);assertTrue(provider.deletes>0);
        LibraryStore.Entry next=library.list("",false).get(0);assertEquals(2,AlbumStorage.load(context,Uri.parse(next.uri)).images.get(2).chapter);
    }
    @Test public void safZipRetainsBytesAndOriginalOnRenameFailure()throws Exception {
        LibraryStore.Entry old=fixture(true,true);provider.failRename=true;
        try{delete(old,2);fail();}catch(Exception expected){assertTrue(expected.getMessage().contains("重命名"));}
        assertEquals(old.uri,library.list("",false).get(0).uri);assertTrue(provider.file(DocumentsContract.getDocumentId(Uri.parse(old.uri))).isFile());
        provider.failRename=false;delete(old,2);assertEquals(4,ChapterDeletion.inspect(context,library.list("",false).get(0),()->false).chapters.size());
    }
    @Test public void cancellationAndInvalidSelectionPreserveOriginal()throws Exception {
        LibraryStore.Entry old=fixture(false,false);ChapterDeletion.Plan plan=ChapterDeletion.inspect(context,old,()->false);
        for(Set<Integer> choice:Arrays.asList(Collections.<Integer>emptySet(),new HashSet<>(Arrays.asList(1,2,3)),Collections.singleton(8))){try{ChapterDeletion.delete(context,store,old,plan,choice,()->false,t->{});fail();}catch(IOException expected){}}
        AtomicBoolean cancelled=new AtomicBoolean();
        try{ChapterDeletion.delete(context,store,old,plan,Collections.singleton(2),cancelled::get,t->{if(t.equals("校验保留图片 4/4"))cancelled.set(true);});fail();}catch(IOException expected){assertTrue(expected.getMessage().contains("取消"));}
        assertEquals(6,AlbumStorage.load(context,Uri.parse(old.uri)).images.size());assertEquals(old.uri,library.list("",false).get(0).uri);assertFalse(store.libraryBusy);
    }
    @Test public void failedLibraryCommitPreservesSourceAndRemovesReplacement()throws Exception {
        LibraryStore.Entry old=fixture(false,false);Set<String> before=new HashSet<>(Arrays.asList(root.getParentFile().list()));
        try{ChapterDeletion.delete(context,store,old,ChapterDeletion.inspect(context,old,()->false),Collections.singleton(2),()->false,t->{if(t.startsWith("校验保留图片")){try{Field f=LibraryStore.class.getDeclaredField("loadError");f.setAccessible(true);f.set(library,"simulated unwritable index");}catch(Exception e){throw new RuntimeException(e);}}});fail();}catch(IOException expected){assertTrue(expected.getMessage().contains("simulated"));}
        assertTrue(root.exists());assertEquals(before,new HashSet<>(Arrays.asList(root.getParentFile().list())));assertEquals(old.uri,store.tasks.get(0).resultUri);
    }
    @Test public void staleFilesForeignFilesAndActiveDownloadsRejected()throws Exception {
        LibraryStore.Entry old=fixture(false,false);ChapterDeletion.Plan plan=ChapterDeletion.inspect(context,old,()->false);
        Files.write(new File(root,"0001/00001.jpg").toPath(),new byte[]{1,2,3,4});
        try{ChapterDeletion.delete(context,store,old,plan,Collections.singleton(2),()->false,t->{});fail();}catch(IOException expected){}
        Files.write(new File(root,"personal.txt").toPath(),new byte[]{1});try{ChapterDeletion.inspect(context,old,()->false);fail();}catch(IOException expected){assertTrue(expected.getMessage().contains("额外"));}
        store.running=true;try{ChapterDeletion.delete(context,store,old,plan,Collections.singleton(2),()->false,t->{});fail();}catch(IOException expected){assertTrue(expected.getMessage().contains("暂停"));}
        assertTrue(root.exists());assertFalse(store.libraryBusy);
    }
    @Test public void safCleanupFailureKeepsReplacementAndReportsOldUri()throws Exception {
        LibraryStore.Entry old=fixture(false,true);provider.failDelete=DocumentsContract.getDocumentId(Uri.parse(old.uri));String message=delete(old,2);
        assertTrue(message.contains("清理未完成"));assertTrue(message.contains(old.uri));assertTrue(root.exists());assertNotEquals(old.uri,library.list("",false).get(0).uri);
    }
    @Test public void largeFolderReadsOneListingPerChapterWithAndWithoutIndex()throws Exception {
        LibraryStore.Entry item=fixture(false,true);JSONArray records=new JSONArray();
        for(int c=1;c<=151;c++)for(int p=1;p<=(c<=130?48:47);p++){
            String name=String.format(Locale.ROOT,"%04d/%05d.jpg",c,p);File image=new File(root,name);image.getParentFile().mkdirs();Files.write(image.toPath(),new byte[]{1,2,3});
            records.put(new JSONObject().put("chapter",c).put("page",p).put("file",name).put("size",3));
        }
        Uri uri=Uri.parse(item.uri);AlbumStorage.remember(context,uri,new JSONObject().put("version",2).put("id","123").put("title","test").put("entries",records));
        for(boolean indexed:new boolean[]{true,false}){
            if(!indexed)AlbumStorage.forget(context,uri);
            provider.documents=provider.children=0;provider.reads.clear();List<String> progress=new ArrayList<>();
            ChapterDeletion.Plan plan=ChapterDeletion.inspect(context,item,()->false,progress::add);
            assertEquals(151,plan.counts.size());assertEquals(7227,plan.chapters.size());
            assertEquals(152,provider.children);assertEquals(indexed?1:2,provider.documents);assertTrue(provider.reads.isEmpty());
            assertTrue(progress.get(0).contains("正在检查"));assertTrue(progress.get(progress.size()-1).contains("7227/7227"));
        }
    }
    @Test public void safRetainedPagesAreReadOnceAndWrittenOnceWithoutCacheCopy()throws Exception {
        LibraryStore.Entry item=fixture(false,true);ChapterDeletion.Plan plan=ChapterDeletion.inspect(context,item,()->false);
        provider.reads.clear();provider.writes.clear();String oldPrefix=DocumentsContract.getDocumentId(Uri.parse(item.uri))+"/";
        List<String> progress=new ArrayList<>();ChapterDeletion.delete(context,store,item,plan,Collections.singleton(2),()->false,progress::add);
        int sourceReads=0,targetReads=0,writes=0;
        for(Map.Entry<String,Integer> e:provider.reads.entrySet())if(e.getKey().endsWith(".jpg")){assertEquals(1,(int)e.getValue());if(e.getKey().startsWith(oldPrefix))sourceReads++;else targetReads++;}
        for(Map.Entry<String,Integer> e:provider.writes.entrySet())if(e.getKey().endsWith(".jpg"))writes+=e.getValue();
        assertEquals(1,provider.writes.entrySet().stream().filter(e->e.getKey().endsWith("/.nomedia")).mapToInt(Map.Entry::getValue).sum());
        assertEquals(4,sourceReads);assertEquals(4,targetReads);assertEquals(4,writes);
        assertFalse(new File(context.getCacheDir(),"chapter-delete").exists());
        assertTrue(progress.stream().anyMatch(t->t.contains("校验保留图片 4/4")));
        assertTrue(progress.stream().anyMatch(t->t.contains("清理原漫画")));
        assertUpdated(item,true);
    }
    @Test public void timestampChangeDuringCopyKeepsOriginalAndRemovesNewOutput()throws Exception {
        LibraryStore.Entry item=fixture(false,true);ChapterDeletion.Plan plan=ChapterDeletion.inspect(context,item,()->false);
        Set<String> before=new HashSet<>(Arrays.asList(root.getParentFile().list()));File changed=new File(root,"0001/00001.jpg");
        try{ChapterDeletion.delete(context,store,item,plan,Collections.singleton(2),()->false,t->{if(t.contains("核对原漫画"))assertTrue(changed.setLastModified(changed.lastModified()+10000));});fail();}catch(IOException expected){assertTrue(expected.getMessage().contains("变化"));}
        assertEquals(before,new HashSet<>(Arrays.asList(root.getParentFile().list())));assertEquals(item.uri,library.list("",false).get(0).uri);assertFalse(store.libraryBusy);
    }
    @Test public void targetReadbackCorruptionPreservesOriginal()throws Exception {
        LibraryStore.Entry item=fixture(false,true);provider.corruptReadback=true;
        try{delete(item,2);fail();}catch(IOException expected){assertTrue(expected.getMessage().contains("校验失败"));}
        assertTrue(root.exists());assertEquals(item.uri,library.list("",false).get(0).uri);
        assertEquals(1,root.getParentFile().list().length);assertFalse(store.libraryBusy);
    }
    @Test public void inspectionCancellationAndNullTimestampsAreSupported()throws Exception {
        LibraryStore.Entry item=fixture(false,true);AtomicBoolean stop=new AtomicBoolean();
        try{ChapterDeletion.inspect(context,item,stop::get,t->stop.set(true));fail();}catch(IOException expected){assertTrue(expected.getMessage().contains("取消"));}
        provider.nullTimestamps=true;delete(item,2);assertUpdated(item,true);
    }
    @Test public void legacyManifestUsesOneListingAndKeepsExtraFileProtection()throws Exception {
        LibraryStore.Entry item=fixture(false,true);JSONArray entries=new JSONArray();
        for(int c=1;c<=3;c++)for(int p=1;p<=2;p++)entries.put(new JSONObject().put("chapter",c).put("page",p).put("file",String.format(Locale.ROOT,"%04d/%05d.jpg",c,p)).put("size",3));
        Files.write(new File(root,AlbumRules.MANIFEST).toPath(),new JSONObject().put("version",1).put("id","123").put("title","test").put("entries",entries).toString().getBytes("UTF-8"));
        provider.children=0;assertEquals(6,ChapterDeletion.inspect(context,item,()->false).chapters.size());assertEquals(4,provider.children);
        Files.write(new File(root,"0002/personal.txt").toPath(),new byte[]{1});
        try{ChapterDeletion.inspect(context,item,()->false);fail();}catch(IOException expected){assertTrue(expected.getMessage().contains("额外"));}
        Files.delete(new File(root,"0002/personal.txt").toPath());delete(item,2);assertUpdated(item,true);
    }
    static byte[] read(InputStream in)throws IOException {try(InputStream input=in;ByteArrayOutputStream output=new ByteArrayOutputStream()){byte[] b=new byte[1024];int n;while((n=input.read(b))!=-1)output.write(b,0,n);return output.toByteArray();}}
    public static class Bridge extends ContentProvider {
        final TreeProvider documents;Bridge(TreeProvider value){documents=value;}
        public boolean onCreate(){return true;}
        public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order){return documents.query(uri,projection,new Bundle(),null);}
        public Bundle call(String method,String arg,Bundle extras){return documents.call(method,arg,extras);}
        public ParcelFileDescriptor openFile(Uri uri,String mode)throws FileNotFoundException{return documents.openFile(uri,mode);}
        public String getType(Uri uri){return "application/octet-stream";}
        public Uri insert(Uri uri,ContentValues values){throw new UnsupportedOperationException();}
        public int update(Uri uri,ContentValues values,String selection,String[] args){throw new UnsupportedOperationException();}
        public int delete(Uri uri,String selection,String[] args){throw new UnsupportedOperationException();}
    }
    public static class TreeProvider extends DocumentsProvider {
        final File base;int creates,renames,deletes,documents,children;boolean failRename,corruptReadback,nullTimestamps;String failDelete="";final Map<String,Integer> reads=new HashMap<>(),writes=new HashMap<>();
        TreeProvider(File value){base=value;}
        public boolean onCreate(){return true;}
        File file(String id)throws FileNotFoundException {try{File f=id.equals("root")?base:new File(base,id.substring(5));if(!f.getCanonicalPath().startsWith(base.getCanonicalPath()))throw new IOException();return f;}catch(Exception e){throw new FileNotFoundException();}}
        String id(File file){return "root/"+base.toPath().relativize(file.toPath()).toString().replace('\\','/');}
        void row(MatrixCursor cursor,String[] projection,File file){Object[] values=new Object[projection.length];for(int i=0;i<projection.length;i++){switch(projection[i]){case "document_id":values[i]=id(file);break;case "_display_name":values[i]=file.getName();break;case "mime_type":values[i]=file.isDirectory()?DocumentsContract.Document.MIME_TYPE_DIR:"application/octet-stream";break;case "_size":values[i]=file.length();break;case "last_modified":values[i]=nullTimestamps?null:file.lastModified();break;case "flags":values[i]=0;break;}}cursor.addRow(values);}
        public Cursor queryRoots(String[] projection){return new MatrixCursor(projection);}
        public Cursor queryDocument(String id,String[] projection)throws FileNotFoundException {documents++;MatrixCursor cursor=new MatrixCursor(projection);File f=file(id);if(f.exists())row(cursor,projection,f);return cursor;}
        public Cursor queryChildDocuments(String id,String[] projection,String sort)throws FileNotFoundException {children++;MatrixCursor cursor=new MatrixCursor(projection);File[] listed=file(id).listFiles();if(listed==null)throw new FileNotFoundException();for(File f:listed)row(cursor,projection,f);return cursor;}
        public ParcelFileDescriptor openDocument(String id,String mode,CancellationSignal signal)throws FileNotFoundException {
            Map<String,Integer> counts=mode.contains("w")?writes:reads;counts.put(id,counts.getOrDefault(id,0)+1);
            if(corruptReadback&&!mode.contains("w")&&id.contains(".partial/")&&id.endsWith(".jpg"))try{Files.write(file(id).toPath(),new byte[]{0,0,0});}catch(IOException error){throw new FileNotFoundException();}
            return ParcelFileDescriptor.open(file(id),ParcelFileDescriptor.parseMode(mode));
        }
        public String createDocument(String parent,String mime,String name)throws FileNotFoundException {creates++;File f=new File(file(parent),name);try{if(mime.equals(DocumentsContract.Document.MIME_TYPE_DIR)){if(!f.mkdir())throw new IOException();}else if(!f.createNewFile())throw new IOException();return id(f);}catch(IOException e){throw new FileNotFoundException();}}
        public String renameDocument(String id,String name)throws FileNotFoundException {renames++;if(failRename)throw new FileNotFoundException("重命名失败");File from=file(id),to=new File(from.getParentFile(),name);if(!from.renameTo(to))throw new FileNotFoundException();return id(to);}
        public void deleteDocument(String id)throws FileNotFoundException {deletes++;if(failDelete.equals(id))throw new FileNotFoundException("delete denied");try{Downloader.deleteOwned(file(id),base);}catch(Exception e){throw new FileNotFoundException(e.getMessage());}}
        public boolean isChildDocument(String parent,String document){return document.startsWith(parent+"/");}
    }
}
