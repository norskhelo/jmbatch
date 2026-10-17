"""Exercise the production service/cleanup with a small host Android framework.

Downloader gates simulate workers and publication; no network or user files.
"""
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
jdk,work=map(Path,sys.argv[1:3])
work.mkdir(parents=True,exist_ok=True)
sources={
'android/content/Context.java': '''package android.content;
import java.io.*;import android.os.*;import android.app.*;
public class Context {
 public static File home;public static final String POWER_SERVICE="power";
 public File getFilesDir(){return new File(home,"files");}
 public String getPackageName(){return "app.jmbatch.android";}
 public ContentResolver getContentResolver(){return new ContentResolver();}
 public Object getSystemService(String key){return new PowerManager();}
 public <T> T getSystemService(Class<T> type){try{return type.getConstructor().newInstance();}catch(Exception e){throw new RuntimeException(e);}}
}''',
'android/content/ContentResolver.java': '''package android.content;
import android.database.*;import android.net.*;
public class ContentResolver {
 public static boolean denied;public static boolean present=true;
 public Cursor query(Uri u,String[] p,String s,String[] a,String o){if(denied)throw new SecurityException("denied");return new Cursor(){public boolean moveToFirst(){return present;}public void close(){}};}
}''',
'android/database/Cursor.java':'package android.database; public interface Cursor extends AutoCloseable {boolean moveToFirst();void close();}',
'android/provider/DocumentsContract.java':'''package android.provider;import android.content.*;import android.net.*;
public class DocumentsContract {public static boolean deleteDocument(ContentResolver r,Uri u){if(ContentResolver.denied)throw new SecurityException();ContentResolver.present=false;return true;}}''',
'android/net/Uri.java':'''package android.net; public class Uri {private String value;private Uri(String v){value=v;}public static Uri parse(String v){return new Uri(v);}public String toString(){return value;}}''',
'android/content/Intent.java':'''package android.content;public class Intent {String action,key;public Intent(){}public Intent(Context c,Class<?> t){}public Intent setAction(String a){action=a;return this;}public String getAction(){return action;}public Intent putExtra(String n,String v){key=v;return this;}public String getStringExtra(String n){return key;}}''',
'android/os/Handler.java':'''package android.os;import java.util.*;public class Handler {static final List<Runnable> pending=new ArrayList<>();public Handler(Looper l){}public synchronized boolean post(Runnable r){synchronized(pending){pending.add(r);}return true;}public boolean postDelayed(Runnable r,long d){return post(r);}public void removeCallbacks(Runnable r){synchronized(pending){pending.removeIf(x->x==r);}}public static void pump(){List<Runnable> copy;synchronized(pending){copy=new ArrayList<>(pending);pending.clear();}for(Runnable r:copy)r.run();}}''',
'android/os/Looper.java':'package android.os;public class Looper {public static Looper getMainLooper(){return new Looper();}}',
'android/os/SystemClock.java':'package android.os;public class SystemClock {public static long elapsedRealtime(){return System.nanoTime()/1000000;}}',
'android/os/Build.java':'package android.os;public class Build {public static class VERSION {public static final int SDK_INT=29;}}',
'android/os/IBinder.java':'package android.os;public interface IBinder {}',
'android/os/PowerManager.java':'''package android.os;public class PowerManager {public static final int PARTIAL_WAKE_LOCK=1;public WakeLock newWakeLock(int a,String b){return new WakeLock();}public static class WakeLock {boolean held;public void acquire(long t){held=true;}public boolean isHeld(){return held;}public void release(){held=false;}}}''',
'android/app/Service.java':'''package android.app;import android.content.*;import android.os.*;public class Service extends Context {public static final int START_NOT_STICKY=2;public void onCreate(){}public void onDestroy(){}public int onStartCommand(Intent i,int f,int id){return 2;}public IBinder onBind(Intent i){return null;}public void startForeground(int i,Notification n){}public void stopForeground(boolean r){}public void stopSelf(){}}''',
'android/app/NotificationChannel.java':'package android.app;public class NotificationChannel {public NotificationChannel(String a,String b,int c){}public void setDescription(String s){}public void setShowBadge(boolean b){}}',
'android/app/NotificationManager.java':'package android.app;public class NotificationManager {public static final int IMPORTANCE_LOW=2;public void createNotificationChannel(NotificationChannel c){}public void notify(int id,Notification n){}}',
'android/app/PendingIntent.java':'''package android.app;import android.content.*;public class PendingIntent {public static final int FLAG_IMMUTABLE=1,FLAG_UPDATE_CURRENT=2;public static PendingIntent getActivity(Context c,int i,Intent n,int f){return new PendingIntent();}public static PendingIntent getService(Context c,int i,Intent n,int f){return new PendingIntent();}}''',
'android/app/Notification.java':'''package android.app;import android.content.*;public class Notification {public static final int VISIBILITY_PRIVATE=1;public static class BigTextStyle {public BigTextStyle bigText(String s){return this;}}public static class Action {public static class Builder {public Builder(Object o,String s,PendingIntent p){}public Action build(){return new Action();}}}public static class Builder {public Builder(Context c,String s){}public Builder setSmallIcon(int i){return this;}public Builder setContentTitle(String s){return this;}public Builder setContentText(String s){return this;}public Builder setStyle(BigTextStyle s){return this;}public Builder setContentIntent(PendingIntent p){return this;}public Builder setOngoing(boolean b){return this;}public Builder setOnlyAlertOnce(boolean b){return this;}public Builder setVisibility(int i){return this;}public Builder addAction(Action a){return this;}public Notification build(){return new Notification();}}}''',
'app/jmbatch/android/MainActivity.java':'package app.jmbatch.android;public class MainActivity {}',
'app/jmbatch/android/R.java':'package app.jmbatch.android;public class R {public static class drawable {public static final int ic_launcher=1;}}',
'app/jmbatch/android/Core.java':'package app.jmbatch.android;public class Core {public static String error(Throwable e,String cookie){return e.toString();}}',
'app/jmbatch/android/ChapterRules.java':'package app.jmbatch.android;import java.util.*;public class ChapterRules {public static class ChoiceRequired extends Exception {public List<Object> chapters=new ArrayList<>();}}',
'app/jmbatch/android/LibraryStore.java':'''package app.jmbatch.android;import android.content.*;import java.util.*;public class LibraryStore {public static int synced;public static LibraryStore get(Context c){return new LibraryStore();}public void sync(List<Store.Task> t){synced++;}}''',
'app/jmbatch/android/JmApi.java':'''package app.jmbatch.android;import java.util.concurrent.atomic.*;import java.util.function.*;public class JmApi {public static class Control {public volatile String stop="",stage="download";public volatile long lastData=android.os.SystemClock.elapsedRealtime();public AtomicLong bytes=new AtomicLong();public Consumer<String> routeMessage;public void cancel(String s){stop=s;}}}''',
'app/jmbatch/android/AlbumStorage.java':'''package app.jmbatch.android;import android.content.*;import android.net.*;import java.io.*;
public class AlbumStorage {public static File root(Context c){return new File(Context.home,"exports");}public static File local(Context c,Uri u)throws IOException {if(u.toString().startsWith("saf:"))return null;File f=new File(u.toString());if(!f.getCanonicalPath().startsWith(root(c).getCanonicalPath()+File.separator))throw new IOException("outside");return f;}public static void forget(Context c,Uri u){} }''',
'app/jmbatch/android/Store.java':'''package app.jmbatch.android;import android.content.*;import java.io.*;import java.util.*;import java.util.concurrent.*;
public class Store {
 public static Store instance;public final Context context;public List<Task> tasks=new ArrayList<>();public Set<String> activeKeys=ConcurrentHashMap.newKeySet();public volatile boolean running,libraryBusy;public volatile String note="",cookie="",cleanupNotice="";public Settings settings=new Settings();public List<String> saved=new ArrayList<>();
 public Store(Context c){context=c;}public static Store get(Context c){if(instance==null)instance=new Store(c);return instance;}
 public synchronized List<Task> snapshot(){return new ArrayList<>(tasks);}public synchronized void save()throws IOException {saved=new ArrayList<>();for(Task t:tasks)saved.add(t.key);}
 public synchronized Task next(){for(Task t:tasks)if(t.status.equals("queued")&&!activeKeys.contains(t.key))return t;return null;}
 public void resume(){for(Task t:tasks)if(t.status.equals("paused"))t.status="queued";}public void pauseQueued(){pauseQueuedOnly();}public void pauseQueuedOnly(){for(Task t:tasks)if(t.status.equals("queued"))t.status="paused";}
 public static class Settings {public int concurrentTasks=2,timeout=1,stall=30,retries=0,maxResets=0,window=30,slowKB=0;public boolean autoReset=false;}
 public static class Task {public String key=UUID.randomUUID().toString(),id="123456";public volatile String status="queued",phase="",error="",stage="",resultUri="",cleanupUri="",cleanupNote="";public volatile boolean discardRequested;public int done,total,cached,resets;public long speed,bytes,resultBytes,downloadStarted,elapsed;public Settings settings=new Settings();public List<Object> chapterOptions;public String progressText(){return "";}public String etaText(){return "";}}
}''',
'app/jmbatch/android/Downloader.java':'''package app.jmbatch.android;import android.content.*;import java.io.*;import java.nio.file.*;import java.util.*;import java.util.concurrent.*;
public class Downloader {
 public static final Set<String> entered=ConcurrentHashMap.newKeySet(),release=ConcurrentHashMap.newKeySet();public static volatile boolean publish;
 final Store store;final Store.Task task;final JmApi.Control control;
 public Downloader(Context c,Store s,Store.Task t,JmApi.Control a,String cookie){store=s;task=t;control=a;}
 public String run()throws Exception {File cache=new File(store.context.getFilesDir(),"work/"+task.key);cache.mkdirs();Files.write(new File(cache,"image.jpg").toPath(),new byte[]{1,2});entered.add(task.key);while(!release.contains(task.key))Thread.sleep(5);if(!publish&&!control.stop.isEmpty())throw new IOException("cancel");File file=new File(AlbumStorage.root(store.context),task.key+".zip");file.getParentFile().mkdirs();Files.write(file.toPath(),new byte[]{3,4});task.cleanupUri=file.toString();return file.toString();}
}''',
'app/jmbatch/android/CancelServiceTest.java':'''package app.jmbatch.android;
import android.os.*;import android.content.*;import java.io.*;import java.nio.file.*;import java.util.*;import java.util.concurrent.*;import java.util.function.*;
public class CancelServiceTest {
 static int checks;static void check(boolean b){checks++;if(!b)throw new AssertionError("check "+checks);}
 static void until(BooleanSupplier condition)throws Exception {long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(8);while(System.nanoTime()<end){Handler.pump();if(condition.getAsBoolean())return;Thread.sleep(10);}throw new AssertionError("timed out "+checks);}
 static File cache(Store s,Store.Task t)throws Exception {File f=new File(s.context.getFilesDir(),"work/"+t.key+"/images/0001.jpg");f.getParentFile().mkdirs();Files.write(f.toPath(),new byte[]{1,2,3});return f;}
 static void cancel(DownloadService service,Store.Task task){service.onStartCommand(new Intent().setAction(DownloadService.CANCEL).putExtra("key",task.key),0,1);}
 public static void main(String[] args)throws Exception {
  Context.home=new File(args[0]);Context.home.mkdirs();DownloadService service=new DownloadService();service.onCreate();Store s=Store.get(service);
  try{
   Store.Task a=new Store.Task(),b=new Store.Task();s.tasks.add(a);s.tasks.add(b);File image=cache(s,a),other=cache(s,b);
   service.onStartCommand(new Intent().setAction(DownloadService.START),0,1);until(()->Downloader.entered.contains(a.key)&&Downloader.entered.contains(b.key));
   cancel(service,a);cancel(service,a);check(a.discardRequested);check(image.isFile());check(s.activeKeys.contains(a.key));check(!b.discardRequested);
   service.onStartCommand(new Intent().setAction(DownloadService.PAUSE),0,1);check(a.discardRequested);Downloader.release.add(a.key);until(()->!s.snapshot().contains(a));check(!image.exists());check(!s.saved.contains(a.key));check(other.isFile());
   Downloader.release.add(b.key);until(()->!s.activeKeys.contains(b.key));check(b.status.equals("paused"));check(other.isFile());
   for(String state:new String[]{"queued","paused","selecting","failed","cancelled"}){Store.Task t=new Store.Task();t.status=state;s.tasks.add(t);File f=cache(s,t);cancel(service,t);until(()->!s.snapshot().contains(t));check(!f.exists());check(!s.saved.contains(t.key));}
   Store.Task done=new Store.Task();done.status="done";s.tasks.add(done);File keep=cache(s,done);cancel(service,done);Handler.pump();check(s.tasks.contains(done));check(keep.exists());
   Store.Task failed=new Store.Task();failed.status="paused";s.tasks.add(failed);File locked=cache(s,failed);
   try(FileInputStream stream=new FileInputStream(locked)){cancel(service,failed);until(()->failed.status.equals("cancel_failed")&&!s.activeKeys.contains(failed.key));check(s.saved.contains(failed.key));check(locked.exists());}
   cancel(service,failed);until(()->!s.snapshot().contains(failed));check(!locked.exists());
   Store.Task saf=new Store.Task();saf.status="paused";saf.cleanupUri="saf:created-by-task";s.tasks.add(saf);File sf=cache(s,saf);ContentResolver.denied=true;cancel(service,saf);until(()->saf.status.equals("cancel_failed")&&!s.activeKeys.contains(saf.key));check(sf.exists());check(s.tasks.contains(saf));ContentResolver.denied=false;cancel(service,saf);until(()->!s.snapshot().contains(saf));check(!sf.exists());check(!ContentResolver.present);
   // A cancel arriving just before publication must not be turned into done or library history.
   Store.Task race=new Store.Task();s.tasks.add(race);b.status="paused";s.tasks.remove(b);Downloader.publish=true;int syncs=LibraryStore.synced;
   service.onStartCommand(new Intent().setAction(DownloadService.START),0,1);until(()->Downloader.entered.contains(race.key));cancel(service,race);Downloader.release.add(race.key);until(()->!s.snapshot().contains(race));check(!new File(AlbumStorage.root(service),race.key+".zip").exists());check(LibraryStore.synced==syncs);
   // Restored intent with no active worker can be finished idempotently.
   Store.Task restored=new Store.Task();restored.discardRequested=true;restored.status="cancelling";s.tasks.add(restored);File restoredFile=cache(s,restored);cancel(service,restored);until(()->!s.snapshot().contains(restored));check(!restoredFile.exists());
   check(keep.exists());check(s.cleanupNotice.contains("记录已删除"));
   // WorkerDrain retains ownership through interruption until the child really exits.
   ExecutorService child=Executors.newSingleThreadExecutor();CountDownLatch entered=new CountDownLatch(1),finish=new CountDownLatch(1);child.submit(()->{entered.countDown();while(finish.getCount()>0){try{finish.await();}catch(InterruptedException ignored){}}});check(entered.await(2,TimeUnit.SECONDS));child.shutdownNow();Thread drain=new Thread(()->WorkerDrain.await(child));drain.start();drain.interrupt();Thread.sleep(50);check(drain.isAlive());finish.countDown();drain.join(2000);check(!drain.isAlive());check(drain.isInterrupted());
   System.out.println("CancelServiceTest: "+checks+" checks passed");
  }finally{Downloader.release.addAll(Downloader.entered);service.onDestroy();}
 }
}'''
}
paths=[]
for name,source in sources.items():
    p=work/'stubs'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(source,encoding='utf-8');paths.append(p)
paths += [root/'app/src/main/java/app/jmbatch/android'/f'{name}.java' for name in ('DownloadService','DownloadPool','CacheCleanup','CancelledTaskCleanup','DownloadDisplay','WorkerDrain')]
out=work/'classes';out.mkdir(exist_ok=True)
subprocess.run([str(jdk/'bin/javac.exe'),'-encoding','UTF-8','-d',str(out),*map(str,paths)],check=True)
subprocess.run([str(jdk/'bin/java.exe'),'-cp',str(out),'app.jmbatch.android.CancelServiceTest',str(work/'data')],check=True)
