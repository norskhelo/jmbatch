package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.os.*;
import java.util.*;
import java.util.concurrent.*;

public final class DownloadService extends Service {
    public static final String START="start", SELECTED="selected", PAUSE="pause", PAUSE_ONE="pause_one", CANCEL="cancel", CLEANUP="cleanup";
    private final DownloadRate rate=new DownloadRate(()->Store.get(this).settings.downloadLimitKB);
    private static final String CHANNEL="downloads";
    private Store store;
    private final DownloadPool<String,DownloadJob> pool=new DownloadPool<>();
    private final Set<String> cleaningKeys=ConcurrentHashMap.newKeySet();
    private ScheduledExecutorService monitor;
    private PowerManager.WakeLock wake;
    private final Handler main=new Handler(Looper.getMainLooper());
    private boolean accepting, foreground, destroyed, startedDownloads;
    private long lastSave;
    private final Runnable dispatch=new Runnable(){public void run(){
        if(destroyed)return;
        try{dispatch();}catch(Throwable error){
            store.note="队列异常："+Core.error(error,store.cookie);
            accepting=false;pool.cancelAll("PAUSE");
            try{store.pauseQueued();}catch(Exception ignored){}
        }
        if(accepting||pool.size()>0||!cleaningKeys.isEmpty()||hasPendingCleanup())main.postDelayed(this,250);else finishQueue();
    }};

    public void onCreate(){
        super.onCreate();store=Store.get(this);
        NotificationChannel channel=new NotificationChannel(CHANNEL,"下载进度",NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("显示同时进行的下载，可随时暂停全部任务");channel.setShowBadge(false);
        getSystemService(NotificationManager.class).createNotificationChannel(channel);
        wake=((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,getPackageName()+":download");
        monitor=Executors.newSingleThreadScheduledExecutor();
        monitor.scheduleAtFixedRate(()->{try{monitor();}catch(Exception error){store.note="进度监控异常："+Core.error(error,store.cookie);}},1,1,TimeUnit.SECONDS);
    }

    public int onStartCommand(Intent intent,int flags,int startId){
        String action=intent==null?PAUSE:intent.getAction();
        if(PAUSE_ONE.equals(action)){String key=intent.getStringExtra("key");DownloadJob job=pool.get(key);if(job!=null)job.cancel("PAUSE");return START_NOT_STICKY;}
        if(PAUSE.equals(action)){
            accepting=false;pool.cancelAll("PAUSE");
            try{store.pauseQueued();}catch(Exception error){store.note=error.getMessage();}
            if(pool.size()==0&&cleaningKeys.isEmpty())finishQueue();
            return START_NOT_STICKY;
        }
        if(CLEANUP.equals(action)){
            if(!foreground){startForeground(1,notification());foreground=true;}
            main.removeCallbacks(dispatch);main.post(dispatch);return START_NOT_STICKY;
        }
        if(CANCEL.equals(action)){
            String key=intent.getStringExtra("key");DownloadJob job=pool.get(key);
            synchronized(store){
                Store.Task target=null;for(Store.Task task:store.snapshot())if(task.key.equals(key))target=task;
                if(target==null||target.status.equals("done"))return START_NOT_STICKY;
                if(store.fileBlocked(target)){store.note="该漫画正在进行文件操作，请稍后取消";return START_NOT_STICKY;}
                boolean wasRequested=target.discardRequested;String previousStatus=target.status,previousPhase=target.phase;
                target.discardRequested=true;target.status="cancelling";target.phase="正在取消并删除任务文件…";target.speed=0;target.error="";
                try{store.save();}catch(Exception error){target.discardRequested=wasRequested;target.status=previousStatus;target.phase=previousPhase;store.note="无法保存取消状态，未开始删除："+error.getMessage();return START_NOT_STICKY;}
            }
            if(job!=null)job.cancel("CANCEL");
            if(!foreground){startForeground(1,notification());foreground=true;}
            main.removeCallbacks(dispatch);main.post(dispatch);return START_NOT_STICKY;
        }
        if(accepting||pool.size()>0){store.note=accepting?"队列已在运行":"正在停止旧请求，请稍后继续";return START_NOT_STICKY;}
        startForeground(1,notification());foreground=true;
        synchronized(store){
            if(store.globalFileOperation()||!store.activeKeys.isEmpty()){store.note="正在管理文件或关闭旧请求，请稍后再开始下载";stopForeground(true);foreground=false;stopSelf();return START_NOT_STICKY;}
            store.running=true;
        }
        try{if(!SELECTED.equals(action))store.resume();}catch(Exception error){store.note=error.getMessage();finishQueue();return START_NOT_STICKY;}
        store.note="";accepting=true;startedDownloads=true;
        wake.acquire(6*60*60*1000L);
        main.removeCallbacks(dispatch);main.post(dispatch);return START_NOT_STICKY;
    }

    private void dispatch(){
        for(String key:pool.reap())store.activeKeys.remove(key);
        cleanCancelled();
        if(!accepting)return;
        synchronized(store){
            while(pool.size()<store.settings.concurrentTasks){
                Store.Task task=store.next();if(task==null)break;
                task.status="running";task.error="";task.phase="正在启动下载";
                store.activeKeys.add(task.key);
                try{
                    if(!pool.start(task.key,new DownloadJob(task),store.settings.concurrentTasks))throw new IllegalStateException("任务已在运行");
                }catch(Throwable error){
                    store.activeKeys.remove(task.key);task.status="failed";task.phase="无法启动下载";task.error=Core.error(error,store.cookie);
                }
            }
            if(pool.size()==0&&!store.hasQueuedTasks())accepting=false;
        }
    }

    private boolean hasPendingCleanup(){
        for(Store.Task task:store.snapshot())if(task.discardRequested&&task.status.equals("cancelling"))return true;
        return false;
    }
    private void cleanCancelled(){
        synchronized(store){
            if(store.globalFileOperation())return;
            for(Store.Task task:store.snapshot()){
                if(cleaningKeys.size()>=2)break;
                if(store.fileBlocked(task)||!task.discardRequested||!task.status.equals("cancelling")||store.activeKeys.contains(task.key)||!cleaningKeys.add(task.key))continue;
                store.activeKeys.add(task.key);store.running=true;
                new Thread(()->{
                    CacheCleanup.Result result;
                    try{result=CancelledTaskCleanup.run(store,task);}
                    catch(Exception error){result=new CacheCleanup.Result();result.errors=1;task.error=Core.error(error,store.cookie);}
                    synchronized(store){
                        if(result.errors==0){store.tasks.remove(task);store.cleanupNotice="JM"+task.id+" 文件和任务记录已删除；"+result.message(true);}
                        else{task.status="cancel_failed";task.phase="文件清理失败，再次删除可重试清理";store.cleanupNotice="JM"+task.id+" "+task.phase;}
                        try{store.save();}catch(Exception error){
                            if(!store.tasks.contains(task))store.tasks.add(task);
                            task.status="cancel_failed";task.phase="记录保存失败，再次删除可重试清理";task.error=Core.error(error,store.cookie);
                        }
                        store.activeKeys.remove(task.key);cleaningKeys.remove(task.key);
                        if(destroyed&&store.activeKeys.isEmpty())store.running=false;
                    }
                },"jm-cancel-cleanup").start();
            }
        }
    }

    private void finishQueue(){
        accepting=false;if(store.activeKeys.isEmpty())store.running=false;
        if(startedDownloads)try{store.pauseQueuedOnly();}catch(Exception error){store.note=error.getMessage();}
        if(wake.isHeld())wake.release();saveQuietly();
        if(foreground){stopForeground(true);foreground=false;}stopSelf();
    }

    private final class DownloadJob implements DownloadPool.Job {
        final Store.Task task;
        volatile JmApi.Control control;
        volatile String stop="";
        JmApi.Control watched;
        String watchedStage="";
        final RealtimeSpeed speed=new RealtimeSpeed();
        DownloadJob(Store.Task task){this.task=task;}
        public synchronized void cancel(String reason){
            if(stop.isEmpty()||reason.equals("CANCEL"))stop=reason;
            if(task.status.equals("running")||task.status.equals("resetting"))task.phase=stop.equals("CANCEL")?"正在取消…":"正在关闭请求并暂停…";
            task.speed=0;
            if(control!=null)control.cancel(stop);
        }
        private synchronized JmApi.Control attempt(){
            if(!stop.isEmpty())return null;
            control=new JmApi.Control();control.routeMessage=message->task.phase=message;
            final JmApi.Control current=control;control.rateLimit=bytes->rate.acquire(bytes,current);
            return control;
        }
        private void stopped(){task.status=task.discardRequested?"cancelling":"paused";task.phase=task.discardRequested?"正在取消并删除任务文件…":"已暂停，缓存保留";}
        public void run(){
            long begin=SystemClock.elapsedRealtime();
            try{
                while(true){
                    JmApi.Control attempt=attempt();if(attempt==null){stopped();break;}
                    // Retain the last snapshot until the cache scan has reconciled it.
                    task.status="running";task.speed=0;task.bytes=0;
                    task.resultBytes=0;task.downloadStarted=0;task.stage="metadata";saveQuietly();
                    try{
                        String result=new Downloader(DownloadService.this,store,task,attempt,store.cookie).run();
                        synchronized(store){
                            task.resultUri=result;
                            if(task.discardRequested){task.cleanupUri=result;stopped();}
                            else{
                                task.status="done";task.cleanupUri="";task.phase="下载完成"+(task.cleanupNote.isEmpty()?"":"；"+task.cleanupNote);task.error="";
                                try{LibraryStore.get(DownloadService.this).sync(store.snapshot());}catch(Exception error){store.note="文件已下载，但漫画列表保存失败："+error.getMessage();}
                            }
                        }
                        break;
                    }catch(Throwable error){
                        if(!stop.isEmpty()){stopped();break;}
                        if(error instanceof ChapterRules.ChoiceRequired){
                            task.chapterOptions=((ChapterRules.ChoiceRequired)error).chapters;
                            task.stage=attempt.stage="selection";task.phase="请选择下载章节";task.status="selecting";
                            break;
                        }
                        String reason=attempt.stop;
                        if(reason.startsWith("RESET:")){
                            if(task.resets>=task.settings.maxResets){task.status="failed";task.error=reason.substring(6)+"；已达到自动重连上限 "+task.settings.maxResets+" 次";task.phase="自动重连失败";break;}
                            task.resets++;task.status="resetting";task.phase=reason.substring(6)+"；重连 "+task.resets+"/"+task.settings.maxResets;saveQuietly();
                            long wait=SystemClock.elapsedRealtime()+Math.min(30000,3000L<<(task.resets-1));
                            while(stop.isEmpty()&&SystemClock.elapsedRealtime()<wait)Thread.sleep(200);
                            continue;
                        }
                        task.phase="下载失败，点击任务重试";
                        task.error=error instanceof OutOfMemoryError?"手机内存不足，缓存已保留。请减少同时下载任务数或图片线程后重试。":Core.error(error,store.cookie);task.status="failed";break;
                    }finally{task.elapsed=SystemClock.elapsedRealtime()-begin;task.speed=0;saveQuietly();}
                }
            }catch(Throwable error){
                if(!stop.isEmpty())stopped();else{task.status="failed";task.error=Core.error(error,store.cookie);task.phase="任务异常，缓存保留";}
            }finally{control=null;task.speed=0;if(task.discardRequested)stopped();saveQuietly();}
        }

        synchronized void monitor(long now){
            JmApi.Control active=control;if(active==null)return;
            long bytes=active.bytes.get();task.bytes=bytes;
            long saved=active.savedBytes.get();
            if(watched!=active||!watchedStage.equals(active.stage)){
                watched=active;watchedStage=active.stage;speed.reset(now,saved);
            }
            task.speed=task.status.equals("running")&&active.stop.isEmpty()&&(active.stage.equals("download")||active.stage.equals("page_retry"))?speed.sample(now,saved):0;
            if(!stop.isEmpty())return;
            if(active.stage.equals("page_retry")&&active.stop.isEmpty()&&active.networkStalled(now,Math.max(task.settings.stall,task.settings.timeout*(task.settings.retries+1)*2)*1000L))
                active.cancel("单页重试超时；已保留其他图片，请重试任务");
            if(task.status.equals("running")&&active.stop.isEmpty()&&task.settings.autoReset&&(active.stage.equals("metadata")||active.stage.equals("download"))){
                String reason="";
                // Recover only stalled network waits. Low throughput and local
                // queue, bitmap/memory or fsync waits must not reset downloads.
                if(active.stage.equals("metadata")?now-active.lastData>=task.settings.stall*1000L:active.networkStalled(now,task.settings.stall*1000L))
                    reason="连续 "+task.settings.stall+" 秒没有接收数据或取得进度";
                if(!reason.isEmpty()){task.phase="正在关闭旧连接："+reason;active.cancel("RESET:"+reason);}
            }
        }
    }

    private void monitor(){
        long now=SystemClock.elapsedRealtime();
        for(DownloadJob job:pool.snapshot())job.monitor(now);
        main.post(()->{if(!destroyed&&foreground)getSystemService(NotificationManager.class).notify(1,notification());});
        if(pool.size()>0&&now-lastSave>5000){saveQuietly();lastSave=now;}
    }

    private Notification notification(){
        int immutable=Build.VERSION.SDK_INT>=23?PendingIntent.FLAG_IMMUTABLE:0;
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|immutable);
        PendingIntent pause=PendingIntent.getService(this,1,new Intent(this,DownloadService.class).setAction(PAUSE),PendingIntent.FLAG_UPDATE_CURRENT|immutable);
        List<DownloadJob> jobs=pool.snapshot();long speed=0;StringBuilder detail=new StringBuilder();
        for(DownloadJob job:jobs){Store.Task task=job.task;speed+=task.speed;detail.append("JM").append(task.id).append(" · ").append(task.progressText()).append(" · ").append(DownloadDisplay.speed(task.speed)).append("\n").append(task.etaText()).append("\n");}
        String summary=jobs.isEmpty()?"正在启动队列":"同时下载 "+jobs.size()+" 本 · 总实时速度 "+DownloadDisplay.speed(speed);
        return new Notification.Builder(this,CHANNEL).setSmallIcon(R.drawable.ic_launcher).setContentTitle("JM Batch 正在下载")
            .setContentText(summary).setStyle(new Notification.BigTextStyle().bigText(summary+"\n"+detail))
            .setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true).setVisibility(Notification.VISIBILITY_PRIVATE)
            .addAction(new Notification.Action.Builder(null,"暂停全部",pause).build()).build();
    }
    private void saveQuietly(){try{store.save();}catch(Exception error){store.note=error.getMessage();}}
    public void onDestroy(){
        destroyed=true;accepting=false;main.removeCallbacks(dispatch);pool.cancelAll("PAUSE");
        if(monitor!=null)monitor.shutdownNow();if(wake!=null&&wake.isHeld())wake.release();
        // Retain the busy guard until every old worker has left its cache files.
        if(pool.size()>0||!cleaningKeys.isEmpty()||hasPendingCleanup())new Thread(()->{
            while(true){
                synchronized(store){
                    for(String key:pool.reap())store.activeKeys.remove(key);
                    cleanCancelled();
                    if(pool.size()==0&&cleaningKeys.isEmpty()&&!hasPendingCleanup()){store.running=false;if(startedDownloads)try{store.pauseQueued();}catch(Exception error){store.note=error.getMessage();}break;}
                }
                try{Thread.sleep(100);}catch(InterruptedException ignored){}
            }
        },"jm-download-cleanup").start();
        super.onDestroy();
    }
    public IBinder onBind(Intent intent){return null;}
}
