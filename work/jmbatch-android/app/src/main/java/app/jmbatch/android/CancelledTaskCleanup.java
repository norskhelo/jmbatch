package app.jmbatch.android;

import android.net.Uri;
import android.database.Cursor;
import android.provider.DocumentsContract;
import java.io.*;
import java.nio.file.*;

/** Called only after the download and all child workers have exited. */
public final class CancelledTaskCleanup {
    public static CacheCleanup.Result run(Store store,Store.Task task)throws Exception {
        CacheCleanup.Result result=new CacheCleanup.Result();
        if(!task.discardRequested||task.status.equals("done"))throw new IOException("任务未取消");
        if(!task.key.matches("[0-9a-f-]{36}"))throw new IOException("任务标识无效");
        if(!task.cleanupUri.isEmpty()){
            Uri uri=Uri.parse(task.cleanupUri);
            File local=AlbumStorage.local(store.context,uri);
            if(local!=null){
                result.add(CacheCleanup.discard(local,AlbumStorage.root(store.context),r->{}));
                if(result.errors>0)return result;
            }else{
                // Only URIs returned by this task's create/rename operations are recorded.
                boolean exists;
                try(Cursor cursor=store.context.getContentResolver().query(uri,new String[]{"document_id"},null,null,null)){
                    if(cursor==null)throw new IOException("无法确认待删除文件，请恢复目录授权后重试取消");
                    exists=cursor.moveToFirst();
                }
                if(exists&&!DocumentsContract.deleteDocument(store.context.getContentResolver(),uri))
                    throw new IOException("无法删除任务输出，请恢复目录授权后重试取消");
            }
            AlbumStorage.forget(store.context,uri);
            task.cleanupUri="";store.save();
        }
        File owner=new File(store.context.getFilesDir(),"work"),cache=new File(owner,task.key);
        result.add(CacheCleanup.discard(cache,owner,r->task.phase="取消任务 · "+r.message(true)));
        return result;
    }
    private CancelledTaskCleanup(){}
}
