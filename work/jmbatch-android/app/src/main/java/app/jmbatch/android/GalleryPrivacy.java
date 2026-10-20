package app.jmbatch.android;

import android.content.Context;
import android.database.Cursor;
import android.media.MediaScannerConnection;
import android.net.Uri;
import android.provider.DocumentsContract;
import java.io.*;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Media-scanner exclusion is scoped to comic folders, never a shared destination root. */
public final class GalleryPrivacy {
    private static final AtomicBoolean running=new AtomicBoolean();
    private static final String ALBUM="JM[0-9]{1,10}-.+-[0-9a-f]{8}";

    public static synchronized boolean protect(Context context,Uri folder)throws IOException {
        File local=AlbumStorage.local(context,folder);
        if(local!=null){
            boolean created=FolderSave.ensureNoMedia(local);
            if(created)try{MediaScannerConnection.scanFile(context,new String[]{local.getAbsolutePath()},null,null);}catch(RuntimeException ignored){}
            return created;
        }
        for(AlbumStorage.Node node:AlbumStorage.children(context,folder)){
            if(!node.name.equals(FolderSave.NO_MEDIA))continue;
            if(node.directory)throw new IOException("无法设置相册隐藏：标记不是文件");
            return false;
        }
        Uri marker=DocumentsContract.createDocument(context.getContentResolver(),folder,"application/octet-stream",FolderSave.NO_MEDIA);
        if(marker==null)throw new IOException("所选目录无法设置相册隐藏，请更换保存目录");
        // Providers can silently append an extension. Only the exact name has Android semantics.
        try(Cursor cursor=context.getContentResolver().query(marker,new String[]{"_display_name","mime_type"},null,null,null)){
            if(cursor==null||!cursor.moveToFirst()||!FolderSave.NO_MEDIA.equals(cursor.getString(0))||
                    DocumentsContract.Document.MIME_TYPE_DIR.equals(cursor.getString(1)))
                throw new IOException("存储服务不支持相册隐藏标记，请更换保存目录");
        }
        try(OutputStream out=context.getContentResolver().openOutputStream(marker,"w")){
            if(out==null)throw new IOException("无法写入相册隐藏标记");
            out.flush();
        }
        return true;
    }

    public static void start(Context context,Store store){
        if(!running.compareAndSet(false,true))return;
        Context application=context.getApplicationContext();
        new Thread(()->{
            try{store.galleryNotice=migrate(application,store);}
            catch(Exception error){store.galleryNotice="旧下载的相册隐藏设置未完成，下次打开应用会重试。";}
            finally{running.set(false);}
        },"gallery-privacy").start();
    }

    /** Also retry inaccessible folders on later launches, without changing files or library records. */
    static String migrate(Context context,Store store)throws IOException {
        Set<String> folders=new LinkedHashSet<>(),trees=new LinkedHashSet<>();
        trees.add(store.settings.outputUri);
        for(Store.Task task:store.snapshot()){
            trees.add(task.settings.outputUri);
            if(task.settings.format.equals("images")&&!task.resultUri.isEmpty())folders.add(task.resultUri);
        }
        for(LibraryStore.Entry item:LibraryStore.get(context).list("",false)){
            trees.add(item.tree);
            if(item.format.equals("images"))folders.add(item.uri);
        }
        int failed=0;
        File[] local=AlbumStorage.root(context).listFiles();
        if(local!=null)for(File file:local)
            if(file.getName().matches(ALBUM)&&file.isDirectory()&&!Files.isSymbolicLink(file.toPath()))
                folders.add(ExportProvider.uri(context,file).toString());
        for(String tree:trees){
            if(tree.isEmpty())continue;
            try{
                Uri uri=Uri.parse(tree),root=DocumentsContract.buildDocumentUriUsingTree(uri,DocumentsContract.getTreeDocumentId(uri));
                for(AlbumStorage.Node child:AlbumStorage.children(context,root))
                    if(child.directory&&child.name.matches(ALBUM))folders.add(child.uri.toString());
            }catch(Exception error){failed++;}
        }
        for(String folder:folders)try{protect(context,Uri.parse(folder));}catch(Exception error){failed++;}
        return failed==0?"":"部分旧下载未能设置相册隐藏，请确认文件仍在并重新授权保存目录；下次打开应用会重试。";
    }
}
