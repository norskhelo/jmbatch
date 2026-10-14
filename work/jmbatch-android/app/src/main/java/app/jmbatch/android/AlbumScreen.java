package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.net.Uri;
import java.util.*;

public final class AlbumScreen {
    public static void show(Activity activity,Store store,LibraryStore.Entry entry){
        ProgressDialog loading=ProgressDialog.show(activity,"图片漫画","正在读取章节…",true,false);
        new Thread(()->{
            try{
                AlbumStorage.Album album=AlbumStorage.load(activity,Uri.parse(entry.uri));
                String[] names=new String[album.images.size()];for(int i=0;i<names.length;i++){AlbumStorage.Image image=album.images.get(i);names[i]=String.format(Locale.ROOT,"第 %04d 章 / 第 %05d 页",image.chapter,image.page);}
                activity.runOnUiThread(()->{loading.dismiss();if(activity.isFinishing()||activity.isDestroyed())return;
                    new AlertDialog.Builder(activity).setTitle("JM"+album.id+" · "+album.title).setItems(names,(d,index)->{
                        Uri uri=album.images.get(index).uri;Intent open=new Intent(Intent.ACTION_VIEW).setDataAndType(uri,"image/jpeg").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);open.setClipData(ClipData.newRawUri("图片",uri));
                        try{activity.startActivity(Intent.createChooser(open,"打开图片"));}catch(Exception e){new AlertDialog.Builder(activity).setMessage("没有可打开图片的应用，或目录权限已失效").setPositiveButton("关闭",null).show();}
                    }).setPositiveButton("导出 PDF / ZIP",(d,w)->new ExportScreen(activity,store,entry).show()).setNegativeButton("关闭",null).show();
                });
            }catch(Exception error){activity.runOnUiThread(()->{loading.dismiss();if(!activity.isFinishing())new AlertDialog.Builder(activity).setMessage("无法打开图片："+error.getMessage()).setPositiveButton("关闭",null).show();});}
        },"album-list").start();
    }
}
