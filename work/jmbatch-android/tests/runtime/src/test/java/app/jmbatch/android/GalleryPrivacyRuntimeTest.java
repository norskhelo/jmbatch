package app.jmbatch.android;

import android.content.*;
import android.content.pm.ProviderInfo;
import android.net.Uri;
import android.provider.DocumentsContract;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.*;
import org.robolectric.shadows.ShadowContentResolver;
import java.io.*;
import java.lang.reflect.Field;
import java.nio.file.*;
import java.util.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35})
@LooperMode(LooperMode.Mode.PAUSED)
public class GalleryPrivacyRuntimeTest {
    Context context;Store store;File base;GuardProvider provider;
    String tree="content://gallery.test/tree/root";
    static final byte[] IMAGE={1,2,3,4};
    static final FolderSave.Progress QUIET=(p,d,t,b,z)->{};
    @Before public void setup()throws Exception {
        context=RuntimeEnvironment.getApplication();
        for(Class<?> type:new Class<?>[]{Store.class,LibraryStore.class}){
            Field f=type.getDeclaredField("instance");f.setAccessible(true);f.set(null,null);
        }
        for(String name:new String[]{"queue.json","library.json"})Files.deleteIfExists(new File(context.getFilesDir(),name).toPath());
        store=Store.get(context);
        base=new File(context.getCacheDir(),"shared-"+UUID.randomUUID());assertTrue(base.mkdirs());
        provider=new GuardProvider(base);
        ProviderInfo info=new ProviderInfo();info.authority="gallery.test";info.exported=true;info.grantUriPermissions=true;
        info.readPermission=info.writePermission="android.permission.MANAGE_DOCUMENTS";
        provider.attachInfo(context,info);
        ChapterDeletionRuntimeTest.Bridge bridge=new ChapterDeletionRuntimeTest.Bridge(provider);bridge.attachInfo(context,info);
        ShadowContentResolver.registerProviderInternal(info.authority,bridge);
    }
    static class GuardProvider extends ChapterDeletionRuntimeTest.TreeProvider {
        boolean rejectMarker,renameMarker;int imageCreates,markerCreates;
        GuardProvider(File value){super(value);}
        @Override public String createDocument(String parent,String mime,String name)throws FileNotFoundException {
            if(name.equals(FolderSave.NO_MEDIA)){
                if(rejectMarker)throw new FileNotFoundException("marker denied");
                markerCreates++;if(renameMarker)name+=".bin";
            }
            if(name.endsWith(".jpg")){
                File folder=file(parent);boolean hidden=false;
                while(folder!=null&&!folder.equals(base)){
                    hidden|=new File(folder,FolderSave.NO_MEDIA).isFile();folder=folder.getParentFile();
                }
                assertTrue("marker must exist before the first image is created",hidden);imageCreates++;
            }
            return super.createDocument(parent,mime,name);
        }
    }
    List<FolderSave.Entry> pages(boolean chapters)throws Exception {
        List<FolderSave.Entry> result=new ArrayList<>();
        result.add(new FolderSave.Entry(()->new ByteArrayInputStream(IMAGE),chapters?"0001/00001.jpg":"00001.jpg",4));
        if(chapters)result.add(new FolderSave.Entry(()->new ByteArrayInputStream(IMAGE),"0002/00001.jpg",4));
        return result;
    }
    File path(Uri uri)throws Exception {
        File local=AlbumStorage.local(context,uri);
        return local!=null?local:provider.file(DocumentsContract.getDocumentId(uri));
    }
    Uri save(boolean saf,boolean chapters)throws Exception {
        return AlbumStorage.publishImages(context,pages(chapters),saf?tree:"","JM123-test-"+UUID.randomUUID().toString().substring(0,8),()->{},QUIET);
    }
    @Test public void localFlatAndMultiChapterAreHiddenBeforeCopyAndRemainReadable()throws Exception {
        for(boolean chapters:new boolean[]{false,true}){
            final File[] stage={null};
            FolderSave.Entry entry=new FolderSave.Entry(()->{
                assertTrue(new File(stage[0],FolderSave.NO_MEDIA).isFile());
                return new ByteArrayInputStream(IMAGE);
            },chapters?"0001/00001.jpg":"00001.jpg",4);
            List<FolderSave.Entry> entries=new ArrayList<>();entries.add(entry);
            if(chapters)entries.add(new FolderSave.Entry(()->new ByteArrayInputStream(IMAGE),"0002/00001.jpg",4));
            Uri uri=AlbumStorage.publishImages(context,entries,"","JM123-local-"+UUID.randomUUID().toString().substring(0,8),
                ()->{},QUIET,u->{if(u!=null)stage[0]=AlbumStorage.local(context,u);});
            assertTrue(new File(path(uri),FolderSave.NO_MEDIA).isFile());
            assertEquals(chapters?2:1,AlbumStorage.load(context,uri).images.size());
            AlbumStorage.validateForDeletion(context,uri);
            assertArrayEquals(IMAGE,Files.readAllBytes(path(AlbumStorage.load(context,uri).images.get(0).uri).toPath()));
        }
    }
    @Test public void safFlatAndMultiChapterHideOnlyComicFolders()throws Exception {
        Files.write(new File(base,"personal.jpg").toPath(),IMAGE);
        for(boolean chapters:new boolean[]{false,true}){
            Uri uri=save(true,chapters);
            assertTrue(new File(path(uri),FolderSave.NO_MEDIA).isFile());
            assertEquals(chapters?2:1,AlbumStorage.load(context,uri).images.size());
            AlbumStorage.validateForDeletion(context,uri);
        }
        assertEquals(3,provider.imageCreates);assertFalse(new File(base,FolderSave.NO_MEDIA).exists());
        assertArrayEquals(IMAGE,Files.readAllBytes(new File(base,"personal.jpg").toPath()));
    }
    @Test public void rejectedOrRenamedSafMarkerStopsImagesAndCleansOwnedOutput()throws Exception {
        for(boolean renamed:new boolean[]{false,true}){
            provider.rejectMarker=!renamed;provider.renameMarker=renamed;
            try{save(true,false);fail("must not expose images");}catch(IOException expected){}
            assertEquals(0,provider.imageCreates);assertEquals(0,base.list().length);
        }
    }
    @Test public void markerIsIdempotentAndExistingContentsArePreserved()throws Exception {
        Uri uri=save(true,false);File marker=new File(path(uri),FolderSave.NO_MEDIA);
        Files.write(marker.toPath(),new byte[]{9,8});
        assertFalse(GalleryPrivacy.protect(context,uri));assertFalse(GalleryPrivacy.protect(context,uri));
        assertArrayEquals(new byte[]{9,8},Files.readAllBytes(marker.toPath()));assertEquals(1,provider.markerCreates);
        Uri local=save(false,false);assertFalse(GalleryPrivacy.protect(context,local));
    }
    @Test public void directoryNamedNomediaIsRejectedWithoutReplacingIt()throws Exception {
        File album=new File(base,"JM123-old-abcd1234");assertTrue(album.mkdir());
        File marker=new File(album,FolderSave.NO_MEDIA);assertTrue(marker.mkdir());
        Uri uri=DocumentsContract.buildDocumentUriUsingTree(Uri.parse(tree),provider.id(album));
        try{GalleryPrivacy.protect(context,uri);fail();}catch(IOException expected){}
        try{FolderSave.ensureNoMedia(album);fail();}catch(IOException expected){}
        assertTrue(marker.isDirectory());assertEquals(0,provider.markerCreates);
    }
    @Test public void migrationFindsOldDownloadsAndLeavesSharedRootAndPhotosAlone()throws Exception {
        File old=new File(base,"JM123-old-abcd1234");assertTrue(old.mkdir());
        Files.write(new File(old,"00001.jpg").toPath(),IMAGE);
        File other=new File(base,"Camera");assertTrue(other.mkdir());Files.write(new File(other,"photo.jpg").toPath(),IMAGE);
        File local=new File(AlbumStorage.root(context),"JM456-old-1234abcd");assertTrue(local.mkdirs());Files.write(new File(local,"00001.jpg").toPath(),IMAGE);
        store.settings.outputUri=tree;
        assertEquals("",GalleryPrivacy.migrate(context,store));
        assertTrue(new File(old,FolderSave.NO_MEDIA).isFile());assertTrue(new File(local,FolderSave.NO_MEDIA).isFile());
        assertFalse(new File(base,FolderSave.NO_MEDIA).exists());assertFalse(new File(other,FolderSave.NO_MEDIA).exists());
        assertEquals("",GalleryPrivacy.migrate(context,store));assertEquals(1,provider.markerCreates);
        assertArrayEquals(IMAGE,Files.readAllBytes(new File(old,"00001.jpg").toPath()));
        assertTrue(store.snapshot().isEmpty());
    }
    @Test public void migrationUsesLibraryAndTaskHistoryAndRetriesFailures()throws Exception {
        File old=new File(base,"renamed-comic");assertTrue(old.mkdir());Files.write(new File(old,"00001.jpg").toPath(),IMAGE);
        Uri uri=DocumentsContract.buildDocumentUriUsingTree(Uri.parse(tree),provider.id(old));
        LibraryStore.Entry item=new LibraryStore.Entry("123","old",uri.toString(),tree,"saved","images",true);
        LibraryStore.get(context).importFound(Collections.singletonList(item));
        Store.Task task=new Store.Task("123",new Store.Settings());task.settings.outputUri=tree;task.resultUri=uri.toString();task.status="done";store.tasks.add(task);
        provider.rejectMarker=true;assertFalse(GalleryPrivacy.migrate(context,store).isEmpty());
        provider.rejectMarker=false;assertEquals("",GalleryPrivacy.migrate(context,store));
        assertTrue(new File(old,FolderSave.NO_MEDIA).isFile());assertEquals(1,provider.markerCreates);
        assertEquals(uri.toString(),LibraryStore.get(context).list("",false).get(0).uri);assertEquals("done",task.status);
    }
    @Test public void folderExportPreservesMarkerButZipAndPdfRemainOrdinaryFiles()throws Exception {
        File source=new File(context.getCacheDir(),"source-"+UUID.randomUUID());assertTrue(source.mkdir());
        Files.write(new File(source,"00001.jpg").toPath(),IMAGE);FolderSave.ensureNoMedia(source);
        for(String destination:new String[]{"",tree}){
            Uri result=AlbumStorage.publish(context,source,destination,"JM123-export-"+UUID.randomUUID().toString().substring(0,8),()->{});
            assertTrue(new File(path(result),FolderSave.NO_MEDIA).isFile());assertEquals(1,AlbumStorage.load(context,result).images.size());
            AlbumStorage.validateForDeletion(context,result);
            for(String extension:new String[]{".zip",".pdf"}){
                File archive=new File(context.getCacheDir(),"export"+extension);Files.write(archive.toPath(),IMAGE);
                Uri published=AlbumStorage.publish(context,archive,destination,"export-"+UUID.randomUUID()+extension,()->{});
                assertArrayEquals(IMAGE,Files.readAllBytes(path(published).toPath()));
            }
        }
    }
    @Test public void unrelatedFilesStillPreventDeletionAndCancelCleansMarker()throws Exception {
        Uri uri=save(false,false);File foreign=new File(path(uri),"personal.txt");Files.write(foreign.toPath(),IMAGE);
        try{AlbumStorage.validateForDeletion(context,uri);fail();}catch(IOException expected){assertTrue(expected.getMessage().contains("额外"));}
        Set<String> before=new HashSet<>(Arrays.asList(base.list()));
        try{AlbumStorage.publishImages(context,pages(false),tree,"JM123-cancel-abcd1234",()->{},
            (p,d,t,b,z)->{if(p.equals("save"))throw new IOException("cancel");});fail();}catch(IOException expected){}
        assertEquals(before,new HashSet<>(Arrays.asList(base.list())));assertTrue(foreign.isFile());
    }
}
