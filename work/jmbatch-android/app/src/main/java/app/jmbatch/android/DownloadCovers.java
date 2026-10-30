package app.jmbatch.android;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Rect;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.LruCache;
import android.view.View;
import android.widget.ImageView;
import android.widget.TextView;
import java.io.File;
import java.io.ByteArrayOutputStream;
import java.util.concurrent.*;

/** One bounded worker; visible rows refresh while downloads atomically commit pages. */
public final class DownloadCovers {
    private final Context context;
    private final CoverDiskCache disk;
    private int startupReads;
    private final Handler main=new Handler(Looper.getMainLooper());
    private final ThreadPoolExecutor worker=new ThreadPoolExecutor(1,1,0L,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(24));
    private final LruCache<String,Cover> cache=new LruCache<String,Cover>(8*1024*1024){
        protected int sizeOf(String key,Cover value){return value.bitmap==null?1024:value.bitmap.getByteCount();}
    };
    private volatile boolean closed;
    private static final class Cover {
        final Bitmap bitmap;final long checked=SystemClock.elapsedRealtime();
        String savedFor;
        Cover(Bitmap bitmap){this.bitmap=bitmap;}
    }
    public static final class Target {
        final ImageView image;final TextView placeholder;long next;boolean pending,removed;
        String identity="",stamp;Bitmap displayed;long generation;
        public Target(ImageView image,TextView placeholder){this.image=image;this.placeholder=placeholder;}
        private void show(Bitmap bitmap){
            if(displayed==bitmap)return;
            displayed=bitmap;
            if(bitmap==null)image.setImageDrawable(null);else image.setImageBitmap(bitmap);
            image.setContentDescription(bitmap==null?"等待第一页封面":"首章第一页封面");
            placeholder.setVisibility(bitmap==null?View.VISIBLE:View.GONE);
        }
        public void clear(){show(null);}
        private void clearIfScrolledAway(){
            if(image.getWidth()>0&&image.getHeight()>0&&image.isShown()&&image.getWindowVisibility()==View.VISIBLE)clear();
        }
        public void remove(){removed=true;generation++;stamp=null;clear();}
    }
    public DownloadCovers(Context context){this.context=context.getApplicationContext();disk=new CoverDiskCache(new File(this.context.getFilesDir(),"covers"));}
    private Bitmap restore(String identity,String status,String result,String format){
        try{
            CoverDiskCache.Snapshot saved=disk.peek("download\n"+identity);
            if(saved==null&&"done".equals(status)&&result!=null&&!result.isEmpty())saved=disk.peek(format+"\n"+result);
            if(saved==null)return null;
            BitmapFactory.Options options=new BitmapFactory.Options();options.inJustDecodeBounds=true;
            BitmapFactory.decodeByteArray(saved.image,0,saved.image.length,options);
            if(options.outWidth<=0||options.outHeight<=0||options.outWidth>192||options.outHeight>256)return null;
            return BitmapFactory.decodeByteArray(saved.image,0,saved.image.length);
        }catch(Exception|OutOfMemoryError ignored){return null;}
    }
    public void bind(Store.Task task,Target target){
        if(closed||target.removed)return;
        final String key=task.key,status=task.status,result=task.resultUri,format=task.settings.format;
        final int firstChapter=task.selectedChapters.isEmpty()?1:task.selectedChapters.get(0).number;
        String identity=key+"|"+firstChapter+"|"+format+"|"+task.settings.outputUri;
        if(!identity.equals(target.identity)){
            target.identity=identity;target.generation++;target.pending=false;target.next=0;target.stamp=null;target.clear();
            // The first screenful can be painted from private thumbnails before
            // layout. Never query external storage or decode a comic on this thread.
            if(startupReads++<12)target.show(restore(identity,status,result,format));
        }
        if(!target.image.getGlobalVisibleRect(new Rect())){
            // A not-yet-laid-out or background window is not a scrolled-away row.
            target.clearIfScrolledAway();
            return;
        }
        // Restore synchronously before the polling/pending gate. Off-screen rows
        // release their bitmap references, but scrolling back must not flash blank.
        Cover retained=target.stamp==null?null:cache.get(target.stamp);
        if(retained!=null&&retained.bitmap!=null)target.show(retained.bitmap);
        long now=SystemClock.elapsedRealtime();
        if(target.pending||now<target.next)return;
        final long generation=target.generation;
        target.pending=true;target.next=now+1000;
        try{worker.execute(()->{
            Bitmap bitmap=null;String stamp=null;
            try{
                DownloadCoverRules.Source source=DownloadCoverRules.resolve(new File(context.getFilesDir(),"work"),key,status,result,format,firstChapter);
                if(source!=null){
                    stamp=source.stamp;
                    Cover found=cache.get(source.stamp);
                    if(found==null||(found.bitmap==null&&SystemClock.elapsedRealtime()-found.checked>=3000)){
                        Bitmap loaded=source.format.equals("image")?LibraryCover.loadImage(new File(source.path)):
                            LibraryCover.load(context,new LibraryStore.Entry("","",source.path,"","",source.format,false));
                        found=new Cover(loaded);cache.put(source.stamp,found);
                    }
                    bitmap=found.bitmap;
                    if(bitmap!=null&&!identity.equals(found.savedFor)){
                        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
                        if(bitmap.compress(Bitmap.CompressFormat.PNG,100,bytes))
                            disk.remember("download\n"+identity,source.stamp,bytes.toByteArray());
                        found.savedFor=identity;
                    }
                }
            }catch(Exception|OutOfMemoryError ignored){ /* Preview failure must not stop the queue. */ }
            final Bitmap ready=bitmap;final String readyStamp=stamp;
            main.post(()->{
                if(closed||target.removed||target.generation!=generation)return;
                target.pending=false;
                // Keep the last valid preview through export/cache cleanup or a
                // transient read failure; replace it only when a new image is ready.
                if(ready!=null)target.stamp=readyStamp;
                if(!target.image.getGlobalVisibleRect(new Rect())){target.clearIfScrolledAway();return;}
                if(ready!=null)target.show(ready);
            });
        });}catch(RejectedExecutionException ignored){target.pending=false;target.next=now;}
    }
    public void close(){closed=true;worker.shutdownNow();main.removeCallbacksAndMessages(null);cache.evictAll();}
}
