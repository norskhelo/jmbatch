package app.jmbatch.android;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Rect;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.LruCache;
import android.view.View;
import android.widget.ImageView;
import android.widget.TextView;
import java.io.File;
import java.util.concurrent.*;

/** One bounded worker; visible rows refresh while downloads atomically commit pages. */
public final class DownloadCovers {
    private final Context context;
    private final Handler main=new Handler(Looper.getMainLooper());
    private final ThreadPoolExecutor worker=new ThreadPoolExecutor(1,1,0L,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(24));
    private final LruCache<String,Cover> cache=new LruCache<String,Cover>(8*1024*1024){
        protected int sizeOf(String key,Cover value){return value.bitmap==null?1024:value.bitmap.getByteCount();}
    };
    private volatile boolean closed;
    private static final class Cover {
        final Bitmap bitmap;final long checked=SystemClock.elapsedRealtime();
        Cover(Bitmap bitmap){this.bitmap=bitmap;}
    }
    public static final class Target {
        final ImageView image;final TextView placeholder;long next;boolean pending,removed;
        public Target(ImageView image,TextView placeholder){this.image=image;this.placeholder=placeholder;}
        public void clear(){image.setImageDrawable(null);image.setContentDescription("等待第一页封面");placeholder.setVisibility(View.VISIBLE);}
        public void remove(){removed=true;clear();}
    }
    public DownloadCovers(Context context){this.context=context.getApplicationContext();}
    public void bind(Store.Task task,Target target){
        if(closed||target.removed)return;
        if(!target.image.getGlobalVisibleRect(new Rect())){target.clear();return;}
        long now=SystemClock.elapsedRealtime();
        if(target.pending||now<target.next)return;
        final String key=task.key,status=task.status,result=task.resultUri,format=task.settings.format;
        target.pending=true;target.next=now+1000;
        try{worker.execute(()->{
            Bitmap bitmap=null;
            try{
                DownloadCoverRules.Source source=DownloadCoverRules.resolve(new File(context.getFilesDir(),"work"),key,status,result,format);
                if(source!=null){
                    Cover found=cache.get(source.stamp);
                    if(found==null||(found.bitmap==null&&SystemClock.elapsedRealtime()-found.checked>=3000)){
                        Bitmap loaded=source.format.equals("image")?LibraryCover.loadImage(new File(source.path)):
                            LibraryCover.load(context,new LibraryStore.Entry("","",source.path,"","",source.format,false));
                        found=new Cover(loaded);cache.put(source.stamp,found);
                    }
                    bitmap=found.bitmap;
                }
            }catch(Exception|OutOfMemoryError ignored){ /* Preview failure must not stop the queue. */ }
            final Bitmap ready=bitmap;
            main.post(()->{
                target.pending=false;
                if(closed||target.removed)return;
                if(!target.image.getGlobalVisibleRect(new Rect())){target.clear();return;}
                target.image.setImageBitmap(ready);
                target.image.setContentDescription(ready==null?"等待第一页封面":"首章第一页封面");
                target.placeholder.setVisibility(ready==null?View.VISIBLE:View.GONE);
            });
        });}catch(RejectedExecutionException ignored){target.pending=false;target.next=now;}
    }
    public void close(){closed=true;worker.shutdownNow();main.removeCallbacksAndMessages(null);cache.evictAll();}
}
