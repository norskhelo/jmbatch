package app.jmbatch.android;

import java.net.*;
import java.util.*;
import java.time.Duration;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import android.content.SharedPreferences;
import org.robolectric.RuntimeEnvironment;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.*;
import org.robolectric.shadows.ShadowSystemClock;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},instrumentedPackages={"app.jmbatch.android"},shadows={ChapterRouteRuntimeTest.Transport.class})
public class ChapterRouteRuntimeTest {
    static final AtomicInteger discoveryReads=new AtomicInteger();
    static int settingsReads,albums;
    static boolean blockSaved,refuseSaved,slowBook;
    static CountDownLatch slowStarted,slowStopped,renewing,allowRenewal;
    static boolean holdRecovery;
    static CountDownLatch savedEntered, savedStopped;
    static volatile String albumHost;
    static boolean slowBuiltins,staleAlbum,limited,race;
    static java.util.concurrent.CountDownLatch loserStopped;
    private static SharedPreferences prefs(){
        return RuntimeEnvironment.getApplication().getSharedPreferences("chapter-catalog",0);
    }
    private static void clearMemory()throws Exception {
        for(String name:new String[]{"rememberedRoutes","anonymousCatalog"}){
            java.lang.reflect.Field field=JmApi.class.getDeclaredField(name);field.setAccessible(true);
            ((java.util.concurrent.atomic.AtomicReference<?>)field.get(null)).set(null);
        }
    }
    @Before public void reset()throws Exception {
        clearMemory();prefs().edit().clear().commit();
        savedEntered=new CountDownLatch(1);savedStopped=new CountDownLatch(1);
        renewing=new CountDownLatch(1);allowRenewal=new CountDownLatch(1);holdRecovery=false;
        slowStarted=new CountDownLatch(1);slowStopped=new CountDownLatch(1);
        blockSaved=refuseSaved=slowBook=false;albumHost="";
        discoveryReads.set(0);settingsReads=albums=0;slowBuiltins=staleAlbum=limited=race=false;
        loserStopped=new java.util.concurrent.CountDownLatch(1);
    }
    @Implements(value=JmApi.class,isInAndroidSdk=false)
    public static class Transport {
        @RealObject JmApi owner;
        private static String encrypted(String value,String secret)throws Exception {
            java.nio.charset.Charset utf8=java.nio.charset.StandardCharsets.UTF_8;
            javax.crypto.Cipher cipher=javax.crypto.Cipher.getInstance("AES/ECB/PKCS5Padding");
            cipher.init(javax.crypto.Cipher.ENCRYPT_MODE,new javax.crypto.spec.SecretKeySpec(Core.md5(secret).getBytes(utf8),"AES"));
            return Base64.getEncoder().encodeToString(cipher.doFinal(value.getBytes(utf8)));
        }
        @Implementation protected String text(String address,Map<String,String> headers,boolean api,int timeout)throws Exception {
            URL url=new URL(address);
            if(!api){
                discoveryReads.incrementAndGet();
                if(race&&address.equals(JmApi.DOMAIN_SERVERS[0])){
                    try{
                        for(int i=0;i<150;i++){owner.control.check();Thread.sleep(20);}
                        throw new AssertionError("slow discovery blocked other routes");
                    }finally{loserStopped.countDown();}
                }
                if(race)return encrypted("{\"Server\":[\"fixture.test\"]}",Core.DOMAIN_SECRET);
                throw new SocketTimeoutException("discovery unavailable");
            }
            if(url.getPath().equals("/setting")){
                synchronized(ChapterRouteRuntimeTest.class){settingsReads++;}
                if(holdRecovery&&settingsReads>1){renewing.countDown();assertTrue(allowRenewal.await(5,TimeUnit.SECONDS));}
                if(url.getHost().equals("saved.test")){
                    if(refuseSaved)throw new JmApi.HttpError(404);
                    if(blockSaved){
                        savedEntered.countDown();
                        try{while(true){owner.control.check();Thread.sleep(20);}}
                        finally{savedStopped.countDown();}
                    }
                }

                return "{}";
            }
            assertEquals("/album",url.getPath());albumHost=url.getHost();albums++;
            if(holdRecovery&&timeout<=5&&url.getQuery().equals("id=99"))throw new SocketTimeoutException();
            if(slowBook&&url.getQuery().equals("id=99")){
                if(timeout<=5){Thread.sleep(1000);throw new SocketTimeoutException("quick route");}
                slowStarted.countDown();
                try{Thread.sleep(25000);throw new AssertionError("long read was not cancelled");}
                finally{slowStopped.countDown();}
            }
            if(slowBuiltins&&timeout<=5)throw new SocketTimeoutException("short attempt expired");
            if(limited)throw new JmApi.HttpError(429);
            String id=staleAlbum&&timeout<=5?"1":url.getQuery().substring(3);
            org.json.JSONObject album=new org.json.JSONObject().put("id",id).put("name","fixture");
            String timestamp=headers.get("tokenparam").split(",")[0];
            return new org.json.JSONObject().put("code",200).put("data",encrypted(album.toString(),timestamp+Core.API_SECRET)).toString();
        }
    }
    private ChapterUpdates.Session open(String cookie)throws Exception {
        Store.Settings settings=new Store.Settings();settings.retries=0;
        return ChapterUpdates.open(org.robolectric.RuntimeEnvironment.getApplication(),settings,cookie,new JmApi.Control());
    }
    @Test public void slowPrimaryDiscoveryDoesNotBlockAWorkingBackup()throws Exception {
        race=true;assertEquals("42",open("").get("42").get(0).id);
        assertTrue(loserStopped.await(2,java.util.concurrent.TimeUnit.SECONDS));
        assertEquals(1,settingsReads);
    }
    @Test public void anonymousWarmCheckStillFetchesAlbumAndLoginsHaveSeparateSessions()throws Exception {
        open("").get("42");open("").get("42");
        assertEquals(2,albums);assertEquals(1,settingsReads);assertEquals(3,discoveryReads.get());
        open("account=A").get("42");open("account=B").get("42");assertEquals(3,settingsReads);
        ShadowSystemClock.advanceBy(Duration.ofMinutes(3));
        open("").get("42");assertEquals(4,settingsReads);assertEquals(5,albums);
    }
    @Test public void quickTimeoutFallsBackToDiscoveryAndFullTimeout()throws Exception {
        open("").get("42");slowBuiltins=true;assertEquals("42",open("").get("42").get(0).id);
        assertEquals(6,discoveryReads.get());assertEquals(2,settingsReads);
    }
    @Test public void staleSessionRenewsOnceWithoutAcceptingAnotherAlbum()throws Exception {
        open("").get("42");staleAlbum=true;
        ChapterUpdates.Session session=open("");assertEquals("42",session.get("42").get(0).id);
        assertEquals("43",session.get("43").get(0).id);assertEquals(6,discoveryReads.get());
        assertEquals(2,settingsReads);assertEquals(4,albums);
    }
    @Test public void lastVerifiedHostSurvivesProcessRestart()throws Exception {
        race=true;open("").get("42");
        assertEquals("fixture.test",prefs().getString("host",""));
        clearMemory();discoveryReads.set(0);race=false;
        open("account=A").get("43");
        assertEquals(0,discoveryReads.get());assertEquals("fixture.test",albumHost);
        assertEquals(Collections.singleton("host"),prefs().getAll().keySet());
    }
    @Test public void staleSavedRouteStartsDiscoveryAndCancelsLosingConnection()throws Exception {
        prefs().edit().putString("host","saved.test").commit();blockSaved=true;
        assertEquals("42",open("").get("42").get(0).id);
        assertEquals(0,savedEntered.getCount());assertTrue(savedStopped.await(2,TimeUnit.SECONDS));
        assertTrue(discoveryReads.get()>0);assertNotEquals("saved.test",albumHost);
        assertEquals(albumHost,prefs().getString("host",""));
    }
    @Test public void failedAlbumDoesNotReplaceSavedHost()throws Exception {
        prefs().edit().putString("host","saved.test").commit();refuseSaved=true;limited=true;
        try{open("").get("42");fail();}catch(JmApi.HttpError expected){assertEquals(429,expected.code);}
        assertEquals("saved.test",prefs().getString("host",""));
    }
    @Test public void healthyBookDoesNotWaitForAnotherBooksRecovery()throws Exception {
        holdRecovery=true;
        ChapterUpdates.Session session=open("");ExecutorService caller=Executors.newFixedThreadPool(2);
        try{
            Future<String> slow=caller.submit(()->session.get("99").get(0).id);
            assertTrue(renewing.await(2,TimeUnit.SECONDS));
            assertEquals("42",caller.submit(()->session.get("42").get(0).id).get(1,TimeUnit.SECONDS));
            allowRenewal.countDown();assertEquals("99",slow.get(2,TimeUnit.SECONDS));
        }finally{allowRenewal.countDown();caller.shutdownNow();}
    }
    @Test public void oneDeadlineCoversRetriesAndRecoveryAndLeavesOtherBooksUsable()throws Exception {
        slowBook=true;
        ChapterUpdates.Session session=open("");ExecutorService pool=Executors.newFixedThreadPool(4);
        try{
            Future<?> slow=pool.submit(()->session.get("99"));
            List<Future<String>> healthy=new ArrayList<>();
            for(int i=1;i<=9;i++){String id=String.valueOf(i);healthy.add(pool.submit(()->session.get(id).get(0).id));}
            for(int i=1;i<=9;i++)assertEquals(String.valueOf(i),healthy.get(i-1).get(3,TimeUnit.SECONDS));
            assertTrue(slowStarted.await(4,TimeUnit.SECONDS));
            // A fresh 15 s allowance on the full retry would exceed the remaining ~13 s.
            try{slow.get(14,TimeUnit.SECONDS);fail();}
            catch(ExecutionException expected){
                assertTrue(expected.getCause() instanceof SocketTimeoutException);
                assertTrue(expected.getCause().getMessage().contains("15 秒"));
            }
            assertTrue(slowStopped.await(1,TimeUnit.SECONDS));
            assertEquals("10",session.get("10").get(0).id);
        }finally{pool.shutdownNow();}
    }
    @Test public void cancellingBatchReleasesBookDuringSharedSetup()throws Exception {
        prefs().edit().putString("host","saved.test").commit();blockSaved=true;
        JmApi.Control control=new JmApi.Control();
        ChapterUpdates.Session session=ChapterUpdates.open(RuntimeEnvironment.getApplication(),new Store.Settings(),"",control);
        ExecutorService caller=Executors.newSingleThreadExecutor();
        try{
            Future<?> request=caller.submit(()->session.get("5"));
            assertTrue(savedEntered.await(2,TimeUnit.SECONDS));control.cancel("检查已取消");
            try{request.get(1,TimeUnit.SECONDS);fail();}
            catch(ExecutionException expected){assertTrue(expected.getCause().getMessage().contains("检查已取消"));}
            assertTrue(savedStopped.await(2,TimeUnit.SECONDS));
        }finally{caller.shutdownNow();}
    }
    @Test public void rateLimitIsReportedWithoutDiscoveryOrRepeat()throws Exception {
        limited=true;try{open("").get("42");fail();}catch(JmApi.HttpError expected){assertEquals(429,expected.code);}
        assertEquals(3,discoveryReads.get());assertEquals(1,albums);
    }
}
