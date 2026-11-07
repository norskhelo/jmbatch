package app.jmbatch.android;

import java.net.*;
import java.util.*;
import java.time.Duration;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.*;
import org.robolectric.shadows.ShadowSystemClock;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(manifest=Config.NONE,sdk={29,35},instrumentedPackages={"app.jmbatch.android"},shadows={ChapterRouteRuntimeTest.Transport.class})
public class ChapterRouteRuntimeTest {
    static int discovery,settingsReads,albums;
    static boolean slowBuiltins,staleAlbum,limited,race;
    static java.util.concurrent.CountDownLatch loserStopped;
    @Before public void reset()throws Exception {
        for(String name:new String[]{"rememberedRoutes","anonymousCatalog"}){
            java.lang.reflect.Field field=JmApi.class.getDeclaredField(name);field.setAccessible(true);
            ((java.util.concurrent.atomic.AtomicReference<?>)field.get(null)).set(null);
        }
        discovery=settingsReads=albums=0;slowBuiltins=staleAlbum=limited=race=false;
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
                discovery++;
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
                settingsReads++;

                return "{}";
            }
            assertEquals("/album",url.getPath());albums++;
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
        return ChapterUpdates.open(settings,cookie,new JmApi.Control());
    }
    @Test public void slowPrimaryDiscoveryDoesNotBlockAWorkingBackup()throws Exception {
        race=true;assertEquals("42",open("").get("42").get(0).id);
        assertTrue(loserStopped.await(2,java.util.concurrent.TimeUnit.SECONDS));
        assertEquals(1,settingsReads);
    }
    @Test public void anonymousWarmCheckStillFetchesAlbumAndLoginsHaveSeparateSessions()throws Exception {
        open("").get("42");open("").get("42");
        assertEquals(2,albums);assertEquals(1,settingsReads);assertEquals(3,discovery);
        open("account=A").get("42");open("account=B").get("42");assertEquals(3,settingsReads);
        ShadowSystemClock.advanceBy(Duration.ofMinutes(3));
        open("").get("42");assertEquals(4,settingsReads);assertEquals(5,albums);
    }
    @Test public void quickTimeoutFallsBackToDiscoveryAndFullTimeout()throws Exception {
        open("").get("42");slowBuiltins=true;assertEquals("42",open("").get("42").get(0).id);
        assertEquals(6,discovery);assertEquals(2,settingsReads);
    }
    @Test public void staleSessionRenewsOnceWithoutAcceptingAnotherAlbum()throws Exception {
        open("").get("42");staleAlbum=true;
        ChapterUpdates.Session session=open("");assertEquals("42",session.get("42").get(0).id);
        assertEquals("43",session.get("43").get(0).id);assertEquals(6,discovery);
        assertEquals(2,settingsReads);assertEquals(4,albums);
    }
    @Test public void rateLimitIsReportedWithoutDiscoveryOrRepeat()throws Exception {
        limited=true;try{open("").get("42");fail();}catch(JmApi.HttpError expected){assertEquals(429,expected.code);}
        assertEquals(3,discovery);assertEquals(1,albums);
    }
}
