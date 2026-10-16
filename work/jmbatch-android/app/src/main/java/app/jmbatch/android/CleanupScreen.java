package app.jmbatch.android;

import android.app.*;
import android.database.Cursor;
import android.net.Uri;
import java.io.*;
import java.util.*;

public final class CleanupScreen {
    private static boolean resultExists(Activity activity,Store.Task task){
        if(!task.status.equals("done")||task.resultUri.isEmpty())return false;
        try{
            Uri uri=Uri.parse(task.resultUri);File local=AlbumStorage.local(activity,uri);
            if(local!=null)return local.exists();
            try(Cursor c=activity.getContentResolver().query(uri,new String[]{"_display_name"},null,null,null)){
                return c!=null&&c.moveToFirst();
            }
        }catch(Exception error){return false;}
    }
    public static void show(Activity activity,Store store,Store.Task selected){
        final List<Store.Task> tasks;
        synchronized(store){
            if(store.running||store.libraryBusy||!store.activeKeys.isEmpty()){
                new AlertDialog.Builder(activity).setTitle("清理下载缓存").setMessage("请先暂停全部下载，等待请求及文件操作结束。").setPositiveButton("知道了",null).show();return;
            }
            store.libraryBusy=true;tasks=selected==null?store.snapshot():Collections.singletonList(selected);
        }
        AlertDialog dialog=new AlertDialog.Builder(activity).setTitle("清理下载缓存")
            .setMessage("正在清理…\n保留成品、完成标记、未完成任务的完整图片和章节缓存。")
            .setCancelable(false).setPositiveButton("关闭",null).create();
        dialog.show();dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
        new Thread(()->{
            CacheCleanup.Result total=new CacheCleanup.Result();String message;
            try{
                File owner=new File(store.context.getFilesDir(),"work");
                for(Store.Task task:tasks){
                    if(!task.key.matches("[0-9a-f-]{36}")){total.errors++;continue;}
                    CacheCleanup.Result one=CacheCleanup.clean(new File(owner,task.key),owner,resultExists(activity,task),task.settings.keepImages,r->{
                        CacheCleanup.Result current=new CacheCleanup.Result();current.add(total);current.add(r);
                        String text=current.message(false);activity.runOnUiThread(()->{if(!activity.isDestroyed())dialog.setMessage(text+"\n保留成品和续传所需缓存。");});
                    });
                    total.add(one);
                }
                message=total.message(false);
            }catch(Exception error){message=total.message(false)+"；部分清理未完成："+error.getMessage();}
            store.cleanupNotice=message;
            try{store.save();}catch(IOException error){store.note="清理结果未能保存："+error.getMessage();}
            finally{store.libraryBusy=false;}
            String text=message;activity.runOnUiThread(()->{
                if(activity.isFinishing()||activity.isDestroyed())return;
                dialog.setMessage(text+"\n成品、完成标记及续传所需完整图片和章节缓存已保留。");
                dialog.setCancelable(true);dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(true);
            });
        },"jm-cache-cleanup").start();
    }
    private CleanupScreen(){}
}
