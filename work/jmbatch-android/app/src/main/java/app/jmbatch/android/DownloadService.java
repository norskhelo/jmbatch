package app.jmbatch.android;

import android.app.*;
import android.content.*;
import android.os.*;
import java.util.*;
import java.util.concurrent.*;

public final class DownloadService extends Service {
    public static final String START="start", PAUSE="pause", CANCEL="cancel";
    private static final String CHANNEL="downloads";
    private Store store;
    private volatile Thread runner;
    private volatile Store.Task current;
    private volatile JmApi.Control control;
    private ScheduledExecutorService monitor;
    private PowerManager.WakeLock wake;
    private final Handler main=new Handler(Looper.getMainLooper());
    private JmApi.Control watched;
    private String watchedStage="";
    private long phaseStart,lastSave;
    private final Deque<long[]> samples=new ArrayDeque<>();

    public void onCreate(){
        super.onCreate();store=Store.get(this);
        NotificationChannel channel=new NotificationChannel(CHANNEL,"下载进度",NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("显示正在进行的下载，可随时暂停");channel.setShowBadge(false);
        getSystemService(NotificationManager.class).createNotificationChannel(channel);
        wake=((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,getPackageName()+":download");
        monitor=Executors.newSingleThreadScheduledExecutor();
        monitor.scheduleAtFixedRate(()->{try{monitor();}catch(Exception error){store.note="进度监控异常："+Core.error(error,store.cookie);}},1,1,TimeUnit.SECONDS);
    }

    public int onStartCommand(Intent intent,int flags,int startId){
        String action=intent==null?PAUSE:intent.getAction();
        if(PAUSE.equals(action)){
            store.running=false;
            if(control!=null)control.cancel("PAUSE");
            if(current!=null)current.phase="正在关闭请求并暂停…";
            try{store.pauseQueued();}catch(Exception error){store.note=error.getMessage();}
            if(runner==null||!runner.isAlive())stopSelf();
            return START_NOT_STICKY;
        }
        if(CANCEL.equals(action)){
            if(current!=null&&current.key.equals(intent.getStringExtra("key"))){current.phase="正在取消…";if(control!=null)control.cancel("CANCEL");}
            else for(Store.Task task:store.snapshot())if(task.key.equals(intent.getStringExtra("key"))&&!task.status.equals("done")){task.status="cancelled";task.phase="已取消，缓存保留";}
            saveQuietly();if(runner==null||!runner.isAlive())stopSelf();return START_NOT_STICKY;
        }
        if(runner!=null&&runner.isAlive()){store.note=store.running?"队列已在运行":"正在停止旧请求，请稍后继续";return START_NOT_STICKY;}
        startForeground(1,notification(null));
        synchronized(store){
            if(store.libraryBusy){store.note="正在管理漫画文件，请稍后再开始下载";stopForeground(true);stopSelf();return START_NOT_STICKY;}
            store.running=true;
        }
        try{store.resume();}catch(Exception error){store.running=false;store.note=error.getMessage();stopForeground(true);stopSelf();return START_NOT_STICKY;}
        wake.acquire(6*60*60*1000L);
        runner=new Thread(this::runQueue,"jm-queue");runner.start();return START_NOT_STICKY;
    }

    private void runQueue(){
        try{
            while(store.running){
                Store.Task task=store.next();if(task==null)break;current=task;
                task.status="running";task.error="";long begin=SystemClock.elapsedRealtime();saveQuietly();
                while(store.running){
                    JmApi.Control attempt=new JmApi.Control();control=attempt;attempt.routeMessage=message->task.phase=message;task.done=0;task.total=0;task.cached=0;task.speed=0;task.bytes=0;
                    task.imageBytes=0;task.resultBytes=0;task.downloadStarted=0;task.stage="metadata";
                    try{
                        String result=new Downloader(this,store,task,attempt,store.cookie).run();
                        task.resultUri=result;task.status="done";task.phase="下载完成";task.error="";
                        try{LibraryStore.get(this).sync(store.snapshot());}catch(Exception indexError){store.note="文件已下载，但漫画列表保存失败："+indexError.getMessage();}
                        break;
                    }catch(Throwable error){
                        String reason=attempt.stop;
                        if(reason.equals("PAUSE")||!store.running){task.status="paused";task.phase="已暂停，缓存保留";break;}
                        if(reason.equals("CANCEL")){task.status="cancelled";task.phase="已取消，缓存保留";break;}
                        if(reason.startsWith("RESET:")){
                            if(task.resets>=task.settings.maxResets){task.status="failed";task.error=reason.substring(6)+"；已达到自动重置上限 "+task.settings.maxResets+" 次";task.phase="速度恢复失败";break;}
                            task.resets++;task.status="resetting";task.phase=reason.substring(6)+"；重连 "+task.resets+"/"+task.settings.maxResets;saveQuietly();
                            long wait=SystemClock.elapsedRealtime()+Math.min(30000,3000L<<(task.resets-1));
                            while(store.running&&SystemClock.elapsedRealtime()<wait&&!attempt.stop.equals("CANCEL")&&!attempt.stop.equals("PAUSE"))Thread.sleep(200);
                            if(attempt.stop.equals("CANCEL")){task.status="cancelled";task.phase="已取消";break;}
                            if(!store.running){task.status="paused";task.phase="已暂停";break;}
                            task.status="running";continue;
                        }
                        task.status="failed";task.phase="下载失败，点详情查看原因";
                        task.error=error instanceof OutOfMemoryError?"手机内存不足，缓存已保留。请关闭其他应用并减少线程后重试。":Core.error(error,store.cookie);break;
                    }finally{task.elapsed=SystemClock.elapsedRealtime()-begin;task.speed=0;saveQuietly();}
                }
                current=null;control=null;
            }
        }catch(Throwable error){store.note="队列异常："+Core.error(error,store.cookie);if(current!=null){current.status="failed";current.error=store.note;}}
        finally{
            current=null;control=null;store.running=false;
            try{store.pauseQueued();}catch(Exception error){store.note=error.getMessage();}
            if(wake.isHeld())wake.release();saveQuietly();
            Thread finished=Thread.currentThread();
            main.post(()->{if(runner==finished){stopForeground(true);stopSelf();}});
        }
    }

    private void monitor(){
        Store.Task task=current;JmApi.Control active=control;if(task==null||active==null)return;
        long now=SystemClock.elapsedRealtime(), bytes=active.bytes.get();task.bytes=bytes;
        if(watched!=active||!watchedStage.equals(active.stage)){
            watched=active;watchedStage=active.stage;phaseStart=now;samples.clear();samples.add(new long[]{now,bytes});
        }
        samples.addLast(new long[]{now,bytes});
        while(samples.size()>2){Iterator<long[]> it=samples.iterator();it.next();long[] second=it.next();if(second[0]<=now-task.settings.window*1000L)samples.removeFirst();else break;}
        long[] recent=samples.peekFirst();for(long[] sample:samples)if(sample[0]>=now-10000){recent=sample;break;}
        task.speed=task.status.equals("running")&&active.stop.isEmpty()&&active.stage.equals("download")?Math.max(0,bytes-recent[1])*1000/Math.max(1000,now-recent[0]):0;
        if(active.stage.equals("page_retry")&&active.stop.isEmpty()&&now-active.lastData>=Math.max(task.settings.stall,task.settings.timeout*(task.settings.retries+1)*2)*1000L){
            active.cancel("单页重试超时；已保留其他图片，请重试任务");
        }
        if(task.status.equals("running")&&active.stop.isEmpty()&&task.settings.autoReset&&(active.stage.equals("metadata")||active.stage.equals("download"))){
            String reason="";
            if(now-active.lastData>=task.settings.stall*1000L)reason="连续 "+task.settings.stall+" 秒没有接收数据或取得进度";
            else if(active.stage.equals("download")&&task.settings.slowKB>0&&now-phaseStart>=(task.settings.window+30)*1000L){
                long[] oldest=samples.peekFirst();long duration=now-oldest[0];
                if(duration>=task.settings.window*1000L&&Math.max(0,bytes-oldest[1])*1000/Math.max(1,duration)<task.settings.slowKB*1024L)
                    reason="最近 "+task.settings.window+" 秒平均速度低于 "+task.settings.slowKB+" KB/s";
            }
            if(!reason.isEmpty()){task.phase="正在关闭旧连接："+reason;active.cancel("RESET:"+reason);}
        }
        getSystemService(NotificationManager.class).notify(1,notification(task));
        if(now-lastSave>5000){saveQuietly();lastSave=now;}
    }

    private Notification notification(Store.Task task){
        int immutable=Build.VERSION.SDK_INT>=23?PendingIntent.FLAG_IMMUTABLE:0;
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|immutable);
        PendingIntent pause=PendingIntent.getService(this,1,new Intent(this,DownloadService.class).setAction(PAUSE),PendingIntent.FLAG_UPDATE_CURRENT|immutable);
        Notification.Builder builder=new Notification.Builder(this,CHANNEL).setSmallIcon(R.drawable.ic_launcher).setContentTitle("JM Batch 正在下载")
            .setContentText(task==null?"正在启动队列":task.progressText()+" · "+DownloadDisplay.speed(task.speed))
            .setContentIntent(open).setOngoing(true).setOnlyAlertOnce(true).setVisibility(Notification.VISIBILITY_PRIVATE)
            .addAction(new Notification.Action.Builder(null,"暂停",pause).build());
        if(task!=null){
            builder.setStyle(new Notification.BigTextStyle().bigText("JM"+task.id+" · "+task.progressText()+" · "+DownloadDisplay.speed(task.speed)+"\n"+task.sizeText()+"\n"+task.etaText()));
            builder.setProgress(1000,(int)(DownloadDisplay.percent(task.done,task.total,task.status)*10),task.total==0);
        }return builder.build();
    }
    private void saveQuietly(){try{store.save();}catch(Exception error){store.note=error.getMessage();}}
    public void onDestroy(){store.running=false;if(control!=null)control.cancel("PAUSE");if(monitor!=null)monitor.shutdownNow();if(wake!=null&&wake.isHeld())wake.release();super.onDestroy();}
    public IBinder onBind(Intent intent){return null;}
}
