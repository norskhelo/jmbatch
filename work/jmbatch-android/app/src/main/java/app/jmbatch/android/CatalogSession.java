package app.jmbatch.android;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.SystemClock;
import java.net.SocketTimeoutException;
import java.util.*;
import java.util.concurrent.*;

/** One library check shares setup and recovery, but each album owns its request and deadline. */
final class CatalogSession implements ChapterUpdates.Session {
    static final int BOOK_TIMEOUT_MS=15000;
    private static final int BACKUP_DELAY_MS=1000;
    private static final String TIMEOUT="章节目录检查超时（15 秒）";
    private static ThreadPoolExecutor pool(String name,int size) {
        ThreadPoolExecutor pool=new ThreadPoolExecutor(size,size,20,TimeUnit.SECONDS,new LinkedBlockingQueue<>(),
                r->{Thread t=new Thread(r,name);t.setDaemon(true);return t;});
        pool.allowCoreThreadTimeOut(true);
        return pool;
    }
    private static final ThreadPoolExecutor books=pool("jm-catalog-book",4);
    private static final ThreadPoolExecutor sessions=pool("jm-catalog-session",3);
    private static final ThreadPoolExecutor connections=pool("jm-catalog-connect",4);
    private static final ScheduledThreadPoolExecutor deadlines=new ScheduledThreadPoolExecutor(1,
            r->{Thread t=new Thread(r,"jm-catalog-timeout");t.setDaemon(true);return t;});
    static {deadlines.setRemoveOnCancelPolicy(true);}
    private final Store.Settings settings;
    private final String cookie;
    private final JmApi.Control batch;
    private final SharedPreferences prefs;
    private final Future<JmApi> initial;
    private Future<JmApi> recovery;
    private volatile JmApi recovered;

    CatalogSession(Context context,Store.Settings settings,String cookie,JmApi.Control batch) {
        this.settings=settings;this.cookie=cookie;this.batch=batch;
        prefs=context.getSharedPreferences("chapter-catalog",Context.MODE_PRIVATE);
        initial=sessions.submit(this::connect);
    }

    private JmApi connect()throws Exception {
        batch.check();
        JmApi api=new JmApi(settings,cookie,batch);
        if(api.reuseAnonymousCatalog())return api;
        List<String> saved=NetworkRoutes.merge(Collections.singletonList(prefs.getString("host","")),Collections.emptyList());
        if(saved.isEmpty()){
            api.initializeCatalogRoutes(false,true);
            return api;
        }

        // Each contender has its own cookie jar and sockets. Only the winning session is used.
        CompletionService<JmApi> finished=new ExecutorCompletionService<>(connections);
        JmApi.Control primary=new JmApi.Control(),backup=new JmApi.Control();
        Future<JmApi> first=finished.submit(()->{
            JmApi candidate=new JmApi(settings,cookie,primary);
            candidate.initializeSavedCatalog(saved.get(0));
            return candidate;
        });
        Future<JmApi> second=null;
        try{
            Future<JmApi> ready=finished.poll(BACKUP_DELAY_MS,TimeUnit.MILLISECONDS);
            if(ready!=null){
                try{return value(ready);}
                catch(Exception error){if(!routeUnavailable(error))throw error;}
            }
            batch.check();
            second=finished.submit(()->{
                JmApi candidate=new JmApi(settings,cookie,backup);
                candidate.initializeCatalogRoutes(true,true);
                return candidate;
            });
            int remaining=ready==null?2:1;
            while(true){
                batch.check();
                ready=finished.poll(100,TimeUnit.MILLISECONDS);
                if(ready==null)continue;
                try{return value(ready);}
                catch(Exception error){if(--remaining==0||!routeUnavailable(error))throw error;}
            }
        }finally{
            primary.cancel("线路选择结束");backup.cancel("线路选择结束");
            first.cancel(true);if(second!=null)second.cancel(true);
        }
    }

    private static boolean routeUnavailable(Exception error){
        NetworkRoutes.HttpFailure http=NetworkRoutes.httpFailure(error);
        return error instanceof NetworkRoutes.Exhausted || http!=null&&(http.code==404||http.code==410);
    }

    private static <T> T value(Future<T> future)throws Exception {
        try{return future.get();}
        catch(ExecutionException error){throw cause(error);}
    }
    private static Exception cause(ExecutionException error){
        Throwable cause=error.getCause();
        if(cause instanceof Error)throw (Error)cause;
        return cause instanceof Exception?(Exception)cause:error;
    }

    private synchronized Future<JmApi> recover(JmApi stale)throws Exception {
        batch.check();
        if(recovery==null){
            stale.forgetCatalog();
            recovery=sessions.submit(()->{
                batch.check();
                JmApi replacement=new JmApi(settings,cookie,batch);
                replacement.initializeCatalogRoutes(true,false);
                recovered=replacement;
                return replacement;
            });
        }
        return recovery;
    }

    private static final class Album {
        final JmApi session,request;
        final List<ChapterRules.Chapter> chapters;
        Album(JmApi session,String id,JmApi.Control control)throws Exception {
            control.check();
            this.session=session;request=session.catalogRequest(control);
            chapters=ChapterSelection.catalog(request.detail("album",id),id);
        }
    }
    private Album fetch(String id,JmApi.Control control)throws Exception {
        // Other albums can keep using the original session while a slow one renews it.
        JmApi api=recovered;
        if(api!=null)return new Album(api,id,control);
        api=value(initial);
        try{return new Album(api,id,control);}
        catch(NetworkRoutes.Exhausted|JmApi.WrongAlbum stale){
            control.check();if(!api.usesQuickCatalog())throw stale;
        }catch(JmApi.HttpError denied){
            control.check();if(!api.usesQuickCatalog()||denied.code!=401)throw denied;
        }
        return new Album(value(recover(api)),id,control);
    }

    @Override public List<ChapterRules.Chapter> get(String id)throws Exception {
        batch.check();
        if(!id.matches("[0-9]{1,10}"))throw new java.io.IOException("漫画编号无效");
        long end=SystemClock.elapsedRealtime()+BOOK_TIMEOUT_MS;
        JmApi.Control control=new JmApi.Control();
        FutureTask<Album> task=new FutureTask<>(()->fetch(id,control));
        ScheduledFuture<?> timeout=deadlines.schedule(()->task.cancel(true),BOOK_TIMEOUT_MS,TimeUnit.MILLISECONDS);
        try{
            books.execute(task);
            // A DNS lookup or disconnect can outlive socket timeouts. Bound the caller as well.
            while(SystemClock.elapsedRealtime()<end){
                batch.check();
                try{
                    Album album=task.get(100,TimeUnit.MILLISECONDS);
                    batch.check();
                    if(SystemClock.elapsedRealtime()>=end)break;
                    synchronized(this){
                        String host=album.session.rememberCatalog(album.request);
                        if(!host.equals(prefs.getString("host","")))prefs.edit().putString("host",host).apply();
                    }
                    return album.chapters;
                }catch(TimeoutException waiting){/* Check for batch cancellation. */}
                catch(CancellationException expired){break;}
                catch(ExecutionException failure){
                    batch.check();
                    if(SystemClock.elapsedRealtime()>=end)break;
                    throw cause(failure);
                }
            }
            throw new SocketTimeoutException(TIMEOUT);
        }finally{
            timeout.cancel(false);
            control.cancel("本书检查结束");
            task.cancel(true);
            books.remove(task);
        }
    }
}
